"""Regras puras da proposta automatizada + documento (app.domain.modelo_proposta)."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain import RegraViolada
from app.domain import modelo_proposta as dom
from app.modules.comercial import regras

HOJE = date(2026, 11, 11)


# ------------------------------------------------------------------------------------------- modelo
def test_validar_modelo_ok_e_nome_limpo():
    assert dom.validar_modelo_proposta(nome="  Serviços  ", validade_dias=30, condicao_padrao="2 parcelas",
                                       outros_nomes=["Outro"]) == "Serviços"
    assert dom.validar_modelo_proposta(nome="X", validade_dias=1, condicao_padrao=None, outros_nomes=[]) == "X"
    assert dom.validar_modelo_proposta(nome="X", validade_dias=365, condicao_padrao="", outros_nomes=[]) == "X"


@pytest.mark.parametrize("kw, msg", [
    ({"nome": " "}, "Informe o nome do modelo de proposta."),
    ({"nome": "proposta PADRÃO"}, "Já existe um modelo de proposta chamado proposta PADRÃO. Escolha outro nome."),
    ({"validade_dias": 0}, "A validade da proposta deve ficar entre 1 e 365 dias."),
    ({"validade_dias": 366}, "A validade da proposta deve ficar entre 1 e 365 dias."),
    ({"validade_dias": None}, "A validade da proposta deve ficar entre 1 e 365 dias."),
    ({"condicao_padrao": "12x"}, "Condição de pagamento inválida."),
])
def test_validar_modelo_recusa(kw, msg):
    base = {"nome": "Novo", "validade_dias": 15, "condicao_padrao": "À vista", "outros_nomes": ["Proposta padrão"]}
    with pytest.raises(RegraViolada) as e:
        dom.validar_modelo_proposta(**{**base, **kw})
    assert str(e.value).startswith(msg)


def test_condicoes_iguais_as_da_proposta():
    assert dom.CONDICOES == regras.CONDICOES_PROPOSTA


def test_padrao_nao_inativa_e_nao_desmarca():
    dom.conferir_padrao_e_ativo(era_padrao=False, padrao=False, ativo=False)
    dom.conferir_padrao_e_ativo(era_padrao=False, padrao=True, ativo=True)
    dom.conferir_padrao_e_ativo(era_padrao=True, padrao=True, ativo=True)
    with pytest.raises(RegraViolada, match="não pode ser inativado"):
        dom.conferir_padrao_e_ativo(era_padrao=True, padrao=True, ativo=False)
    with pytest.raises(RegraViolada, match="não pode ser inativado"):
        dom.conferir_padrao_e_ativo(era_padrao=False, padrao=True, ativo=False)
    with pytest.raises(RegraViolada, match="marque outro modelo como padrão"):
        dom.conferir_padrao_e_ativo(era_padrao=True, padrao=False, ativo=True)


def test_modelo_inicial_usa_so_variaveis_aceitas():
    for campo in ("introducao", "termos", "rodape"):
        assert set(regras.variaveis_do_texto(dom.MODELO_INICIAL[campo])) <= set(dom.VARIAVEIS)
    dom.validar_modelo_proposta(nome=dom.MODELO_INICIAL["nome"], validade_dias=dom.MODELO_INICIAL["validade_dias"],
                                condicao_padrao=dom.MODELO_INICIAL["condicao_padrao"], outros_nomes=[])


# ------------------------------------------------------------------------------------------- proposta automática
def _auto(**kw):
    base = {"oportunidade_titulo": "Projeto X", "necessidade": None, "valor_unico": Decimal("1000"),
            "valor_recorrente_mensal": Decimal("0"), "produto": None, "validade_dias": 15, "condicao_padrao": None,
            "versoes": [], "hoje": HOJE}
    return dom.dados_proposta_automatica(**{**base, **kw})


def test_automatica_sem_produto_usa_valor_da_oportunidade():
    d = _auto(necessidade="Reduzir custo", versoes=[1, 2])
    assert d["titulo"] == "Proposta — Projeto X" and d["versao"] == 3
    assert d["preco_unitario"] == Decimal("1000.00") and d["total"] == Decimal("1000.00")
    assert d["quantidade"] == 1 and d["desconto_pct"] == 0 and d["status"] == "rascunho"
    assert d["validade"] == date(2026, 11, 26) and d["condicao"] == "À vista"
    assert d["escopo"] == "Projeto X\n\nNecessidade: Reduzir custo"


def test_automatica_com_produto_usa_preco_e_descricao():
    prod = dom.ProdutoBase("Consultoria", "Diagnóstico e plano.", Decimal("24000"))
    d = _auto(produto=prod, valor_recorrente_mensal=Decimal("500"), condicao_padrao="2 parcelas", validade_dias=30)
    assert d["preco_unitario"] == Decimal("24000.00") and d["total"] == Decimal("24000.00")
    assert d["escopo"] == "Consultoria\n\nDiagnóstico e plano." and d["condicao"] == "2 parcelas"
    assert d["mensalidade_adicional"] == Decimal("500.00") and d["validade"] == date(2026, 12, 11)


def test_automatica_produto_sem_preco_e_produto_recorrente():
    d = _auto(produto=dom.ProdutoBase("Suporte", None, None))
    assert d["preco_unitario"] == Decimal("1000.00") and d["escopo"] == "Suporte"
    d = _auto(produto=dom.ProdutoBase("SaaS", None, Decimal("300"), recorrente=True),
              valor_recorrente_mensal=Decimal("300"))
    assert d["preco_unitario"] == Decimal("300.00") and d["mensalidade_adicional"] == 0  # não soma duas vezes


def test_automatica_validade_fora_da_faixa():
    with pytest.raises(RegraViolada, match="entre 1 e 365"):
        _auto(validade_dias=0)


def test_escopo_da_ia():
    assert dom.escopo_da_ia({"paragrafos": ["Um.", " ", "Dois."]}) == "Um.\n\nDois."
    assert dom.escopo_da_ia({"paragrafos": [str(i) for i in range(8)]}).count("\n\n") == 4  # máx. 5
    assert dom.escopo_da_ia({"escopo": "A\n\nB"}) == "A\n\nB"
    assert dom.escopo_da_ia({"paragrafos": []}) is None
    assert dom.escopo_da_ia({"outra": 1}) is None
    assert dom.escopo_da_ia(None) is None


# ------------------------------------------------------------------------------------------- documento
def test_valores_variaveis_formatados_e_renderizacao():
    v = dom.valores_variaveis(empresa_nome="Aurora", empresa_cnpj=None, contato_nome="Paula",
                              oportunidade_titulo="Projeto", proposta_titulo="Proposta — Projeto",
                              total=Decimal("24000"), validade=date(2026, 11, 26), condicao="À vista",
                              responsavel_nome="Marina", hoje=HOJE)
    assert set(v) == set(dom.VARIAVEIS)
    texto, faltando = regras.renderizar_modelo("{{empresa.nome}} {{proposta.total}} até {{proposta.validade}} "
                                               "em {{hoje}} {{empresa.cnpj}}", v)
    assert texto == "Aurora R$ 24.000,00 até 26/11/2026 em 11/11/2026 {{empresa.cnpj}}"
    assert faltando == ["empresa.cnpj"]


def test_faixa_rascunho():
    assert dom.mostra_faixa_rascunho("rascunho", 0)
    assert dom.mostra_faixa_rascunho("em_aprovacao", Decimal("5"))
    assert not dom.mostra_faixa_rascunho("em_aprovacao", 0)
    assert not dom.mostra_faixa_rascunho("enviada", Decimal("5"))
    assert not dom.mostra_faixa_rascunho("aprovada_internamente", Decimal("5"))


def test_nome_arquivo_e_linha():
    assert dom.nome_arquivo_pdf(7, 2) == "proposta-7-v2.pdf"
    linha = dom.linha_item(quantidade="2", preco_unitario="100", desconto_pct="10")
    assert linha["total"] == Decimal("180.00")
