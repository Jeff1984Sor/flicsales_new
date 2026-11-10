"""Regras puras do Núcleo: valores de campos personalizados e detecção de duplicidade."""

import pytest

from app.domain import RegraViolada
from app.modules.nucleo.regras import (
    DefCampo,
    EmpresaComparavel,
    encontrar_duplicidades,
    nome_comparavel,
    slug_de,
    validar_campos_custom,
    validar_definicao_campo,
)

ORIGEM = DefCampo(slug="origem", nome="Origem", tipo="lista", opcoes=("Site", "Evento"))
DEFS = [
    ORIGEM,
    DefCampo(slug="colab", nome="Colaboradores", tipo="numero"),
    DefCampo(slug="limite", nome="Limite", tipo="moeda"),
    DefCampo(slug="desde", nome="Cliente desde", tipo="data"),
    DefCampo(slug="vip", nome="VIP", tipo="sim_nao"),
    DefCampo(slug="nota", nome="Nota", tipo="texto"),
    DefCampo(slug="velho", nome="Velho", tipo="texto", arquivado=True),
]


def test_slug():
    assert slug_de("Origem do lead") == "origem_do_lead"
    assert slug_de("  Ação / Prioridade! ") == "acao_prioridade"


def test_definicao_lista_exige_opcao_e_limpa_repetidas():
    with pytest.raises(RegraViolada, match="ao menos uma opção"):
        validar_definicao_campo(nome="X", tipo="lista", objeto="empresa", opcoes=["", " "])
    assert validar_definicao_campo(nome="X", tipo="lista", objeto="empresa", opcoes=["A", "A", " B "]) == ["A", "B"]
    assert validar_definicao_campo(nome="X", tipo="texto", objeto="pessoa", opcoes=["A"]) == []
    with pytest.raises(RegraViolada, match="Objeto inválido"):
        validar_definicao_campo(nome="X", tipo="texto", objeto="titulo", opcoes=None)


def test_valores_convertidos_por_tipo():
    r = validar_campos_custom(DEFS, {"origem": "Site", "colab": "12", "limite": "1500,5", "desde": "2026-01-05",
                                     "vip": "sim", "nota": "  boa  "})
    assert r == {"origem": "Site", "colab": 12, "limite": "1500.50", "desde": "2026-01-05", "vip": True,
                 "nota": "boa"}


@pytest.mark.parametrize("chave,valor,msg", [
    ("origem", "Rádio", "escolha uma das opções"),
    ("colab", "muitos", "informe um número"),
    ("desde", "05/01/2026", "AAAA-MM-DD"),
    ("vip", "talvez", "sim ou não"),
    ("inexistente", "x", "desconhecido"),
    ("velho", "x", "desconhecido"),
])
def test_valores_invalidos(chave, valor, msg):
    with pytest.raises(RegraViolada, match=msg):
        validar_campos_custom(DEFS, {chave: valor})


def test_merge_preserva_atuais_apaga_com_none_e_mantem_arquivado():
    atuais = {"origem": "Site", "velho": "guardado", "nota": "x"}
    r = validar_campos_custom(DEFS, {"nota": None, "colab": 3}, atuais)
    assert r == {"origem": "Site", "velho": "guardado", "colab": 3}


def test_obrigatorio():
    defs = [DefCampo(slug="seg", nome="Segmento", tipo="texto", obrigatorio=True)]
    with pytest.raises(RegraViolada, match="obrigatório: Segmento"):
        validar_campos_custom(defs, {})
    assert validar_campos_custom(defs, {}, exigir_obrigatorios=False) == {}
    assert validar_campos_custom(defs, {"seg": "Saúde"}) == {"seg": "Saúde"}


def test_nome_comparavel_tira_sufixos_e_pontuacao():
    assert nome_comparavel("Aurora Consultoria LTDA.") == "aurora consultoria"
    assert nome_comparavel("Vértice Serviços S/A") == "vertice servicos"
    assert nome_comparavel("Lume & Cia") == "lume"


def test_duplicidades():
    pares = encontrar_duplicidades([
        EmpresaComparavel(1, "Aurora Consultoria"),
        EmpresaComparavel(2, "Aurora Consultoria Ltda"),
        EmpresaComparavel(3, "Atlas Tecnologia", "12.345.678/0001-90"),
        EmpresaComparavel(4, "Atlas Tec", "12345678000190"),
        EmpresaComparavel(5, "Horizonte Gestão"),
        EmpresaComparavel(6, "Horizonte Gestao e"),
        EmpresaComparavel(7, "Nuvem Digital"),
    ])
    por_par = {(p.a, p.b): p.motivo for p in pares}
    assert por_par[(1, 2)] == "Mesmo nome sem sufixos e pontuação"
    assert por_par[(3, 4)] == "Mesmo documento (CPF/CNPJ)"
    assert por_par[(5, 6)] == "Nomes muito parecidos"
    assert not any(7 in par for par in por_par)
