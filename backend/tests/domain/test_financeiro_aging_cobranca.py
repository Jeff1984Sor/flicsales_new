"""Regras financeiras acrescentadas pelo módulo Financeiro: aging, próxima competência (worker) e cobrança."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain import RegraViolada
from app.domain.cobranca import cobranca_suspensa, validar_cobranca
from app.domain.recorrencia import proximas_competencias
from app.domain.titulos import TituloAging, aging, faixa_aging

HOJE = date(2026, 11, 10)
D = Decimal


@pytest.mark.parametrize(("venc", "faixa"), [
    (date(2026, 11, 10), "a_vencer"),  # vence hoje: ainda não está vencido
    (date(2026, 12, 1), "a_vencer"),
    (date(2026, 11, 9), "1_30"),
    (date(2026, 10, 11), "1_30"),  # 30 dias
    (date(2026, 10, 10), "31_60"),  # 31 dias
    (date(2026, 9, 11), "31_60"),  # 60
    (date(2026, 9, 10), "61_90"),  # 61
    (date(2026, 8, 12), "61_90"),  # 90
    (date(2026, 8, 11), "90_mais"),  # 91
])
def test_faixa_aging_limites(venc, faixa):
    assert faixa_aging(venc, HOJE) == faixa


def test_aging_soma_saldo_aberto_e_ignora_rascunho_cancelado_liquidado_e_pagar():
    titulos = [
        TituloAging("receber", "aberto", date(2026, 11, 3), D("6000")),  # 7 dias
        TituloAging("receber", "parcial", date(2026, 11, 20), D("2500")),
        TituloAging("receber", "aberto", date(2026, 7, 1), D("100")),  # 90+
        TituloAging("receber", "rascunho", date(2026, 10, 1), D("999")),
        TituloAging("receber", "cancelado", date(2026, 10, 1), D("999")),
        TituloAging("receber", "liquidado", date(2026, 10, 1), D("0")),
        TituloAging("pagar", "aberto", date(2026, 10, 1), D("4200")),
    ]
    r = {f.faixa: (f.valor, f.quantidade) for f in aging(titulos, HOJE)}
    assert r == {"a_vencer": (D("2500.00"), 1), "1_30": (D("6000.00"), 1), "31_60": (D("0.00"), 0),
                 "61_90": (D("0.00"), 0), "90_mais": (D("100.00"), 1)}
    pagar = {f.faixa: f.valor for f in aging(titulos, HOJE, "pagar")}
    assert pagar["31_60"] == D("4200.00")


def test_proximas_competencias_ate_30_dias_sem_passado_e_sem_duplicar():
    kw = dict(situacao="ativa", inicio=date(2026, 9, 1), fim=date(2027, 8, 31), frequencia="mensal",
              dia_vencimento=12, hoje=HOJE)
    assert proximas_competencias(**kw, existentes=set()) == ["2026-11"]  # set/out ficam para a tela; dez/12 > 30 dias
    assert proximas_competencias(**kw, existentes={"2026-11"}) == []
    kw["dia_vencimento"] = 5  # nov/05 já passou; dez/05 está a 25 dias
    assert proximas_competencias(**kw, existentes=set()) == ["2026-12"]


def test_proximas_competencias_respeita_frequencia_vigencia_e_situacao():
    base = dict(inicio=date(2026, 9, 1), fim=date(2027, 8, 31), dia_vencimento=12, hoje=HOJE, existentes=set())
    assert proximas_competencias(situacao="ativa", frequencia="trimestral", **base) == []  # set, dez…: dez/12 > 30d
    assert proximas_competencias(situacao="pausada", frequencia="mensal", **base) == []
    fim_curto = dict(base, fim=date(2026, 10, 31))
    assert proximas_competencias(situacao="ativa", frequencia="mensal", **fim_curto) == []


def _cob(**kw):
    args = dict(titulo_direcao="receber", titulo_status="aberto", titulo_saldo=D("6000"), situacao="em_acompanhamento",
                canal="email", data_prometida=None, valor_prometido=None, historico="Contato feito.")
    args.update(kw)
    return validar_cobranca(**args)


def test_cobranca_valida():
    assert _cob() is None
    assert _cob(situacao="promessa_pagamento", data_prometida=date(2026, 11, 20), valor_prometido="6000") == D("6000.00")


@pytest.mark.parametrize(("kw", "msg"), [
    ({"titulo_direcao": "pagar"}, "título a receber"),
    ({"titulo_status": "rascunho"}, "saldo em aberto"),
    ({"titulo_status": "liquidado"}, "saldo em aberto"),
    ({"situacao": "xx"}, "Situação"),
    ({"canal": "fax"}, "Canal"),
    ({"historico": "  "}, "histórico"),
    ({"situacao": "promessa_pagamento"}, "data prometida"),
    ({"valor_prometido": "0"}, "positivo"),
    ({"valor_prometido": "6000.01"}, "não superar"),
])
def test_cobranca_recusa(kw, msg):
    with pytest.raises(RegraViolada, match=msg):
        _cob(**kw)


def test_edicao_de_cobranca_permite_titulo_ja_liquidado():
    assert _cob(titulo_status="liquidado", situacao="resolvida", nova=False) is None


def test_contestacao_suspende_cobranca():
    assert cobranca_suspensa(titulo_status="aberto", situacoes=["em_contestacao"])
    assert cobranca_suspensa(titulo_status="liquidado", situacoes=[])
    assert cobranca_suspensa(titulo_status="cancelado", situacoes=[])
    assert not cobranca_suspensa(titulo_status="parcial", situacoes=["promessa_pagamento", "resolvida"])
