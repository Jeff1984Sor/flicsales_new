"""Regras puras: CNPJ/CPF/CEP/UF, endereço da pessoa x empresa, preencher vazios pelo CNPJ e células de planilha."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.domain import RegraViolada
from app.domain import planilha as cel
from app.domain.cadastro import (
    PessoaEndereco,
    cnpj_valido,
    cpf_valido,
    normalizar_endereco,
    preencher_vazios,
    propagar_endereco,
    resolver_endereco_pessoa,
    validar_cep,
    validar_cnpj,
    validar_documento,
    validar_uf,
)

EMPRESA = {"cep": "01310-100", "logradouro": "Avenida Paulista", "numero": "1000", "complemento": None,
           "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "SP"}


# ------------------------------------------------------------------------------------------------- documentos
def test_cnpj_digitos_verificadores():
    assert cnpj_valido("11.222.333/0001-81") and cnpj_valido("11222333000181")
    assert not cnpj_valido("11.222.333/0001-82")
    assert not cnpj_valido("11111111111111")  # todos iguais
    assert not cnpj_valido("123") and not cnpj_valido(None)
    assert validar_cnpj("11222333000181") == "11.222.333/0001-81"
    with pytest.raises(RegraViolada, match="CNPJ inválido."):
        validar_cnpj("12.345.678/0001-90")


def test_documento_aceita_cnpj_ou_cpf():
    assert cpf_valido("529.982.247-25") and not cpf_valido("529.982.247-26")
    assert validar_documento("52998224725") == "529.982.247-25"
    assert validar_documento("") is None
    with pytest.raises(RegraViolada, match="CPF inválido"):
        validar_documento("111.111.111-11")
    with pytest.raises(RegraViolada, match="14 dígitos"):
        validar_documento("123456")


def test_cep_e_uf():
    assert validar_cep("01310100") == "01310-100" == validar_cep(" 01310-100 ")
    with pytest.raises(RegraViolada, match="CEP inválido"):
        validar_cep("1310-10")
    assert validar_uf(" sp ") == "SP"
    with pytest.raises(RegraViolada, match="UF inválida"):
        validar_uf("XX")


def test_normalizar_endereco_so_mexe_no_que_veio():
    assert normalizar_endereco({"cep": "01310100", "uf": "rj", "bairro": "  Centro  ", "logradouro": "  ",
                                "nome": "x"}) == {"cep": "01310-100", "uf": "RJ", "bairro": "Centro",
                                                  "logradouro": None, "nome": "x"}
    assert normalizar_endereco({}) == {}


# ------------------------------------------------------------------------------------------------- endereço
def test_pessoa_nova_com_empresa_usa_endereco_da_empresa():
    marca, end = resolver_endereco_pessoa(marca_atual=True, endereco_atual={}, enviado={}, marca_enviada=None,
                                          endereco_empresa=EMPRESA)
    assert marca is True and end == EMPRESA


def test_marca_ligada_ignora_endereco_enviado_igual():
    marca, end = resolver_endereco_pessoa(marca_atual=True, endereco_atual=EMPRESA, enviado={"cidade": "São Paulo"},
                                          marca_enviada=None, endereco_empresa=EMPRESA)
    assert marca is True and end == EMPRESA


def test_editar_endereco_desliga_a_marca():
    marca, end = resolver_endereco_pessoa(marca_atual=True, endereco_atual=EMPRESA, enviado={"numero": "200"},
                                          marca_enviada=None, endereco_empresa=EMPRESA)
    assert marca is False and end["numero"] == "200" and end["logradouro"] == "Avenida Paulista"


def test_marca_explicita_vence():
    marca, end = resolver_endereco_pessoa(marca_atual=False, endereco_atual={"cidade": "Rio"}, enviado={"cidade": "X"},
                                          marca_enviada=True, endereco_empresa=EMPRESA)
    assert marca is True and end == EMPRESA
    marca, end = resolver_endereco_pessoa(marca_atual=True, endereco_atual=EMPRESA, enviado={}, marca_enviada=False,
                                          endereco_empresa=EMPRESA)
    assert marca is False and end == EMPRESA  # desligar mantém o endereço que estava (agora editável)


def test_sem_empresa_fica_o_enviado():
    marca, end = resolver_endereco_pessoa(marca_atual=True, endereco_atual={}, enviado={"cidade": "Recife"},
                                          marca_enviada=True, endereco_empresa=None)
    assert marca is True and end["cidade"] == "Recife"


def test_propagar_so_para_quem_tem_a_marca_e_mudou():
    pessoas = [PessoaEndereco(1, True, {}), PessoaEndereco(2, False, {"cidade": "Rio"}),
               PessoaEndereco(3, True, dict(EMPRESA))]
    assert propagar_endereco(EMPRESA, pessoas) == [(1, EMPRESA)]


def test_preencher_vazios_nao_sobrescreve():
    atual = {"segmento": "Consultoria", "telefone": None, "cep": ""}
    consulta = {"segmento": "Outro", "telefone": "(11) 3333-4444", "cep": "01310-100", "porte": None}
    assert preencher_vazios(atual, consulta) == {"telefone": "(11) 3333-4444", "cep": "01310-100"}


# ------------------------------------------------------------------------------------------------- planilha
def test_celulas_de_texto_e_digitos():
    assert cel.texto(11999990000.0) == "11999990000"
    assert cel.texto("  a   b ") == "a b"
    assert cel.texto("") is None
    with pytest.raises(RegraViolada, match="maior que 3"):
        cel.texto("abcd", max_len=3)
    assert cel.digitos(1310100, tamanhos=(8,)) == "01310100"
    assert cel.digitos(1222333000181, tamanhos=(11, 14)) == "01222333000181"
    assert cel.digitos("01.310-100") == "01310100"


@pytest.mark.parametrize("entrada,esperado", [
    ("1.234,56", "1234.56"), ("1234,5", "1234.50"), ("1234.56", "1234.56"), ("R$ 24.000,00", "24000.00"),
    ("1.500", "1500.00"), ("-10,00", "-10.00"), (2400.5, "2400.50"), (3, "3.00"), ("1,234.56", "1234.56"),
])
def test_decimal(entrada, esperado):
    assert cel.decimal(entrada) == Decimal(esperado)


def test_decimal_invalido_e_minimo():
    with pytest.raises(RegraViolada, match="Informe um número"):
        cel.decimal("abc")
    with pytest.raises(RegraViolada, match="menor que 0"):
        cel.decimal("-1", minimo=Decimal("0"))


def test_data_sim_nao_opcao_lista():
    assert cel.data("05/11/2026") == date(2026, 11, 5) == cel.data("2026-11-05") == cel.data(datetime(2026, 11, 5))
    with pytest.raises(RegraViolada, match="DD/MM/AAAA"):
        cel.data("31/02/2026")
    assert cel.sim_nao("Sim") is True and cel.sim_nao("não") is False and cel.sim_nao("") is None
    with pytest.raises(RegraViolada, match="Sim ou Não"):
        cel.sim_nao("talvez")
    canais = {"E-mail": "email", "Ligação": "ligacao"}
    assert cel.opcao("ligacao", canais) == "ligacao" == cel.opcao("LIGAÇÃO", canais)
    with pytest.raises(RegraViolada, match="Use uma das opções: E-mail, Ligação."):
        cel.opcao("fax", canais)
    papeis = {"cliente": "cliente", "fornecedor": "fornecedor"}
    assert cel.lista("Cliente, fornecedor; cliente", papeis) == ["cliente", "fornecedor"]


def test_cabecalho_e_linha_de_exemplo():
    assert cel.chave_cabecalho("Nome *") == "nome" == cel.chave_cabecalho(" NOME")
    assert cel.chave_cabecalho("Número") == "numero"
    assert cel.linha_de_exemplo("EXEMPLO: Aurora") and not cel.linha_de_exemplo("Aurora")
