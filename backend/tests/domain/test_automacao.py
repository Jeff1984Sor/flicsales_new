"""Automações: catálogo, validação e avaliação PURA dos gatilhos (app.domain.automacao)."""

from datetime import date, datetime, timedelta
from decimal import Decimal as D

import pytest

from app.domain import RegraViolada
from app.domain import automacao as a

HOJE = date(2026, 11, 10)  # terça-feira
ATIVADA = datetime(2026, 11, 9, 12, 0)


def _cfg(**kw):
    base = dict(area="comercial", nome="Teste", gatilho="oportunidade_ganha", acao="criar_atividade",
                conteudo="Revisar {{oportunidade.titulo}}")
    base.update(kw)
    return a.Configuracao(**base)


def _opp(id=1, **kw):
    base = dict(id=id, titulo=f"Opp {id}", funil_id=1, etapa_id=10, etapa="Proposta", resultado="aberta",
                responsavel_id=7, valor=D("1000"), empresa_id=3, empresa="Aurora", contato="Paula",
                campos_custom={"interesse": "Alto"}, ultima_interacao=HOJE)
    base.update(kw)
    return a.OportunidadeFoto(**base)


def _tit(id=1, **kw):
    base = dict(id=id, direcao="receber", status="aberto", vencimento=HOJE - timedelta(days=3), valor_original=D("6000"),
                saldo=D("6000"), responsavel_id=9, descricao="Consultoria", empresa_id=5, empresa="Ponto Norte")
    base.update(kw)
    return a.TituloFoto(**base)


def _regra(gatilho, area="comercial", **kw):
    return a.Regra(id=kw.pop("id", 1), area=area, gatilho=gatilho, ativada_em=kw.pop("ativada_em", ATIVADA), **kw)


# ---------------------------------------------------------------- catálogo
def test_quinze_modelos_da_especificacao():
    assert len(a.modelos_da_area("comercial")) == 8 and len(a.modelos_da_area("financeiro")) == 7
    for m in a.MODELOS:
        assert m["gatilho"] in a.GATILHOS[m["area"]] and m["acao"] in a.ACOES
        a.validar_configuracao(_cfg(area=m["area"], nome=m["nome"], gatilho=m["gatilho"], acao=m["acao"],
                                    conteudo=m["conteudo"], campo=m["campo"], operador=m["operador"],
                                    valor_esperado=m["valor_esperado"], prazo_dias=m["prazo_dias"],
                                    tipo_atividade=m["tipo_atividade"], destinatario=m["destinatario"]))
    nomes = {m["nome"] for m in a.MODELOS}
    assert {"Follow-up de proposta", "Cobrança após vencimento", "Alerta de caixa", "Conferir recorrência"} <= nomes


# ---------------------------------------------------------------- validação
@pytest.mark.parametrize("kw, msg", [
    ({"nome": " "}, "nome"),
    ({"gatilho": "titulo_vencido"}, "Gatilho não disponível"),
    ({"acao": "apagar"}, "Ação inválida"),
    ({"conteudo": ""}, "modelo"),
    ({"campo": "interesse", "operador": None}, "operador"),
    ({"campo": "interesse", "operador": "igual"}, "valor esperado"),
    ({"gatilho": "campo_alterado"}, "campo monitorado"),
    ({"prazo_dias": 400}, "Prazo"),
    ({"tipo_atividade": "visita"}, "Tipo de atividade"),
    ({"acao": "enviar_email"}, "destinatário"),
    ({"acao": "atualizar_campo", "conteudo": "sem igual"}, "campo = valor"),
    ({"responsavel_regra": "qualquer"}, "Responsável"),
])
def test_validacao(kw, msg):
    with pytest.raises(RegraViolada, match=msg):
        a.validar_configuracao(_cfg(**kw))


def test_atualizar_o_proprio_campo_monitorado_e_ciclo():
    with pytest.raises(RegraViolada, match="ciclo"):
        a.validar_configuracao(_cfg(gatilho="campo_alterado", campo="Interesse", operador="igual", valor_esperado="Alto",
                                    acao="atualizar_campo", conteudo="interesse = Médio"))


def test_validacao_normaliza():
    c = a.validar_configuracao(_cfg(campo="Data de retomada", operador="preenchido", tipo_atividade=None))
    assert c.campo == "data_de_retomada" and c.tipo_atividade == "tarefa" and c.responsavel_regra == a.RESPONSAVEL_DO_REGISTRO
    f = a.validar_configuracao(_cfg(area="financeiro", gatilho="saldo_abaixo_limite", valor_esperado="R$ 1.500,00",
                                    funil_id=3))
    assert f.valor_esperado == "1500.00" and f.funil_id is None


def test_ativacao_de_envio_exige_canal_conectado():
    with pytest.raises(RegraViolada, match=a.MSG_CANAL):
        a.validar_ativacao("enviar_whatsapp", {"email"})
    a.validar_ativacao("enviar_email", {"email"})
    a.validar_ativacao("criar_atividade", set())


# ---------------------------------------------------------------- condição e variáveis
@pytest.mark.parametrize("dados, op, valor, esperado", [
    ({"interesse": "Alto"}, "igual", "alto", True),
    ({"interesse": "Médio"}, "igual", "Medio", True),
    ({"interesse": "Alto"}, "diferente", "Alto", False),
    ({"saldo": D("6000")}, "maior", "5000", True),
    ({"saldo": D("6000")}, "menor", "R$ 5.000,00", False),
    ({"saldo": "abc"}, "maior", "1", False),
    ({"x": None}, "preenchido", None, False),
    ({"x": "ok"}, "preenchido", None, True),
    ({}, "diferente", "Alto", True),
])
def test_condicao(dados, op, valor, esperado):
    campo = next(iter(dados), "interesse")
    assert a.condicao_ok(dados, campo, op, valor) is esperado
    assert a.condicao_ok(dados, None, None, None) is True


def test_renderizar_variaveis():
    v = a.variaveis_titulo(_tit())
    assert a.renderizar("{{empresa.nome}}: {{titulo.valor}} em {{titulo.vencimento}} {{nao.existe}}", v) == \
        "Ponto Norte: R$ 6.000,00 em 07/11/2026 —"


def test_prazo_em_dias_uteis_e_responsavel():
    sexta = date(2026, 11, 13)
    assert a.prazo_da_atividade("oportunidade_etapa", 2, sexta) == date(2026, 11, 17)
    assert a.prazo_da_atividade("titulo_vencido", 2, sexta) == sexta
    assert a.responsavel("usuario:4", 7) == 4 and a.responsavel(a.RESPONSAVEL_DO_REGISTRO, 7) == 7


def test_retentativa_limitada():
    assert a.decidir_retentativa("falhou", 1) and a.decidir_retentativa("falhou", 2)
    assert not a.decidir_retentativa("falhou", a.MAX_TENTATIVAS)
    assert not a.decidir_retentativa("executada", 1)


# ---------------------------------------------------------------- gatilhos comerciais
def test_eventos_novos_disparam_uma_vez_cada():
    e = a.Estado(oportunidades=[_opp(1), _opp(2, funil_id=2)], eventos=[
        a.EventoFoto(100, 1, "ganha", ATIVADA + timedelta(hours=1)),
        a.EventoFoto(101, 1, "ganha", ATIVADA - timedelta(days=1)),  # antes da ativação: não dispara
        a.EventoFoto(102, 2, "ganha", ATIVADA + timedelta(hours=2)),
        a.EventoFoto(103, 1, "etapa", ATIVADA + timedelta(hours=3)),
    ])
    ocs = a.ocorrencias(_regra("oportunidade_ganha"), e, HOJE)
    assert [(o.registro, o.ocorrencia) for o in ocs] == [("oportunidade:1", "evento:100"), ("oportunidade:2", "evento:102")]
    assert a.ocorrencias(_regra("oportunidade_ganha", funil_id=2), e, HOJE)[0].registro_id == 2
    assert a.chave_idempotencia(5, ocs[0]) == "5:oportunidade:1:evento:100"
    assert a.ocorrencias(_regra("oportunidade_ganha"), e, HOJE) == ocs  # determinística


def test_etapa_destino_e_condicao_de_campo():
    e = a.Estado(oportunidades=[_opp(1, etapa_id=10), _opp(2, etapa_id=11), _opp(3, etapa_id=10,
                                                                               campos_custom={"Interesse": "Baixo"})],
                 eventos=[a.EventoFoto(i, i, "etapa", ATIVADA + timedelta(hours=i)) for i in (1, 2, 3)])
    r = _regra("oportunidade_etapa", etapa_destino_id=10, campo="interesse", operador="igual", valor_esperado="Alto")
    assert [o.registro_id for o in a.ocorrencias(r, e, HOJE)] == [1]


def test_campo_alterado_dispara_quando_passa_a_casar():
    r = _regra("campo_alterado", campo="interesse", operador="igual", valor_esperado="Alto")
    ocs = a.ocorrencias(r, a.Estado(oportunidades=[_opp(1), _opp(2, campos_custom={"interesse": "Baixo"}),
                                                   _opp(3, resultado="ganha")]), HOJE)
    assert [(o.registro_id, o.ocorrencia) for o in ocs] == [(1, "campo:interesse=alto")]


def test_sem_interacao_fechamento_e_reuniao():
    e = a.Estado(oportunidades=[_opp(1, ultima_interacao=HOJE - timedelta(days=6)),
                                _opp(2, ultima_interacao=HOJE - timedelta(days=2), previsao_fechamento=HOJE + timedelta(days=3)),
                                _opp(3, resultado="perdida", ultima_interacao=HOJE - timedelta(days=60))],
                 atividades=[a.AtividadeFoto(50, "Reunião", "reuniao", "concluida", HOJE, 7, 2,
                                             concluida_em=ATIVADA + timedelta(hours=1))])
    assert [o.registro_id for o in a.ocorrencias(_regra("sem_interacao", prazo_dias=5), e, HOJE)] == [1]
    assert [o.registro_id for o in a.ocorrencias(_regra("fechamento_proximo", prazo_dias=7), e, HOJE)] == [2]
    assert [o.registro for o in a.ocorrencias(_regra("reuniao_encerrada"), e, HOJE)] == ["atividade:50"]


def test_atividade_atrasada_com_prevencao_de_ciclo():
    atividades = [a.AtividadeFoto(1, "Manual", "tarefa", "pendente", HOJE - timedelta(days=2), 7),
                  a.AtividadeFoto(2, "Da própria automação", "tarefa", "pendente", HOJE - timedelta(days=2), 7,
                                  criada_por_automacoes=frozenset({1})),
                  a.AtividadeFoto(3, "De outra automação", "tarefa", "pendente", HOJE - timedelta(days=2), 7,
                                  criada_por_automacoes=frozenset({9})),
                  a.AtividadeFoto(4, "Concluída", "tarefa", "concluida", HOJE - timedelta(days=2), 7),
                  a.AtividadeFoto(5, "No prazo", "tarefa", "pendente", HOJE, 7),
                  a.AtividadeFoto(6, "Origem automação", "tarefa", "pendente", HOJE - timedelta(days=2), 7,
                                  origem="automacao")]
    ocs = a.ocorrencias(_regra("atividade_atrasada", id=1), a.Estado(atividades=atividades), HOJE)
    # atividade criada por QUALQUER automação não dispara outra (A → B → A … seria um ciclo): profundidade 1
    assert [o.registro_id for o in ocs] == [1]


def test_reuniao_encerrada_criada_por_automacao_nao_dispara():
    reuniao = a.AtividadeFoto(50, "Reunião", "reuniao", "concluida", HOJE, 7, 2, concluida_em=ATIVADA + timedelta(hours=1),
                              origem="automacao")
    e = a.Estado(oportunidades=[_opp(2)], atividades=[reuniao])
    assert a.ocorrencias(_regra("reuniao_encerrada"), e, HOJE) == []


# ---------------------------------------------------------------- gatilhos financeiros
def test_titulo_vencido_respeita_contestacao_recebido_e_cancelado():
    titulos = [_tit(1), _tit(2, em_contestacao=True), _tit(3, status="liquidado", saldo=D("0")),
               _tit(4, status="cancelado"), _tit(5, vencimento=HOJE - timedelta(days=1)), _tit(6, direcao="pagar"),
               _tit(7, status="parcial", saldo=D("100"))]
    ocs = a.ocorrencias(_regra("titulo_vencido", "financeiro", prazo_dias=2), a.Estado(titulos=titulos), HOJE)
    assert [o.registro_id for o in ocs] == [1, 7]
    assert ocs[0].variaveis["titulo.valor"] == "R$ 6.000,00"


def test_vencimento_e_pagamento_proximos():
    titulos = [_tit(1, vencimento=HOJE + timedelta(days=3)), _tit(2, vencimento=HOJE + timedelta(days=4)),
               _tit(3, direcao="pagar", vencimento=HOJE + timedelta(days=2)),
               _tit(4, vencimento=HOJE + timedelta(days=1), em_contestacao=True)]
    e = a.Estado(titulos=titulos)
    assert [o.registro_id for o in a.ocorrencias(_regra("vencimento_proximo", "financeiro", prazo_dias=3), e, HOJE)] == [1]
    assert [o.registro_id for o in a.ocorrencias(_regra("pagamento_proximo", "financeiro", prazo_dias=3), e, HOJE)] == [3]


def test_recebimentos_confirmacao_e_parcial_por_saldo():
    depois = ATIVADA + timedelta(hours=1)
    titulos = [_tit(1, status="parcial", saldo=D("4000"), ultima_baixa_em=depois),
               _tit(2, status="liquidado", saldo=D("0"), ultima_baixa_em=depois),
               _tit(3, status="parcial", saldo=D("10"), ultima_baixa_em=ATIVADA - timedelta(days=3)),
               _tit(4, status="aberto", confirmado_em=depois)]
    e = a.Estado(titulos=titulos)
    parcial = a.ocorrencias(_regra("recebimento_parcial", "financeiro"), e, HOJE)
    assert [(o.registro_id, o.ocorrencia) for o in parcial] == [(1, "parcial:4000.00")]
    assert [o.registro_id for o in a.ocorrencias(_regra("recebimento_total", "financeiro"), e, HOJE)] == [2]
    assert [o.registro_id for o in a.ocorrencias(_regra("recebivel_confirmado", "financeiro"), e, HOJE)] == [4]


def test_recorrencias_e_saldo():
    rec = a.RecorrenciaFoto(1, "Mensalidade", "ativa", date(2026, 9, 12), date(2026, 11, 30), "mensal",
                            competencias_existentes=frozenset({"2026-09", "2026-10"}))
    e = a.Estado(recorrencias=[rec], caixa=a.CaixaFoto(D("900")))
    gerar = a.ocorrencias(_regra("recorrencia_a_gerar", "financeiro", prazo_dias=5), e, HOJE)
    assert [o.ocorrencia for o in gerar] == ["competencia:2026-11"]
    assert len(a.ocorrencias(_regra("recorrencia_a_renovar", "financeiro", prazo_dias=30), e, HOJE)) == 1
    abaixo = a.ocorrencias(_regra("saldo_abaixo_limite", "financeiro", valor_esperado="1000"), e, HOJE)
    assert abaixo[0].registro == "caixa:0" and "R$ 900,00" in abaixo[0].rotulo
    assert a.ocorrencias(_regra("saldo_abaixo_limite", "financeiro", valor_esperado="500"), e, HOJE) == []


def test_gatilho_de_outra_area_nao_avalia():
    assert a.ocorrencias(_regra("titulo_vencido", "comercial"), a.Estado(titulos=[_tit()]), HOJE) == []
