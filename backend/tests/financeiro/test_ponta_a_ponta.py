"""Critério de aceite do CLAUDE.md, lado financeiro:
venda ganha prepara recebíveis em rascunho (sem duplicar) → confirmar a 1ª parcela → recebimento parcial →
saldo do título e do caixa conferem → estornar → valores voltam → auditoria registrou tudo."""

from decimal import Decimal

from sqlalchemy import select

from app.core.models import Auditoria
from app.modules.comercial.models import Funil, Oportunidade
from app.modules.financeiro.servico import preparar_recebiveis_do_ganho
from tests.financeiro.conftest import baixa


def test_venda_ganha_ate_estorno(client, db, cen):
    funil = Funil(nome="Serviços B2B")
    db.add(funil)
    db.flush()
    op = Oportunidade(titulo="Projeto de consultoria", funil_id=funil.id, empresa_id=cen.cliente.id,
                      responsavel_id=cen.admin_id, valor_unico=Decimal("24000"))
    db.add(op)
    db.flush()
    args = dict(oportunidade_id=op.id, titulo=op.titulo, empresa_id=cen.cliente.id, valor=Decimal("24000"),
                condicao="2 parcelas iguais", primeiro_vencimento=cen.hoje, responsavel_id=cen.admin_id)
    preparar_recebiveis_do_ganho(db, **args)
    db.commit()
    preparar_recebiveis_do_ganho(db, **args)  # ganhar de novo não duplica
    db.commit()

    caixa0 = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    assert caixa0["saldo_gerencial"]["valor"] == "26000.00"
    assert caixa0["entradas_abertas"]["valor"] == "0.00"  # rascunho não compõe projeção: venda ≠ caixa

    lista = client.get("/api/financeiro/titulos", params={"origem_oportunidade_id": op.id},
                       headers=cen.h_fin).json()
    assert lista["total"] == 2
    assert [(t["parcela"], t["status"], t["valor_original"]) for t in lista["itens"]] == [
        (1, "rascunho", "12000.00"), (2, "rascunho", "12000.00")]
    p1 = lista["itens"][0]

    r = client.post(f"/api/financeiro/titulos/{p1['id']}/confirmar", headers=cen.h_fin)
    assert r.json()["status"] == "aberto" and r.json()["saldo"] == "12000.00"
    caixa1 = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    assert caixa1["saldo_gerencial"]["valor"] == "26000.00"  # confirmar não é baixa
    assert caixa1["entradas_abertas"]["valor"] == "12000.00"

    b = baixa(client, cen, p1["id"], "5000", headers=cen.h_fin)
    assert b.status_code == 201
    d = client.get(f"/api/financeiro/titulos/{p1['id']}", headers=cen.h_fin).json()
    assert (d["status"], d["saldo"]) == ("parcial", "7000.00")
    assert d["origem"]["rotulo"] == f"Oportunidade #{op.id} — Projeto de consultoria"
    caixa2 = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    assert caixa2["saldo_gerencial"]["valor"] == "31000.00"
    assert {c["nome"]: c["saldo_atual"] for c in caixa2["contas"]}["Conta operacional"] == "30000.00"
    assert caixa2["entradas_abertas"]["valor"] == "7000.00"

    r = client.post(f"/api/financeiro/baixas/{b.json()['id']}/estornar", json={"motivo": "Depósito não identificado"},
                    headers=cen.h_fin)
    assert r.status_code == 200
    d = client.get(f"/api/financeiro/titulos/{p1['id']}", headers=cen.h_fin).json()
    assert (d["status"], d["saldo"]) == ("aberto", "12000.00")
    assert [x["estornada"] for x in d["baixas"]] == [True]  # o movimento fica no histórico
    caixa3 = client.get("/api/financeiro/caixa", headers=cen.h_fin).json()
    assert caixa3["saldo_gerencial"]["valor"] == "26000.00" and caixa3["entradas_abertas"]["valor"] == "12000.00"

    acoes = [a.acao for a in db.scalars(select(Auditoria).order_by(Auditoria.id))]
    for acao in ("titulo.confirmar", "baixa.registrar", "baixa.estornar"):
        assert acao in acoes
    estorno = db.scalar(select(Auditoria).where(Auditoria.acao == "baixa.estornar"))
    assert "Depósito não identificado" in estorno.descricao and estorno.usuario_nome == "Usuário Financeiro"
