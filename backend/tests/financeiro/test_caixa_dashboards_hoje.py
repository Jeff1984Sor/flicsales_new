"""Caixa (saldo por conta, projeção, limites), dashboards (aging) e o Hoje financeiro (leitura determinística)."""

from datetime import timedelta

from app.core.db import hoje
from app.seed import semear
from tests.conftest import auth, entrar
from tests.financeiro.conftest import baixa, novo_titulo


def test_caixa_saldo_projecao_e_exclusoes(client, cen):
    rec = novo_titulo(client, cen, valor="19300")
    novo_titulo(client, cen, valor="999", rascunho=True)  # rascunho fora
    cancel = novo_titulo(client, cen, valor="888")
    client.post(f"/api/financeiro/titulos/{cancel['id']}/cancelar", json={"motivo": "x"}, headers=cen.h_admin)
    pagar = novo_titulo(client, cen, direcao="pagar", valor="7200")
    client.post(f"/api/financeiro/titulos/{pagar['id']}/aprovar", headers=cen.h_admin)
    cx = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    # 25.000 + 1.000 (reserva) + 19.300 − 7.200
    assert cx["saldo_gerencial"]["valor"] == "26000.00"
    assert (cx["entradas_abertas"]["valor"], cx["saidas_abertas"]["valor"]) == ("19300.00", "7200.00")
    assert cx["saldo_apos_titulos"]["valor"] == "38100.00"
    assert "Sem conciliação bancária" in cx["limites"][0]
    b = baixa(client, cen, rec["id"], "300").json()
    baixa(client, cen, pagar["id"], "200")
    cx = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    contas = {c["nome"]: c["saldo_atual"] for c in cx["contas"]}
    assert contas["Conta operacional"] == "25100.00"  # +300 −200
    assert cx["entradas_abertas"]["valor"] == "19000.00" and cx["saidas_abertas"]["valor"] == "7000.00"
    client.post(f"/api/financeiro/baixas/{b['id']}/estornar", json={"motivo": "erro"}, headers=cen.h_admin)
    cx = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    assert {c["nome"]: c["saldo_atual"] for c in cx["contas"]}["Conta operacional"] == "24800.00"
    assert client.get("/api/financeiro/caixa", headers=cen.h_leitura).status_code == 200


def test_caixa_permissao_comercial_nao_ve(client, db, cen):
    from tests.conftest import criar_usuario

    criar_usuario(db, "Comercial", email="vend@exemplo.com")
    h = auth(entrar(client, "vend").json()["access_token"])
    assert client.get("/api/financeiro/caixa", headers=h).status_code == 403
    assert client.get("/api/financeiro/hoje", headers=h).status_code == 200  # Comercial lê títulos (recebíveis)


def test_dashboards_aging_em_faixas(client, cen):
    novo_titulo(client, cen, valor="100", vencimento=cen.hoje + timedelta(days=3))
    novo_titulo(client, cen, valor="200", vencimento=cen.hoje - timedelta(days=10))
    novo_titulo(client, cen, valor="300", vencimento=cen.hoje - timedelta(days=45))
    novo_titulo(client, cen, valor="400", vencimento=cen.hoje - timedelta(days=75))
    novo_titulo(client, cen, valor="500", vencimento=cen.hoje - timedelta(days=120))
    novo_titulo(client, cen, valor="999", vencimento=cen.hoje - timedelta(days=10), rascunho=True)
    d = client.get("/api/financeiro/dashboards", headers=cen.h_fin).json()
    assert [(f["faixa"], f["valor"], f["quantidade"]) for f in d["aging_receber"]] == [
        ("a_vencer", "100.00", 1), ("1_30", "200.00", 1), ("31_60", "300.00", 1), ("61_90", "400.00", 1),
        ("90_mais", "500.00", 1)]
    assert d["caixa"]["saldo_gerencial"]["valor"] == "26000.00"
    assert all(f["valor"] == "0.00" for f in d["aging_pagar"])


def test_hoje_com_dados_da_demonstracao(client, db, admin, token_admin):
    semear(db, hoje())
    db.commit()
    r = client.get("/api/financeiro/hoje", headers=auth(token_admin))
    assert r.status_code == 200
    h = r.json()
    assert h["saldo_gerencial"]["valor"] == "25000.00"
    assert (h["recebiveis_vencidos"]["valor"], h["recebiveis_vencidos_qtd"]) == ("6000.00", 1)
    assert h["aprovacoes_pendentes"] == 1 and h["recorrencias_ativas"] == 1
    assert [f["empresa_nome"] for f in h["fila_cobranca"]] == ["Ponto Norte"]
    assert h["leitura"]["titulo"] == "Recebível vencido pede ação" and h["leitura"]["origem"] == "regras"
    assert "Ponto Norte" in h["leitura"]["evidencias"][0]["texto"]
    assert h["ia_ligada"] is False
    cx = client.get("/api/financeiro/caixa", headers=auth(token_admin)).json()
    # protótipo: 25.000 + 19.300 − 7.200 = 37.100
    assert (cx["entradas_abertas"]["valor"], cx["saidas_abertas"]["valor"], cx["saldo_apos_titulos"]["valor"]) == (
        "19300.00", "7200.00", "37100.00")


def test_hoje_contestado_sai_da_leitura_mas_fica_na_fila(client, cen):
    t = novo_titulo(client, cen, valor="6000", vencimento=cen.hoje - timedelta(days=7))
    client.post("/api/financeiro/cobrancas", headers=cen.h_admin, json={
        "assunto": "Contestação", "titulo_id": t["id"], "responsavel_id": cen.admin_id, "canal": "email",
        "situacao": "em_contestacao", "historico": "Cliente contesta a entrega."})
    h = client.get("/api/financeiro/hoje", headers=cen.h_admin).json()
    assert h["fila_cobranca"][0]["em_contestacao"] is True
    assert h["leitura"]["titulo"] == "Tudo em dia"
