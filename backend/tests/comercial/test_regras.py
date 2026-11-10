"""Regras puras do Comercial (app/modules/comercial/regras.py)."""

from datetime import date

import pytest

from app.domain import RegraViolada
from app.modules.comercial import regras


def test_probabilidades_padrao():
    assert regras.probabilidades_padrao(4) == [20, 40, 60, 80]
    assert regras.probabilidades_padrao(5) == [16, 32, 48, 64, 80]


def test_tipo_evento_fechado():
    assert regras.validar_tipo_evento("ganha") == "ganha"
    with pytest.raises(ValueError):
        regras.validar_tipo_evento("qualquer")


def test_periodo():
    regras.validar_periodo(date(2026, 1, 1), date(2026, 1, 1))
    with pytest.raises(RegraViolada, match="A data final deve ser igual ou posterior ao início"):
        regras.validar_periodo(date(2026, 1, 2), date(2026, 1, 1))


def test_renderizar_modelo():
    texto, faltando = regras.renderizar_modelo("Olá {{ contato.nome }}, {{empresa.nome}} — {{titulo.valor}}",
                                               {"contato.nome": "Paula", "empresa.nome": "Aurora"})
    assert texto == "Olá Paula, Aurora — {{titulo.valor}}"
    assert faltando == ["titulo.valor"]
    assert regras.variaveis_do_texto("{{a.b}} {{a.b}} {{c}}") == ["a.b", "c"]


def test_validar_analise_normaliza_citacoes():
    a = regras.validar_analise({"necessidades": [" X "], "citacoes": ["trecho", {"trecho": "y", "fonte": "f"}]})
    assert a["necessidades"] == ["X"] and a["objecoes"] == []
    assert a["citacoes"] == [{"trecho": "trecho", "fonte": None}, {"trecho": "y", "fonte": "f"}]
    with pytest.raises(RegraViolada):
        regras.validar_analise({"objecoes": "não é lista"})


def test_rascunho_resposta():
    r = regras.rascunho_resposta(contato="Paula Mendes", analise={"compromissos": ["Enviar detalhamento até 09/11"]})
    assert r.startswith("Olá, Paula!") and "Enviar detalhamento até 09/11" in r
    assert regras.rascunho_resposta(contato=None, analise=None).startswith("Olá!")


def test_gargalo_prioriza_proxima_acao():
    g, a = regras.gargalo_do_vendedor(sem_proxima_acao=2, atividades_atrasadas=1, alem_do_limite=0, encerradas=3)
    assert "próxima ação" in g and "Revisar semanalmente" in a
    g, _ = regras.gargalo_do_vendedor(sem_proxima_acao=0, atividades_atrasadas=0, alem_do_limite=0, encerradas=0)
    assert "amostra" in g


def test_meta_modelo_playbook():
    with pytest.raises(RegraViolada, match="equipe"):
        regras.validar_meta(nome="M", responsavel_tipo="equipe", responsavel_id=None, equipe=" ",
                            inicio=date(2026, 1, 1), fim=date(2026, 1, 31), indicador="mrr_novo", alvo=1)
    with pytest.raises(RegraViolada, match="conteúdo"):
        regras.validar_modelo(nome="M", canal="email", finalidade="proposta", conteudo="", status="rascunho")
    with pytest.raises(RegraViolada, match="objetivo"):
        regras.validar_playbook(nome="P", objetivo=None, criterios_avanco="x")
