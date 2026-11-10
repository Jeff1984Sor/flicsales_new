from datetime import date
from decimal import Decimal as D

import pytest

from app.domain import RegraViolada
from app.domain import caixa as cx
from app.domain import recorrencia as rec
from app.domain.fechamento import CONDICOES, parcelas_do_fechamento, validar_ganho

HOJE = date(2026, 11, 10)


# ---------------------------------------------------------------- fechamento
def _fechar(**kw):
    base = dict(oportunidade_id=7, titulo="Projeto de consultoria", empresa_id=3, valor=D("24000"),
                condicao="2 parcelas iguais", primeiro_vencimento=date(2026, 11, 20))
    return parcelas_do_fechamento(**{**base, **kw})


def test_ganho_gera_rascunhos_mensais():
    p = _fechar()
    assert [(x.parcela, x.parcelas_total, x.valor, x.vencimento, x.status, x.direcao) for x in p] == [
        (1, 2, D("12000.00"), date(2026, 11, 20), "rascunho", "receber"),
        (2, 2, D("12000.00"), date(2026, 12, 20), "rascunho", "receber"),
    ]
    assert p[0].descricao == "Projeto de consultoria • 1/2"


def test_fechamento_idempotente_por_parcela():
    assert _fechar(existentes={1, 2}) == []
    faltando = _fechar(existentes={1})
    assert [x.parcela for x in faltando] == [2]


def test_fechamento_centavos_na_ultima():
    p = _fechar(valor=D("1000"), condicao=3)
    assert [x.valor for x in p] == [D("333.33"), D("333.33"), D("333.34")] and sum(x.valor for x in p) == D("1000")


def test_fechamento_validacoes():
    with pytest.raises(RegraViolada, match="empresa"):
        _fechar(empresa_id=None)
    with pytest.raises(RegraViolada, match="valor acordado"):
        _fechar(valor=D("0"))
    with pytest.raises(RegraViolada, match="primeiro vencimento"):
        _fechar(primeiro_vencimento=None)
    with pytest.raises(RegraViolada, match="Condição"):
        _fechar(condicao="à vista com bônus")
    with pytest.raises(RegraViolada, match="Esta venda já foi processada"):
        validar_ganho("ganha")
    with pytest.raises(RegraViolada):
        validar_ganho("perdida")
    validar_ganho("aberta")
    assert CONDICOES["Parcela única"] == 1


# ---------------------------------------------------------------- caixa
def test_projecao_do_prototipo_37100():
    contas = [cx.Conta(1, D("25000"), date(2026, 10, 1))]
    saldo = cx.saldo_gerencial(contas, [], [])
    titulos = [
        cx.TituloAberto("receber", "aberto", D("6000")),   # Ponto Norte (vencido continua aberto)
        cx.TituloAberto("receber", "aberto", D("4800")),   # Estúdio Base
        cx.TituloAberto("receber", "aberto", D("8500")),   # Lume Serviços
        cx.TituloAberto("pagar", "aberto", D("4200")),     # Espaço Compartilhado
        cx.TituloAberto("pagar", "aberto", D("3000")),     # Nuvem Digital
        cx.TituloAberto("receber", "rascunho", D("99999")),  # rascunho não entra
        cx.TituloAberto("pagar", "cancelado", D("88888")),   # cancelado não entra
        cx.TituloAberto("receber", "liquidado", D("0")),
    ]
    p = cx.projecao(saldo, titulos)
    assert (p.saldo_atual, p.entradas_abertas, p.saidas_abertas, p.saldo_projetado) == (
        D("25000.00"), D("19300.00"), D("7200.00"), D("37100.00"))


def test_saldo_por_conta_com_baixas_estorno_e_transferencias():
    contas = [cx.Conta(1, D("25000"), date(2026, 10, 1)), cx.Conta(2, D("-500"), date(2026, 10, 1))]
    movs = [cx.Movimento(1, "receber", D("2500")), cx.Movimento(1, "pagar", D("3000")),
            cx.Movimento(1, "receber", D("999"), estornada=True)]
    transf = [cx.TransferenciaInfo(1, 2, D("1000"))]
    assert cx.saldo_por_conta(contas, movs, transf) == {1: D("23500.00"), 2: D("500.00")}
    # transferência não é receita nem despesa: o total só muda pelas baixas
    assert cx.saldo_gerencial(contas, movs, transf) == D("24000.00")


def test_projecao_usa_saldo_aberto_do_parcial():
    p = cx.projecao(D("100"), [cx.TituloAberto("receber", "parcial", D("40"))])
    assert p.saldo_projetado == D("140.00")


def test_transferencia_validacoes():
    a, b = cx.Conta(1, D("0"), date(2026, 10, 1)), cx.Conta(2, D("0"), date(2026, 11, 1))
    assert cx.validar_transferencia(origem=a, destino=b, valor="10", data=date(2026, 11, 1), hoje=HOJE) == D("10.00")
    for origem, destino, valor in ((a, a, "10"), (a, b, "0"), (a, None, "10"), (a, b, "-1")):
        with pytest.raises(RegraViolada, match="contas diferentes e valor positivo"):
            cx.validar_transferencia(origem=origem, destino=destino, valor=valor, data=HOJE, hoje=HOJE)
    with pytest.raises(RegraViolada, match="datas-base"):
        cx.validar_transferencia(origem=a, destino=b, valor="10", data=date(2026, 10, 15), hoje=HOJE)
    with pytest.raises(RegraViolada, match="datas-base"):
        cx.validar_transferencia(origem=a, destino=b, valor="10", data=date(2026, 11, 11), hoje=HOJE)


def test_conta_com_movimento_preserva_saldo_inicial():
    cx.validar_edicao_conta(tem_movimento=False, muda_saldo_inicial=True, muda_data_base=True)
    cx.validar_edicao_conta(tem_movimento=True, muda_saldo_inicial=False, muda_data_base=False)
    with pytest.raises(RegraViolada, match="preserve saldo inicial"):
        cx.validar_edicao_conta(tem_movimento=True, muda_saldo_inicial=True, muda_data_base=False)


# ---------------------------------------------------------------- recorrência
VIG = dict(inicio=date(2026, 9, 12), fim=date(2027, 8, 12))


def test_recorrencia_cadastro():
    assert rec.validar_recorrencia(valor_ciclo="4800", dia_vencimento=12, frequencia="mensal", **VIG) == D("4800.00")
    for valor, dia in (("0", 12), ("4800", 0), ("4800", 29), ("-1", 5)):
        with pytest.raises(RegraViolada, match="dia inteiro entre 1 e 28"):
            rec.validar_recorrencia(valor_ciclo=valor, dia_vencimento=dia, frequencia="mensal", **VIG)
    with pytest.raises(RegraViolada, match="posterior ao início"):
        rec.validar_recorrencia(valor_ciclo="1", dia_vencimento=1, frequencia="mensal", inicio=date(2026, 2, 1),
                                fim=date(2026, 1, 1))


def test_competencia_mensal_vigencia_e_duplicidade():
    t = rec.titulo_da_competencia(recorrencia_id=1, situacao="ativa", frequencia="mensal", dia_vencimento=12,
                                  valor_ciclo="4800", competencia="2026-11", existentes={"2026-09", "2026-10"}, **VIG)
    assert (t.competencia, t.vencimento, t.valor, t.status) == ("2026-11", date(2026, 11, 12), D("4800.00"), "rascunho")
    kw = dict(situacao="ativa", frequencia="mensal", existentes={"2026-11"}, **VIG)
    with pytest.raises(RegraViolada, match="Título desta competência já existe"):
        rec.validar_competencia(competencia="2026-11", **kw)
    for fora in ("2026-08", "2027-09"):
        with pytest.raises(RegraViolada, match="Competência fora da vigência"):
            rec.validar_competencia(competencia=fora, **kw)
    rec.validar_competencia(competencia="2026-09", **kw)  # mês do início
    rec.validar_competencia(competencia="2027-08", **kw)  # mês do fim
    with pytest.raises(RegraViolada, match="AAAA-MM"):
        rec.validar_competencia(competencia="11/2026", **kw)
    with pytest.raises(RegraViolada, match="deve estar ativa"):
        rec.validar_competencia(competencia="2026-12", **{**kw, "situacao": "pausada"})


def test_competencia_trimestral_desalinhada():
    kw = dict(situacao="ativa", frequencia="trimestral", existentes=set(), **VIG)
    rec.validar_competencia(competencia="2026-12", **kw)
    rec.validar_competencia(competencia="2027-03", **kw)
    for desalinhada in ("2026-10", "2026-11", "2027-01"):
        with pytest.raises(RegraViolada, match="incompatível com a frequência"):
            rec.validar_competencia(competencia=desalinhada, **kw)
    with pytest.raises(RegraViolada, match="incompatível com a frequência"):
        rec.validar_competencia(competencia="2027-08", **{**kw, "frequencia": "anual"})


def test_competencias_a_gerar_para_o_worker():
    assert rec.competencias_a_gerar(situacao="ativa", frequencia="mensal", ate=date(2026, 12, 1),
                                    existentes={"2026-10"}, **VIG) == ["2026-09", "2026-11", "2026-12"]
    assert rec.competencias_a_gerar(situacao="ativa", frequencia="trimestral", ate=date(2027, 12, 31),
                                    existentes=set(), **VIG) == ["2026-09", "2026-12", "2027-03", "2027-06"]
    assert rec.competencias_a_gerar(situacao="pausada", frequencia="mensal", ate=date(2027, 1, 1),
                                    existentes=set(), **VIG) == []
