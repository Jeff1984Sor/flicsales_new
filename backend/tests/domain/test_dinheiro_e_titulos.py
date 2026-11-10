from datetime import date
from decimal import Decimal as D

import pytest

from app.domain import RegraViolada
from app.domain import titulos as t
from app.domain.dinheiro import arredondar, dinheiro, dividir_em_parcelas, formatar_brl, somar_meses

HOJE = date(2026, 11, 10)


# ---------------------------------------------------------------- dinheiro
def test_arredondamento_half_up():
    assert arredondar(D("0.005")) == D("0.01")
    assert arredondar(D("2.675")) == D("2.68")
    assert dinheiro("1234,5") == D("1234.50")


def test_float_e_recusado():
    with pytest.raises(TypeError):
        dinheiro(0.1)


@pytest.mark.parametrize("total,n,esperado", [
    ("100.00", 3, ["33.33", "33.33", "33.34"]),
    ("10.00", 3, ["3.33", "3.33", "3.34"]),
    ("24000", 2, ["12000.00", "12000.00"]),
    ("0.05", 2, ["0.03", "0.02"]),
    ("8500", 1, ["8500.00"]),
])
def test_parcelas_somam_o_total_e_a_ultima_absorve(total, n, esperado):
    p = dividir_em_parcelas(total, n)
    assert p == [D(x) for x in esperado]
    assert sum(p) == dinheiro(total)


@pytest.mark.parametrize("total", ["0.01", "1.00", "999.99", "123456.78", "7"])
@pytest.mark.parametrize("n", [1, 2, 3, 6, 7, 12])
def test_soma_das_parcelas_sempre_igual_ao_total(total, n):
    if dinheiro(total) < D("0.01") * n:
        with pytest.raises(RegraViolada):
            dividir_em_parcelas(total, n)
        return
    assert sum(dividir_em_parcelas(total, n)) == dinheiro(total)


def test_parcelas_invalidas():
    for total, n in (("0", 1), ("-5", 2), ("100", 0), ("0.02", 3)):
        with pytest.raises(RegraViolada):
            dividir_em_parcelas(total, n)


def test_somar_meses_fim_de_mes():
    assert somar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert somar_meses(date(2026, 11, 20), 2) == date(2027, 1, 20)


def test_formatar_brl():
    assert formatar_brl(D("37100")) == "R$ 37.100,00"
    assert formatar_brl(D("-1234.5")) == "-R$ 1.234,50"


# ---------------------------------------------------------------- status
def test_status_derivado_vencido():
    assert t.status_exibido("aberto", date(2026, 11, 9), HOJE) == "vencido"
    assert t.status_exibido("parcial", date(2026, 11, 9), HOJE) == "vencido"
    assert t.status_exibido("aberto", HOJE, HOJE) == "aberto"  # vence hoje: ainda não venceu
    for s in ("rascunho", "liquidado", "cancelado"):
        assert t.status_exibido(s, date(2026, 1, 1), HOJE) == s
    assert t.dias_em_atraso("aberto", date(2026, 11, 5), HOJE) == 5


def test_saldo_e_status_por_saldo():
    baixas = [t.BaixaInfo(D("100")), t.BaixaInfo(D("50"), estornada=True)]
    assert t.saldo_aberto(D("300"), baixas) == D("200.00")
    assert t.status_por_saldo("aberto", D("300"), D("200")) == "parcial"
    assert t.status_por_saldo("parcial", D("300"), D("0")) == "liquidado"
    assert t.status_por_saldo("parcial", D("300"), D("300")) == "aberto"
    assert t.status_por_saldo("rascunho", D("300"), D("0")) == "rascunho"


def test_confirmar_so_rascunho():
    assert t.validar_confirmacao("rascunho") == "aberto"
    with pytest.raises(RegraViolada, match="rascunho"):
        t.validar_confirmacao("aberto")


# ---------------------------------------------------------------- baixa
def _baixa(**kw):
    base = dict(direcao="receber", status="aberto", aprovacao=None, saldo=D("6000"), valor=D("1000"), data=HOJE,
                data_base_conta=date(2026, 10, 1), hoje=HOJE)
    return t.validar_baixa(**{**base, **kw})


def test_baixa_valida_e_limites_de_valor():
    assert _baixa() == D("1000.00")
    assert _baixa(valor=D("6000")) == D("6000.00")  # igual ao saldo
    for v in (D("0"), D("-1"), D("6000.01")):  # zero, negativo, um centavo acima
        with pytest.raises(RegraViolada, match="não superar o saldo"):
            _baixa(valor=v)


def test_baixa_limites_de_data():
    assert _baixa(data=date(2026, 10, 1)) == D("1000.00")  # na data-base
    with pytest.raises(RegraViolada, match="data-base da conta e hoje"):
        _baixa(data=date(2026, 9, 30))
    with pytest.raises(RegraViolada, match="data-base da conta e hoje"):
        _baixa(data=date(2026, 11, 11))  # amanhã


def test_baixa_exige_conta_confirmacao_e_aprovacao():
    with pytest.raises(RegraViolada, match="conta cadastrada"):
        _baixa(data_base_conta=None)
    with pytest.raises(RegraViolada, match="Confirme"):
        _baixa(status="rascunho")
    with pytest.raises(RegraViolada, match="cancelado"):
        _baixa(status="cancelado")
    with pytest.raises(RegraViolada, match="Aprove o pagamento"):
        _baixa(direcao="pagar", aprovacao="pendente")
    assert _baixa(direcao="pagar", aprovacao="aprovado") == D("1000.00")
    assert t.exige_aprovacao("pagar") and not t.exige_aprovacao("receber")
    assert t.aprovacao_inicial("pagar") == "pendente" and t.aprovacao_inicial("receber") is None


def test_aplicar_baixa_parcial_total_e_estorno():
    saldo, st = t.aplicar_baixa(valor_original=D("6000"), saldo=D("6000"), status="aberto", valor=D("2500"))
    assert (saldo, st) == (D("3500.00"), "parcial")
    saldo, st = t.aplicar_baixa(valor_original=D("6000"), saldo=saldo, status=st, valor=D("3500"))
    assert (saldo, st) == (D("0.00"), "liquidado")
    saldo, st = t.aplicar_estorno(valor_original=D("6000"), saldo=saldo, status=st, valor_baixa=D("3500"),
                                  ja_estornada=False, motivo="Valor lançado na conta errada")
    assert (saldo, st) == (D("3500.00"), "parcial")


def test_estorno_exige_motivo_e_nao_repete():
    kw = dict(valor_original=D("100"), saldo=D("0"), status="liquidado", valor_baixa=D("100"))
    with pytest.raises(RegraViolada, match="motivo do estorno"):
        t.aplicar_estorno(**kw, ja_estornada=False, motivo="  ")
    with pytest.raises(RegraViolada, match="já foi estornada"):
        t.aplicar_estorno(**kw, ja_estornada=True, motivo="x")
    with pytest.raises(RegraViolada, match="acima do valor original"):
        t.aplicar_estorno(valor_original=D("100"), saldo=D("50"), status="parcial", valor_baixa=D("60"),
                          ja_estornada=False, motivo="x")


# ---------------------------------------------------------------- edição e cancelamento
def test_editar_valor_so_sem_baixa_ativa():
    with pytest.raises(RegraViolada, match="Estorne as baixas antes de editar o título"):
        t.validar_edicao_valor(tem_baixa_ativa=True, status="parcial", novo_valor=D("10"))
    assert t.validar_edicao_valor(tem_baixa_ativa=False, status="aberto", novo_valor="10") == D("10.00")
    with pytest.raises(RegraViolada, match="O valor deve ser positivo"):
        t.validar_edicao_valor(tem_baixa_ativa=False, status="aberto", novo_valor="0")
    assert t.pode_editar_valor(False) and not t.pode_editar_valor(True)
    assert t.tem_baixa_ativa([t.BaixaInfo(D("1"), estornada=True)]) is False


def test_cancelar_exige_motivo_e_sem_baixa():
    with pytest.raises(RegraViolada, match="Estorne as baixas antes de cancelar"):
        t.validar_cancelamento(status="parcial", tem_baixa_ativa=True, motivo="x")
    with pytest.raises(RegraViolada, match="motivo do cancelamento"):
        t.validar_cancelamento(status="aberto", tem_baixa_ativa=False, motivo="")
    with pytest.raises(RegraViolada, match="já está cancelado"):
        t.validar_cancelamento(status="cancelado", tem_baixa_ativa=False, motivo="x")
    assert t.validar_cancelamento(status="rascunho", tem_baixa_ativa=False, motivo="Duplicado") == "cancelado"
    assert t.pode_cancelar("aberto", False) and not t.pode_cancelar("aberto", True)


def test_aprovacao_de_pagamento():
    assert t.validar_aprovacao("pagar", "aberto", "pendente") == "aprovado"
    with pytest.raises(RegraViolada):
        t.validar_aprovacao("receber", "aberto", None)
    with pytest.raises(RegraViolada, match="já está aprovado"):
        t.validar_aprovacao("pagar", "aberto", "aprovado")
