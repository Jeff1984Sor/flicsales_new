"""Regras puras dos ajustes do Núcleo, parte 2 (11/2026): contatos da pessoa, desconto/recorrência do produto,
campos sugeridos, campos padrões, exibir na etapa, listas da governança, classificação de modelos e assinatura."""

from decimal import Decimal

import pytest

from app.domain import RegraViolada, contatos, listas
from app.domain import assinatura as ass
from app.domain import campos_padrao as cp
from app.domain import campos_sugeridos as cs
from app.domain import enriquecimento as enr
from app.domain.campos_exibicao import EtapaRef, validar_exibicao, visivel_na_oportunidade
from app.domain.modelos_comunicacao import classificacoes_do_filtro
from app.domain.produto import descrever_recorrencia, validar_desconto, validar_recorrencia
from app.modules.nucleo.regras import slug_de


# ------------------------------------------------------------------------------------------------- contatos
def test_telefones_normaliza_e_um_principal():
    r = contatos.validar_telefones([{"numero": "11 3333-4444", "tipo": "fixo"},
                                    {"numero": "+55 (11) 98888-7777", "tipo": "whatsapp", "principal": True},
                                    {"numero": "  "}])
    assert r == [{"numero": "(11) 98888-7777", "tipo": "whatsapp", "principal": True},
                 {"numero": "(11) 3333-4444", "tipo": "fixo", "principal": False}]
    assert contatos.validar_telefones([{"numero": "11988887777"}])[0]["principal"] is True  # nenhum → o primeiro
    assert contatos.validar_telefones([]) == []
    with pytest.raises(RegraViolada, match="só um telefone"):
        contatos.validar_telefones([{"numero": "1133334444", "principal": True},
                                    {"numero": "11988887777", "principal": True}])
    with pytest.raises(RegraViolada, match="repetido"):
        contatos.validar_telefones([{"numero": "1133334444"}, {"numero": "(11) 3333-4444"}])
    with pytest.raises(RegraViolada, match="Tipo de telefone"):
        contatos.validar_telefones([{"numero": "1133334444", "tipo": "pager"}])
    with pytest.raises(RegraViolada, match="Telefone inválido"):
        contatos.validar_telefones([{"numero": "123"}])


def test_emails_validados_sem_repeticao():
    r = contatos.validar_emails([{"email": "Paula@Aurora.com.br"}, {"email": "p@gmail.com", "tipo": "pessoal"}])
    assert r[0] == {"email": "paula@aurora.com.br", "tipo": "comercial", "principal": True}
    assert r[1]["principal"] is False and r[1]["tipo"] == "pessoal"
    with pytest.raises(RegraViolada, match="E-mail repetido"):
        contatos.validar_emails([{"email": "a@b.com"}, {"email": "A@B.com"}])
    with pytest.raises(RegraViolada, match="E-mail inválido"):
        contatos.validar_emails([{"email": "sem-arroba"}])
    with pytest.raises(RegraViolada, match="só um e-mail"):
        contatos.validar_emails([{"email": "a@b.com", "principal": True}, {"email": "c@d.com", "principal": True}])


def test_principal_e_cliente_antigo():
    lista = [{"email": "a@b.com", "tipo": "comercial", "principal": True},
             {"email": "c@d.com", "tipo": "pessoal", "principal": False}]
    assert contatos.principal_de(lista, "email") == "a@b.com"
    assert contatos.principal_de([], "email") is None
    # valor novo troca o principal sem apagar os outros
    novo = contatos.aplicar_principal(lista, "x@y.com", "email", tipo_padrao="comercial")
    assert [i["email"] for i in novo] == ["x@y.com", "c@d.com"] and novo[0]["principal"]
    # valor que já existe vira o principal
    assert contatos.aplicar_principal(lista, "c@d.com", "email", tipo_padrao="comercial")[0]["email"] == "c@d.com"
    # vazio: o principal sai e o próximo assume
    assert contatos.aplicar_principal(lista, None, "email", tipo_padrao="comercial") == [
        {"email": "c@d.com", "tipo": "pessoal", "principal": True}]
    assert contatos.aplicar_principal([], "1133334444", "numero", tipo_padrao="celular") == [
        {"numero": "1133334444", "tipo": "celular", "principal": True}]


def test_juntar_adicionais_da_planilha():
    lista = [{"email": "a@b.com", "tipo": "comercial", "principal": True},
             {"email": "velho@b.com", "tipo": "pessoal", "principal": False}]
    r = contatos.juntar_adicionais(lista, ["n1@b.com", "A@b.com", "n1@b.com"], "email", tipo_padrao="comercial",
                                   normalizar=contatos.normalizar_email)
    assert [i["email"] for i in r] == ["a@b.com", "n1@b.com"]


# ------------------------------------------------------------------------------------------------- produto
def test_desconto():
    assert validar_desconto(None, None, Decimal("100")) == (None, None)
    assert validar_desconto("percentual", "10", None) == ("percentual", Decimal("10.00"))
    assert validar_desconto("valor", Decimal("100"), Decimal("100")) == ("valor", Decimal("100.00"))
    for tipo, valor, preco, msg in (("percentual", "101", None, "0 a 100"),
                                    ("valor", "150", Decimal("100"), "preço de referência"),
                                    ("valor", "-1", None, "negativo"),
                                    ("percentual", None, None, "Informe o valor"),
                                    (None, "5", None, "Escolha o tipo"),
                                    ("bonus", "5", None, "Tipo de desconto inválido")):
        with pytest.raises(RegraViolada, match=msg):
            validar_desconto(tipo, valor, preco)


def test_recorrencia():
    assert validar_recorrencia(False, "semanal", 3, ["seg"]).frequencia is None
    r = validar_recorrencia(True, None, None, None)
    assert (r.frequencia, r.intervalo, r.dias_semana) == ("mensal", 1, [])
    r = validar_recorrencia(True, "semanal", 2, ["qua", "seg", "seg"])
    assert (r.intervalo, r.dias_semana) == (2, ["seg", "qua"])
    assert validar_recorrencia(True, "semestral", 4, None).intervalo == 1
    assert validar_recorrencia(True, "mensal", 2, ["seg"]).dias_semana == []
    with pytest.raises(RegraViolada, match="ao menos um dia"):
        validar_recorrencia(True, "semanal", 1, [])
    with pytest.raises(RegraViolada, match="1 ou mais"):
        validar_recorrencia(True, "diaria", 0, None)
    with pytest.raises(RegraViolada, match="Frequência inválida"):
        validar_recorrencia(True, "quinzenal", 1, None)
    with pytest.raises(RegraViolada, match="Dia da semana inválido"):
        validar_recorrencia(True, "semanal", 1, ["xyz"])


def test_descrever_recorrencia():
    assert descrever_recorrencia(False, "mensal", 1, []) is None
    assert descrever_recorrencia(True, None, None, []) == "Recorrente"
    assert descrever_recorrencia(True, "diaria", 1, []) == "Todo dia"
    assert descrever_recorrencia(True, "diaria", 2, []) == "A cada 2 dias"
    assert descrever_recorrencia(True, "semanal", 1, ["qua", "seg"]) == "Toda semana: seg, qua"
    assert descrever_recorrencia(True, "mensal", 2, []) == "A cada 2 meses"
    assert descrever_recorrencia(True, "mensal", 1, []) == "Todo mês"
    assert descrever_recorrencia(True, "semestral", 1, []) == "Semestral"
    assert descrever_recorrencia(True, "anual", 3, []) == "A cada 3 anos"


# ------------------------------------------------------------------------------------------------- campos
def test_campos_sugeridos():
    for objeto, itens in cs.CATALOGO.items():
        assert objeto in cs.OBJETOS and all(slug_de(s.nome) == s.chave for s in itens)
    nomes = [s.nome for s in cs.disponiveis("pessoa", {"cpf"})]
    assert "CPF" not in nomes and "LinkedIn" in nomes
    assert cs.obter("produto", "ncm", set()).nome == "NCM"
    with pytest.raises(RegraViolada, match="já existe"):
        cs.obter("produto", "ncm", {"ncm"})
    with pytest.raises(RegraViolada, match="Objeto inválido"):
        cs.disponiveis("titulo", set())


def test_campos_padrao_efetivos_e_alteracao():
    ef = {e.campo: e for e in cp.efetivos("empresa", {"segmento": cp.Config(True, True, 0),
                                                      "nome": cp.Config(False, False, 0)})}
    assert ef["nome"].fixo and ef["nome"].obrigatorio and ef["nome"].visivel  # fixo ignora configuração
    assert ef["segmento"].obrigatorio and not ef["porte"].obrigatorio
    with pytest.raises(RegraViolada, match="sempre obrigatório"):
        cp.validar_alteracao("pessoa", "nome", obrigatorio=False, visivel=True)
    with pytest.raises(RegraViolada, match="precisa ficar visível"):
        cp.validar_alteracao("empresa", "segmento", obrigatorio=True, visivel=False)
    with pytest.raises(RegraViolada, match="não encontrado"):
        cp.validar_alteracao("empresa", "inexistente", obrigatorio=False, visivel=True)


def test_campos_padrao_obrigatorios():
    campos = cp.efetivos("oportunidade", {"empresa_id": cp.Config(True, True), "origem": cp.Config(True, True)})
    with pytest.raises(RegraViolada, match="Empresa, Origem"):
        cp.validar_obrigatorios("oportunidade", campos, {"titulo": "x"}, criando=True)
    cp.validar_obrigatorios("oportunidade", campos, {"empresa_nome": "Nova", "origem": "Site"}, criando=True)
    # alterar: só confere o que veio
    cp.validar_obrigatorios("oportunidade", campos, {"titulo": "y"}, criando=False)
    with pytest.raises(RegraViolada, match="Origem"):
        cp.validar_obrigatorios("oportunidade", campos, {"origem": " "}, criando=False)
    pessoa = cp.efetivos("pessoa", {"email": cp.Config(True, True)})
    cp.validar_obrigatorios("pessoa", pessoa, {"emails": [{"email": "a@b.com"}]}, criando=True)
    with pytest.raises(RegraViolada, match="E-mail"):
        cp.validar_obrigatorios("pessoa", pessoa, {"emails": []}, criando=False)


def test_exibir_na_etapa():
    e2, e3, outra = EtapaRef(2, 1, 2), EtapaRef(3, 1, 3), EtapaRef(9, 5, 1)
    assert validar_exibicao(objeto="oportunidade", exibir_funil_id=None, exibir_etapa=None, exigido_etapa=e2) is None
    assert validar_exibicao(objeto="oportunidade", exibir_funil_id=None, exibir_etapa=e2, exigido_etapa=e3) == 1
    with pytest.raises(RegraViolada, match="anterior"):
        validar_exibicao(objeto="oportunidade", exibir_funil_id=1, exibir_etapa=e3, exigido_etapa=e2)
    with pytest.raises(RegraViolada, match="outro funil"):
        validar_exibicao(objeto="oportunidade", exibir_funil_id=1, exibir_etapa=None, exigido_etapa=outra)
    with pytest.raises(RegraViolada, match="não pertence"):
        validar_exibicao(objeto="oportunidade", exibir_funil_id=5, exibir_etapa=e2, exigido_etapa=None)
    with pytest.raises(RegraViolada, match="Só campos de oportunidade"):
        validar_exibicao(objeto="empresa", exibir_funil_id=1, exibir_etapa=None, exigido_etapa=None)
    assert visivel_na_oportunidade(exibir_funil_id=None, exibir_etapa_ordem=None, funil_id=7, etapa_ordem=1)
    assert not visivel_na_oportunidade(exibir_funil_id=1, exibir_etapa_ordem=None, funil_id=2, etapa_ordem=5)
    assert visivel_na_oportunidade(exibir_funil_id=1, exibir_etapa_ordem=None, funil_id=1, etapa_ordem=1)
    assert not visivel_na_oportunidade(exibir_funil_id=1, exibir_etapa_ordem=3, funil_id=1, etapa_ordem=2)
    assert visivel_na_oportunidade(exibir_funil_id=1, exibir_etapa_ordem=3, funil_id=1, etapa_ordem=3)


# ------------------------------------------------------------------------------------------------- listas e modelos
def test_listas():
    assert listas.validar_nome_opcao("porte", "  Médio  ", ["ME"]) == "Médio"
    with pytest.raises(RegraViolada, match="Já existe"):
        listas.validar_nome_opcao("segmento", "consultória", ["Consultoria"])
    with pytest.raises(RegraViolada, match="Informe o nome"):
        listas.validar_nome_opcao("motivo_perda", " ", [])
    with pytest.raises(RegraViolada, match="Lista inválida"):
        listas.validar_tipo("cor")
    assert listas.validar_reordenacao([1, 2, 3], [3, 1, 2]) == [3, 1, 2]
    for ids in ([1, 2], [1, 2, 2], [1, 2, 4]):
        with pytest.raises(RegraViolada):
            listas.validar_reordenacao([1, 2, 3], ids)
    ini = listas.iniciais("segmento", ["Logística", "consultoria", None, "x" * 200])
    assert ini[0] == "Consultoria" and "Logística" in ini and len([i for i in ini if i.lower() == "consultoria"]) == 1
    assert listas.iniciais("porte", []) == ["ME", "EPP", "Médio", "Grande"]


def test_classificacao_modelos():
    assert classificacoes_do_filtro() == ("comercial", "financeiro", "geral")
    assert classificacoes_do_filtro(contexto="financeiro") == ("financeiro", "geral")
    assert classificacoes_do_filtro("geral,comercial") == ("comercial", "geral")
    assert classificacoes_do_filtro(["financeiro", "geral"]) == ("financeiro", "geral")
    with pytest.raises(RegraViolada, match="Classificação inválida"):
        classificacoes_do_filtro("vendas")
    with pytest.raises(RegraViolada, match="Contexto inválido"):
        classificacoes_do_filtro(contexto="rh")


# ------------------------------------------------------------------------------------------------- outros
def test_assinatura_padrao_com_imagem_da_identidade():
    a = ass.escolher(texto_usuario=None, tem_imagem_usuario=False, texto_identidade=None, tem_imagem_identidade=True)
    assert (a.origem, a.com_imagem, a.texto) == ("identidade", True, None)
    a = ass.escolher(texto_usuario="Marina", tem_imagem_usuario=False, texto_identidade="Equipe",
                     tem_imagem_identidade=True)
    assert (a.origem, a.com_imagem) == ("usuario", False)


def test_lista_branca_sem_email_financeiro_e_produto_com_recorrencia():
    assert "email_financeiro" not in enr.lista_branca("empresa")
    assert "email_financeiro" not in enr.lista_branca("fornecedor")
    produto = enr.lista_branca("produto")
    assert {"frequencia", "intervalo", "dias_semana"} <= produto.keys()
    assert not {"desconto_tipo", "desconto_valor"} & produto.keys()  # a IA não sugere desconto
    assert enr.OBJETO_CUSTOM["produto"] == "produto"
