"""Automações: API (CRUD por área, modelos, testar, ativar/pausar, histórico) e o MOTOR real (idempotência,
retentativas, ciclo, cobrança em contestação, envio pendente de conector)."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import agora, hoje
from app.core.models import Auditoria
from app.modules.comercial.models import Atividade, Etapa, Oportunidade, OportunidadeEvento
from app.modules.financeiro.models import Cobranca, Titulo
from app.modules.orquestracao import motor
from app.modules.orquestracao.models import Automacao, AutomacaoExecucao, Integracao

URL = "/api/orquestracao/automacoes"


def _nova(client, h, **kw):
    corpo = {"area": "comercial", "nome": "Handoff de venda ganha", "gatilho": "oportunidade_ganha",
             "acao": "criar_atividade", "tipo_atividade": "tarefa", "prazo_dias": 1,
             "conteudo": "Handoff: revisar recebíveis de {{oportunidade.titulo}} ({{empresa.nome}})"}
    corpo.update(kw)
    return client.post(URL, json=corpo, headers=h)


def _criar_ativa(db, **kw) -> Automacao:
    base = dict(area="comercial", nome="A", gatilho="oportunidade_ganha", acao="criar_atividade", tipo_atividade="tarefa",
                conteudo="Revisar {{oportunidade.titulo}}", estado="ativa", ativada_em=agora(),
                responsavel_regra="responsavel_do_registro")
    base.update(kw)
    a = Automacao(**base)
    db.add(a)
    db.commit()
    return a


def _contar(db, modelo, *cond) -> int:
    return db.scalar(select(func.count()).select_from(modelo).where(*cond))


# ---------------------------------------------------------------- catálogo e modelos
def test_catalogo_e_modelos(client, gestor, comercial):
    c = client.get(f"{URL}/catalogo", headers=comercial).json()
    assert len(c["gatilhos"]["comercial"]) == 9 and len(c["gatilhos"]["financeiro"]) == 10
    assert c["funis"][0]["nome"] == "Serviços B2B" and len(c["funis"][0]["etapas"]) == 4
    assert any(x["slug"] == "interesse" for x in c["campos"])
    com = client.get(f"{URL}/modelos", params={"area": "comercial"}, headers=gestor).json()
    fin = client.get(f"{URL}/modelos", params={"area": "financeiro"}, headers=gestor).json()
    assert len(com) == 8 and len(fin) == 7
    follow = next(m for m in com if m["nome"] == "Follow-up de proposta")
    assert follow["etapa_destino_id"] and follow["gatilho_rotulo"] == "Oportunidade movida de etapa"


# ---------------------------------------------------------------- CRUD
def test_crud_por_area_com_auditoria(client, gestor, db):
    r = _nova(client, gestor)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["estado"] == "rascunho" and a["acao_rotulo"] == "Criar atividade"
    assert [x["id"] for x in client.get(URL, params={"area": "comercial"}, headers=gestor).json()] == [a["id"]]
    assert client.get(URL, params={"area": "financeiro"}, headers=gestor).json() == []
    r = client.patch(f"{URL}/{a['id']}", json={"nome": "Handoff revisado", "prazo_dias": 2}, headers=gestor)
    assert r.status_code == 200 and r.json()["nome"] == "Handoff revisado" and r.json()["conteudo"] == a["conteudo"]
    acoes = set(db.scalars(select(Auditoria.acao).where(Auditoria.entidade == "automacao")))
    assert {"automacao.criar", "automacao.alterar"} <= acoes


def test_validacoes_403_e_404(client, gestor, comercial, financeiro):
    r = _nova(client, gestor, gatilho="titulo_vencido")
    assert r.status_code == 400 and "Gatilho não disponível" in r.json()["detail"]
    assert _nova(client, gestor, campo="interesse", operador="igual").status_code == 400
    assert _nova(client, gestor, area="vendas").status_code == 422
    assert _nova(client, gestor, funil_id=999).status_code == 400
    assert _nova(client, comercial).status_code == 403  # Comercial só vê automações
    assert client.get(URL, params={"area": "comercial"}, headers=comercial).status_code == 200
    assert client.get(URL, params={"area": "comercial"}, headers=financeiro).status_code == 403  # outra área
    assert client.get(URL, params={"area": "financeiro"}, headers=comercial).status_code == 403
    assert client.get(URL, params={"area": "financeiro"}, headers=financeiro).status_code == 200
    assert client.get(f"{URL}/999", headers=gestor).status_code == 404
    assert client.patch(f"{URL}/999", json={"nome": "x"}, headers=gestor).status_code == 404
    assert client.post(f"{URL}/999/ativar", headers=gestor).status_code == 404


def test_ativar_envio_exige_canal_conectado(client, gestor, db):
    a = _nova(client, gestor, nome="Mensagem de acompanhamento", gatilho="oportunidade_etapa",
              acao="enviar_whatsapp", destinatario="contato_principal").json()
    r = client.post(f"{URL}/{a['id']}/ativar", headers=gestor)
    assert r.status_code == 400 and r.json()["detail"] == "Conecte o canal autorizado antes de ativar envios"
    db.add(Integracao(tipo="whatsapp", estado="conectado", escopos=[]))
    db.commit()
    r = client.post(f"{URL}/{a['id']}/ativar", headers=gestor)
    assert r.status_code == 200 and r.json()["estado"] == "ativa" and r.json()["ativada_em"]
    r = client.post(f"{URL}/{a['id']}/pausar", headers=gestor)
    assert r.json()["estado"] == "pausada"


def test_testar_e_previa_sem_executar(client, gestor, db):
    a = _nova(client, gestor, area="financeiro", nome="Cobrança", gatilho="titulo_vencido", prazo_dias=2,
              acao="criar_atividade", conteudo="Cobrar {{empresa.nome}} · {{titulo.valor}}").json()
    r = client.post(f"{URL}/{a['id']}/testar", headers=gestor)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["elegiveis"] == 1 and "Ponto Norte" in t["amostra"][0] and "não cria tarefas" in t["observacao"]
    assert _contar(db, Atividade, Atividade.origem == "automacao") == 0
    hist = client.get(f"{URL}/execucoes", params={"area": "financeiro"}, headers=gestor).json()
    assert hist[0]["resultado"] == "simulada" and hist[0]["simulacao"] is True


# ---------------------------------------------------------------- motor
def test_motor_evento_ganho_cria_atividade_uma_vez(db, demo):
    a = _criar_ativa(db)
    op = db.scalar(select(Oportunidade).where(Oportunidade.titulo == "Projeto de consultoria"))
    db.add(OportunidadeEvento(oportunidade_id=op.id, tipo="ganha", texto="Ganha"))
    db.commit()
    assert motor.executar(db, hoje()) == {"executada": 1}
    criadas = list(db.scalars(select(Atividade).where(Atividade.origem == "automacao")))
    assert len(criadas) == 1 and criadas[0].assunto == "Revisar Projeto de consultoria"
    assert criadas[0].responsavel_id == op.responsavel_id and criadas[0].oportunidade_id == op.id
    ex = db.scalar(select(AutomacaoExecucao).where(AutomacaoExecucao.automacao_id == a.id))
    assert ex.resultado == "executada" and ex.registro_criado == f"atividade:{criadas[0].id}"
    # idempotência: rodar de novo não duplica
    assert motor.executar(db, hoje()) == {"repetida": 1}
    assert _contar(db, Atividade, Atividade.origem == "automacao") == 1
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "atividade.criar", Auditoria.usuario_id.is_(None)))


def test_motor_ignora_eventos_antes_da_ativacao_e_etapa_destino(db, demo):
    proposta = db.scalar(select(Etapa).where(Etapa.nome == "Proposta"))
    # eventos do seed: 1 minuto antes da ativação (o relógio do Windows tem resolução de ~15 ms)
    db.execute(OportunidadeEvento.__table__.update().values(quando=agora() - timedelta(minutes=1)))
    db.commit()
    _criar_ativa(db, gatilho="oportunidade_etapa", etapa_destino_id=proposta.id, tipo_atividade="email", prazo_dias=2)
    # o seed gravou eventos "etapa" antes da ativação
    assert motor.executar(db, hoje()) == {}
    vertice = db.scalar(select(Oportunidade).where(Oportunidade.titulo == "Expansão de operação"))
    aurora = db.scalar(select(Oportunidade).where(Oportunidade.titulo == "Projeto de consultoria"))
    db.add_all([OportunidadeEvento(oportunidade_id=vertice.id, tipo="etapa", texto="Entrou em Proposta"),
                OportunidadeEvento(oportunidade_id=aurora.id, tipo="etapa", texto="Entrou em Negociação")])
    db.commit()
    assert motor.executar(db, hoje()) == {"executada": 1}
    at = db.scalar(select(Atividade).where(Atividade.origem == "automacao"))
    assert at.oportunidade_id == vertice.id and at.tipo == "email" and at.prazo > hoje()


def test_cobranca_respeita_contestacao(db, demo):
    _criar_ativa(db, area="financeiro", gatilho="titulo_vencido", prazo_dias=2, conteudo="Cobrar {{empresa.nome}}")
    vencido = db.scalar(select(Titulo).where(Titulo.descricao == "Consultoria • parcela 1/2"))
    db.add(Cobranca(assunto="Contestação", titulo_id=vencido.id, responsavel_id=vencido.responsavel_id, canal="email",
                    situacao="em_contestacao", historico="Cliente contesta o valor."))
    db.commit()
    assert motor.executar(db, hoje()) == {}
    db.execute(Cobranca.__table__.update().values(situacao="em_acompanhamento"))
    db.commit()
    assert motor.executar(db, hoje()) == {"executada": 1}
    # recebido não cobra mais
    vencido.status, vencido.saldo = "liquidado", Decimal("0")
    db.commit()
    assert motor.executar(db, hoje()) == {}


def test_envio_fica_pendente_de_conector(db, demo):
    _criar_ativa(db, area="financeiro", gatilho="titulo_vencido", acao="enviar_whatsapp",
                 destinatario="contato_principal", conteudo="Olá, {{titulo.valor}} vencido")
    assert motor.executar(db, hoje()) == {"pendente_conector": 1}
    ex = db.scalar(select(AutomacaoExecucao))
    assert "Nenhuma mensagem foi enviada" in ex.detalhe and "R$ 6.000,00" in ex.detalhe


def test_retentativas_limitadas(db, demo):
    a = _criar_ativa(db, area="financeiro", gatilho="titulo_vencido", acao="atualizar_campo",
                     conteudo="campo_inexistente = 1")
    for _ in range(5):
        motor.executar(db, hoje())
    ex = db.scalar(select(AutomacaoExecucao).where(AutomacaoExecucao.automacao_id == a.id))
    assert ex.resultado == "falhou" and ex.tentativas == 3 and "não se aplica" in ex.erro


def test_prevencao_de_ciclo_atividade_atrasada(db, demo):
    a = _criar_ativa(db, gatilho="atividade_atrasada", conteudo="Remarcar: {{atividade.assunto}}")
    primeira = motor.executar(db, hoje())
    assert primeira == {"executada": 1}  # "Retomar proposta da Vértice" (atrasada no seed)
    criada = db.scalar(select(Atividade).where(Atividade.origem == "automacao"))
    assert criada.assunto == "Remarcar: Retomar proposta da Vértice"
    # dias depois, a atividade criada pela automação também atrasa: a MESMA automação não dispara sobre ela
    depois = hoje() + timedelta(days=5)
    resultado = motor.executar(db, depois)
    criadas = list(db.scalars(select(Atividade).where(Atividade.origem == "automacao")))
    assert all(not x.assunto.startswith("Remarcar: Remarcar") for x in criadas)
    alvos = set(db.scalars(select(AutomacaoExecucao.registro).where(AutomacaoExecucao.automacao_id == a.id)))
    assert f"atividade:{criada.id}" not in alvos
    assert resultado.get("executada", 0) >= 1  # outras atividades do seed atrasaram nesse meio-tempo


def test_notificar_responsavel_vira_aviso(client, gestor, db, demo):
    _criar_ativa(db, area="financeiro", gatilho="saldo_abaixo_limite", acao="notificar", valor_esperado="999999",
                 responsavel_regra=None, conteudo="Saldo projetado {{caixa.saldo_projetado}} ({{caixa.formula}})")
    assert motor.executar(db, hoje()) == {"notificado": 1}
    avisos = client.get(f"{URL}/avisos", headers=gestor).json()
    assert len(avisos) == 1 and "Saldo projetado R$" in avisos[0]["texto"]
    assert motor.executar(db, hoje()) == {"repetida": 1}  # uma vez por dia


def test_atualizar_campo_da_oportunidade(db, demo):
    _criar_ativa(db, gatilho="fechamento_proximo", prazo_dias=15, acao="atualizar_campo", conteudo="Interesse = Alto")
    horizonte = db.scalar(select(Oportunidade).where(Oportunidade.titulo == "Diagnóstico estratégico"))
    horizonte.previsao_fechamento = hoje() + timedelta(days=3)
    horizonte.campos_custom = {"interesse": "Médio"}
    db.commit()
    assert motor.executar(db, hoje()).get("executada", 0) >= 1
    db.refresh(horizonte)
    assert horizonte.campos_custom["interesse"] == "Alto"


def test_tarefa_do_worker_registrada():
    import app.modules.orquestracao.tarefas as tarefas
    from app.worker import TAREFAS

    assert any(t.nome == "automacoes" and t.fn is tarefas.rodar_automacoes for t in TAREFAS)
