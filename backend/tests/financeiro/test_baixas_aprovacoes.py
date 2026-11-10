"""Baixas (parcial/total, validações), estornos (motivo, nunca apaga), aprovações (alçada) e concorrência do saldo."""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.models import Auditoria
from app.domain import RegraViolada
from app.modules.financeiro import operacoes as op
from app.modules.financeiro.models import Baixa, Titulo
from tests.financeiro.conftest import baixa, novo_titulo

T = "/api/financeiro/titulos"


def test_baixa_parcial_mantem_saldo_e_total_liquida(client, db, cen):
    t = novo_titulo(client, cen, valor="1000")
    r = baixa(client, cen, t["id"], "400")
    assert r.status_code == 201
    b = r.json()
    assert (b["valor"], b["conta_nome"], b["direcao"], b["estornada"]) == ("400.00", "Conta operacional", "receber",
                                                                          False)
    d = client.get(f"{T}/{t['id']}", headers=cen.h_admin).json()
    assert (d["saldo"], d["status"]) == ("600.00", "parcial")
    baixa(client, cen, t["id"], "600")
    d = client.get(f"{T}/{t['id']}", headers=cen.h_admin).json()
    assert (d["saldo"], d["status"]) == ("0.00", "liquidado")
    assert db.scalar(select(func.count(Auditoria.id)).where(Auditoria.acao == "baixa.registrar")) == 2


@pytest.mark.parametrize(("valor", "dias", "conta", "msg"), [
    ("0", 0, None, "Valor deve ser positivo e não superar o saldo"),
    ("-1", 0, None, "Valor deve ser positivo e não superar o saldo"),
    ("1000.01", 0, None, "Valor deve ser positivo e não superar o saldo"),
    ("10", 0, 9999, "Selecione uma conta cadastrada"),
    ("10", -31, None, "Data da baixa deve estar entre a data-base da conta e hoje"),
    ("10", 1, None, "Data da baixa deve estar entre a data-base da conta e hoje"),
])
def test_baixa_validacoes(client, cen, valor, dias, conta, msg):
    t = novo_titulo(client, cen, valor="1000")
    r = baixa(client, cen, t["id"], valor, data=cen.hoje + timedelta(days=dias), conta_id=conta)
    assert r.status_code == 400 and r.json()["detail"] == msg


def test_baixa_na_data_base_e_aceita(client, cen):
    t = novo_titulo(client, cen, valor="1000")
    assert baixa(client, cen, t["id"], "1000", data=cen.conta.data_base).status_code == 201


def test_baixa_em_rascunho_e_cancelado_e_recusada(client, cen):
    t = novo_titulo(client, cen, rascunho=True)
    assert "Confirme" in baixa(client, cen, t["id"], "10").json()["detail"]
    c = novo_titulo(client, cen)
    client.post(f"{T}/{c['id']}/cancelar", json={"motivo": "x"}, headers=cen.h_admin)
    assert baixa(client, cen, c["id"], "10").status_code == 400


def test_baixa_permissoes_e_404(client, cen):
    t = novo_titulo(client, cen)
    assert baixa(client, cen, t["id"], "10", headers=cen.h_leitura).status_code == 403
    assert baixa(client, cen, t["id"], "10", headers=cen.h_fin).status_code == 201
    assert baixa(client, cen, 9999, "10").status_code == 404


def test_pagar_so_baixa_aprovado_e_aprovar_exige_alcada(client, db, cen):
    t = novo_titulo(client, cen, direcao="pagar", valor="4200")
    r = baixa(client, cen, t["id"], "4200")
    assert r.status_code == 400 and r.json()["detail"] == "Aprove o pagamento no controle de aprovações primeiro"
    pend = client.get("/api/financeiro/aprovacoes", headers=cen.h_fin).json()
    assert [x["id"] for x in pend] == [t["id"]]
    assert client.post(f"{T}/{t['id']}/aprovar", headers=cen.h_fin).status_code == 403
    r = client.post(f"{T}/{t['id']}/aprovar", headers=cen.h_admin)
    assert r.status_code == 200 and r.json()["aprovacao"] == "aprovado"
    assert r.json()["aprovado_por_nome"] == "Usuário Gestor" and r.json()["aprovado_em"]
    assert client.post(f"{T}/{t['id']}/aprovar", headers=cen.h_admin).status_code == 400
    assert client.get("/api/financeiro/aprovacoes", headers=cen.h_fin).json() == []
    assert len(client.get("/api/financeiro/aprovacoes", params={"situacao": "aprovado"}, headers=cen.h_fin).json()) == 1
    assert baixa(client, cen, t["id"], "4200").status_code == 201
    receber = novo_titulo(client, cen)
    assert client.post(f"{T}/{receber['id']}/aprovar", headers=cen.h_admin).status_code == 400
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "titulo.aprovar")).usuario_nome == "Usuário Gestor"


def test_estorno_exige_motivo_preserva_baixa_e_devolve_saldo(client, db, cen):
    t = novo_titulo(client, cen, valor="1000")
    b1 = baixa(client, cen, t["id"], "400").json()
    baixa(client, cen, t["id"], "600")
    url = f"/api/financeiro/baixas/{b1['id']}/estornar"
    assert client.post(url, json={"motivo": "  "}, headers=cen.h_admin).status_code == 400
    assert client.post(url, json={"motivo": "x"}, headers=cen.h_leitura).status_code == 403
    r = client.post(url, json={"motivo": "Valor lançado na conta errada"}, headers=cen.h_fin)
    assert r.status_code == 200
    e = r.json()
    assert e["estornada"] and e["estorno_motivo"] == "Valor lançado na conta errada" and e["estornada_por_nome"]
    d = client.get(f"{T}/{t['id']}", headers=cen.h_admin).json()
    assert (d["saldo"], d["status"]) == ("400.00", "parcial")
    assert len(d["baixas"]) == 2  # nunca apaga
    assert client.post(url, json={"motivo": "de novo"}, headers=cen.h_admin).json()["detail"] == \
        "Esta baixa já foi estornada."
    assert db.scalar(select(func.count(Baixa.id))) == 2
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "baixa.estornar"))
    assert client.post("/api/financeiro/baixas/9999/estornar", json={"motivo": "x"},
                       headers=cen.h_admin).status_code == 404


def test_estornar_todas_volta_para_aberto(client, cen):
    t = novo_titulo(client, cen, valor="1000")
    b = baixa(client, cen, t["id"], "1000").json()
    client.post(f"/api/financeiro/baixas/{b['id']}/estornar", json={"motivo": "erro"}, headers=cen.h_admin)
    d = client.get(f"{T}/{t['id']}", headers=cen.h_admin).json()
    assert (d["saldo"], d["status"], d["tem_baixa_ativa"]) == ("1000.00", "aberto", False)


def test_trilha_de_baixas_filtra(client, cen):
    t = novo_titulo(client, cen, valor="1000")
    b = baixa(client, cen, t["id"], "100").json()
    baixa(client, cen, t["id"], "200")
    client.post(f"/api/financeiro/baixas/{b['id']}/estornar", json={"motivo": "erro"}, headers=cen.h_admin)
    url = "/api/financeiro/baixas"
    assert client.get(url, headers=cen.h_fin).json()["total"] == 2
    est = client.get(url, params={"situacao": "estornada"}, headers=cen.h_fin).json()["itens"]
    assert [x["id"] for x in est] == [b["id"]]
    assert client.get(url, params={"q": "ponto"}, headers=cen.h_fin).json()["total"] == 2
    assert client.get(url, params={"q": "zzz"}, headers=cen.h_fin).json()["total"] == 0
    assert len(client.get(f"{T}/{t['id']}/baixas", headers=cen.h_fin).json()) == 2


def test_duas_baixas_simultaneas_nao_estouram_o_saldo(client, cen):
    """A sessão B leu o título ANTES da baixa da sessão A (saldo 100 em memória). A valida 70 e grava; B também valida
    70 contra o saldo velho, mas o UPDATE condicional (saldo >= valor) não casa e B é recusada."""
    t = novo_titulo(client, cen, valor="100")
    with SessionLocal() as a, SessionLocal() as b:
        ta, tb = a.get(Titulo, t["id"]), b.get(Titulo, t["id"])
        assert ta.saldo == tb.saldo == Decimal("100.00")
        kw = dict(valor="70", data=cen.hoje, conta_id=cen.conta.id, forma="pix", referencia_comprovante=None,
                  observacao=None, usuario=None, hoje=cen.hoje)
        op.registrar_baixa(a, titulo=ta, **kw)
        a.commit()
        assert tb.saldo == Decimal("100.00")  # B continua com a leitura velha
        with pytest.raises(RegraViolada, match="não superar o saldo"):
            op.registrar_baixa(b, titulo=tb, **kw)
    with SessionLocal() as s:
        final = s.get(Titulo, t["id"])
        assert final.saldo == Decimal("30.00") and final.status == "parcial"
        assert s.scalar(select(func.count(Baixa.id)).where(Baixa.titulo_id == t["id"])) == 1


def test_debito_condicional_recusa_valor_acima_do_saldo_no_banco(client, cen):
    t = novo_titulo(client, cen, valor="100")
    with SessionLocal() as s:
        assert op.debitar_saldo(s, t["id"], Decimal("60"))
        assert not op.debitar_saldo(s, t["id"], Decimal("60"))  # sobrariam -20: o banco não casa a condição
        assert op.debitar_saldo(s, t["id"], Decimal("40"))
        s.commit()
        assert s.get(Titulo, t["id"]).saldo == Decimal("0.00")
