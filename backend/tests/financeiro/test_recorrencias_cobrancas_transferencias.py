"""Recorrências (CRUD, gerar competência, worker idempotente), cobranças e acordos, transferências."""

from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.models import Auditoria
from app.domain.dinheiro import somar_meses
from app.domain.recorrencia import competencia_de
from app.modules.financeiro.models import Titulo
from app.modules.financeiro.tarefas import gerar_competencias_pendentes
from tests.financeiro.conftest import novo_titulo

R = "/api/financeiro/recorrencias"
C = "/api/financeiro/cobrancas"
TR = "/api/financeiro/transferencias"


def _rec(client, cen, headers=None, **kw):
    inicio = date(cen.hoje.year, cen.hoje.month, 1)
    corpo = {"descricao": "Mensalidade", "direcao": "receber", "empresa_id": cen.cliente.id, "valor_ciclo": "4800",
             "frequencia": "mensal", "inicio": str(inicio), "fim": str(somar_meses(inicio, 11)),
             "dia_vencimento": 28, "categoria_id": cen.receita.id, "responsavel_id": cen.admin_id, **kw}
    return client.post(R, json=corpo, headers=headers or cen.h_admin)


# ---------------------------------------------------------------- recorrências
def test_crud_recorrencia(client, db, cen):
    r = _rec(client, cen)
    assert r.status_code == 201
    rec = r.json()
    assert rec["empresa_nome"] == "Ponto Norte" and rec["competencias_geradas"] == []
    assert rec["proxima_competencia"] == competencia_de(cen.hoje)
    r = client.patch(f"{R}/{rec['id']}", json={"situacao": "pausada", "valor_ciclo": "5000"}, headers=cen.h_admin)
    assert r.status_code == 200 and r.json()["situacao"] == "pausada" and r.json()["valor_ciclo"] == "5000.00"
    assert r.json()["proxima_competencia"] is None
    assert client.get(R, params={"situacao": "pausada"}, headers=cen.h_fin).json()[0]["id"] == rec["id"]
    assert client.get(R, params={"q": "ponto"}, headers=cen.h_fin).json()[0]["id"] == rec["id"]
    assert client.get(f"{R}/{rec['id']}", headers=cen.h_fin).status_code == 200
    assert client.get(f"{R}/999", headers=cen.h_fin).status_code == 404
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "recorrencia.editar"))


def test_recorrencia_validacoes_e_permissao(client, cen):
    assert _rec(client, cen, dia_vencimento=29).json()["detail"] == "Informe valor positivo e dia inteiro entre 1 e 28"
    assert _rec(client, cen, valor_ciclo="0").status_code == 400
    r = _rec(client, cen, fim=str(cen.hoje - timedelta(days=400)))
    assert r.json()["detail"] == "A data final deve ser igual ou posterior ao início"
    assert _rec(client, cen, frequencia="semanal").status_code == 422
    assert _rec(client, cen, headers=cen.h_leitura).status_code == 403
    rec = _rec(client, cen).json()
    r = client.patch(f"{R}/{rec['id']}", json={"dia_vencimento": 0}, headers=cen.h_admin)
    assert r.status_code == 400


def test_gerar_competencia_em_rascunho_sem_duplicar(client, cen):
    rec = _rec(client, cen).json()
    comp = competencia_de(cen.hoje)
    r = client.post(f"{R}/{rec['id']}/gerar", json={"competencia": comp}, headers=cen.h_admin)
    assert r.status_code == 201
    t = r.json()
    assert (t["status"], t["competencia"], t["origem_recorrencia_id"], t["valor_original"]) == (
        "rascunho", comp, rec["id"], "4800.00")
    assert t["vencimento"].endswith("-28")
    r = client.post(f"{R}/{rec['id']}/gerar", json={"competencia": comp}, headers=cen.h_admin)
    assert r.json()["detail"] == "Título desta competência já existe"
    fora = competencia_de(somar_meses(cen.hoje, 13))
    r = client.post(f"{R}/{rec['id']}/gerar", json={"competencia": fora}, headers=cen.h_admin)
    assert r.json()["detail"] == "Competência fora da vigência"
    assert client.get(f"{R}/{rec['id']}", headers=cen.h_admin).json()["competencias_geradas"] == [comp]


def test_gerar_competencia_respeita_frequencia_e_situacao(client, cen):
    rec = _rec(client, cen, frequencia="trimestral").json()
    seguinte = competencia_de(somar_meses(cen.hoje, 1))
    r = client.post(f"{R}/{rec['id']}/gerar", json={"competencia": seguinte}, headers=cen.h_admin)
    assert r.json()["detail"] == "Competência incompatível com a frequência"
    client.patch(f"{R}/{rec['id']}", json={"situacao": "pausada"}, headers=cen.h_admin)
    r = client.post(f"{R}/{rec['id']}/gerar", json={"competencia": competencia_de(cen.hoje)}, headers=cen.h_admin)
    assert r.json()["detail"] == "A recorrência deve estar ativa"


def test_recorrencia_a_pagar_gera_titulo_pendente_de_aprovacao(client, cen):
    rec = _rec(client, cen, direcao="pagar", empresa_id=cen.fornecedor.id).json()
    t = client.post(f"{R}/{rec['id']}/gerar", json={"competencia": competencia_de(cen.hoje)},
                    headers=cen.h_admin).json()
    assert t["direcao"] == "pagar" and t["aprovacao"] == "pendente"


def test_worker_gera_proxima_competencia_ate_30_dias_e_e_idempotente(client, db, cen):
    hoje = date(2026, 11, 10)
    inicio = date(2026, 9, 1)
    for dia, sit in ((12, "ativa"), (12, "pausada"), (5, "ativa")):
        _rec(client, cen, inicio=str(inicio), fim=str(date(2027, 8, 31)), dia_vencimento=dia, situacao=sit)
    criados = gerar_competencias_pendentes(db, hoje)
    titulos = [db.get(Titulo, i) for i in criados]
    assert sorted((t.competencia, t.vencimento.day, t.status) for t in titulos) == [
        ("2026-11", 12, "rascunho"), ("2026-12", 5, "rascunho")]
    assert gerar_competencias_pendentes(db, hoje) == []  # idempotente
    assert db.scalar(select(func.count(Titulo.id))) == 2
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "recorrencia.gerar_competencia")).usuario_nome == "Robô"


# ---------------------------------------------------------------- cobranças e acordos
def _cob(client, cen, titulo_id, headers=None, **kw):
    corpo = {"assunto": "Lembrete de vencimento", "titulo_id": titulo_id, "responsavel_id": cen.fin_id,
             "canal": "email", "historico": "Cliente pediu boleto atualizado.", **kw}
    return client.post(C, json=corpo, headers=headers or cen.h_admin)


def test_crud_cobranca_e_contestados(client, db, cen):
    t = novo_titulo(client, cen, valor="6000", vencimento=cen.hoje - timedelta(days=7))
    r = _cob(client, cen, t["id"], headers=cen.h_fin)
    assert r.status_code == 201
    c = r.json()
    assert (c["situacao"], c["empresa_nome"], c["titulo_estado"]) == ("em_acompanhamento", "Ponto Norte", "vencido")
    assert client.get(f"{C}/contestados", headers=cen.h_fin).json() == {"titulo_ids": []}
    r = client.patch(f"{C}/{c['id']}", json={"situacao": "em_contestacao", "historico": "Cliente contesta escopo."},
                     headers=cen.h_fin)
    assert r.status_code == 200 and r.json()["situacao"] == "em_contestacao"
    assert client.get(f"{C}/contestados", headers=cen.h_fin).json() == {"titulo_ids": [t["id"]]}
    assert client.get(f"/api/financeiro/titulos/{t['id']}", headers=cen.h_fin).json()["em_contestacao"]
    assert client.get(C, params={"situacao": "em_contestacao"}, headers=cen.h_fin).json()[0]["id"] == c["id"]
    assert client.get(C, params={"q": "ponto"}, headers=cen.h_fin).json()[0]["id"] == c["id"]
    assert client.get(f"{C}/{c['id']}", headers=cen.h_fin).status_code == 200
    assert client.get(f"{C}/999", headers=cen.h_fin).status_code == 404
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "cobranca.editar"))


def test_cobranca_validacoes_e_permissao(client, cen):
    t = novo_titulo(client, cen, valor="6000")
    r = _cob(client, cen, t["id"], situacao="promessa_pagamento")
    assert r.json()["detail"] == "Promessa de pagamento exige a data prometida."
    r = _cob(client, cen, t["id"], valor_prometido="7000")
    assert r.json()["detail"] == "Valor prometido deve ser positivo e não superar o saldo do título."
    pagar = novo_titulo(client, cen, direcao="pagar")
    assert _cob(client, cen, pagar["id"]).json()["detail"] == "Cobrança é ligada a um título a receber."
    rascunho = novo_titulo(client, cen, rascunho=True)
    assert _cob(client, cen, rascunho["id"]).status_code == 400
    assert _cob(client, cen, 999).status_code == 400
    assert _cob(client, cen, t["id"], historico="").status_code == 422
    assert _cob(client, cen, t["id"], headers=cen.h_leitura).status_code == 403
    ok = _cob(client, cen, t["id"], situacao="promessa_pagamento", data_prometida=str(cen.hoje),
              valor_prometido="3000")
    assert ok.status_code == 201 and ok.json()["valor_prometido"] == "3000.00"


# ---------------------------------------------------------------- transferências
def test_transferencia_valida_e_nao_muda_total(client, db, cen):
    antes = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    corpo = {"conta_origem_id": cen.conta.id, "conta_destino_id": cen.conta2.id, "valor": "5000",
             "data": str(cen.hoje), "descricao": "Reserva mensal"}
    r = client.post(TR, json=corpo, headers=cen.h_fin)
    assert r.status_code == 201
    assert (r.json()["conta_origem_nome"], r.json()["conta_destino_nome"]) == ("Conta operacional", "Reserva")
    depois = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    assert depois["saldo_gerencial"]["valor"] == antes["saldo_gerencial"]["valor"] == "26000.00"
    saldos = {c["nome"]: c["saldo_atual"] for c in depois["contas"]}
    assert saldos == {"Conta operacional": "20000.00", "Reserva": "6000.00"}
    assert client.get(TR, headers=cen.h_fin).json()["total"] == 1
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "transferencia.criar"))


def test_transferencia_validacoes(client, cen):
    base = {"conta_origem_id": cen.conta.id, "conta_destino_id": cen.conta2.id, "valor": "10", "data": str(cen.hoje)}
    msg = "Selecione contas diferentes e valor positivo"
    assert client.post(TR, json={**base, "conta_destino_id": cen.conta.id}, headers=cen.h_fin).json()["detail"] == msg
    assert client.post(TR, json={**base, "valor": "0"}, headers=cen.h_fin).json()["detail"] == msg
    assert client.post(TR, json={**base, "conta_destino_id": 999}, headers=cen.h_fin).json()["detail"] == msg
    data_msg = "Data deve respeitar as datas-base das contas e hoje"
    futuro = {**base, "data": str(cen.hoje + timedelta(days=1))}
    assert client.post(TR, json=futuro, headers=cen.h_fin).json()["detail"] == data_msg
    antes = {**base, "data": str(cen.hoje - timedelta(days=31))}
    assert client.post(TR, json=antes, headers=cen.h_fin).json()["detail"] == data_msg
    assert client.post(TR, json=base, headers=cen.h_leitura).status_code == 403
