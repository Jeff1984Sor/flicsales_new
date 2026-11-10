"""Títulos a receber e a pagar: listar (chips, vencido derivado, busca), criar, editar, confirmar, cancelar, detalhe."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.models import Auditoria
from app.modules.comercial.models import Funil, Oportunidade
from app.modules.financeiro.servico import preparar_recebiveis_do_ganho
from tests.financeiro.conftest import baixa, novo_titulo

URL = "/api/financeiro/titulos"


def test_criar_receber_nasce_aberto_e_auditado(client, db, cen):
    t = novo_titulo(client, cen, valor="1234.5", categoria_id=cen.receita.id, centro_custo_id=cen.centro.id)
    assert t["status"] == "aberto" and t["estado"] == "aberto"
    assert t["saldo"] == "1234.50" and t["valor_original"] == "1234.50"
    assert t["empresa_nome"] == "Ponto Norte" and t["categoria_nome"] == "Serviços prestados"
    assert t["aprovacao"] is None and t["confirmado_em"]
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "titulo.criar"))


def test_criar_em_rascunho(client, cen):
    assert novo_titulo(client, cen, rascunho=True)["status"] == "rascunho"


def test_pagar_nasce_pendente_e_aprovar_na_criacao_exige_alcada(client, cen):
    t = novo_titulo(client, cen, direcao="pagar")
    assert t["aprovacao"] == "pendente"
    corpo = {"direcao": "pagar", "empresa_id": cen.fornecedor.id, "descricao": "Aluguel", "vencimento": str(cen.hoje),
             "valor_original": "4200", "responsavel_id": cen.fin_id, "aprovacao": "aprovado"}
    assert client.post(URL, json=corpo, headers=cen.h_fin).status_code == 403
    r = client.post(URL, json=corpo, headers=cen.h_admin)
    assert r.json()["aprovacao"] == "aprovado" and r.json()["aprovado_por_nome"]


def test_criar_valida_valor_e_vinculos(client, cen):
    base = {"direcao": "receber", "empresa_id": cen.cliente.id, "descricao": "X", "vencimento": str(cen.hoje),
            "responsavel_id": cen.admin_id}
    r = client.post(URL, json={**base, "valor_original": "0"}, headers=cen.h_admin)
    assert r.status_code == 400 and r.json()["detail"] == "O valor deve ser positivo"
    r = client.post(URL, json={**base, "valor_original": "10", "empresa_id": 999}, headers=cen.h_admin)
    assert r.status_code == 400 and "cadastrado" in r.json()["detail"]
    r = client.post(URL, json={**base, "valor_original": "10", "descricao": "   "}, headers=cen.h_admin)
    assert r.status_code == 422
    r = client.post(URL, json={**base, "valor_original": "10", "competencia": "2026-13"}, headers=cen.h_admin)
    assert r.status_code == 422


def test_permissoes(client, cen):
    novo_titulo(client, cen)
    assert client.get(URL, headers=cen.h_leitura).status_code == 200
    corpo = {"direcao": "receber", "empresa_id": cen.cliente.id, "descricao": "X", "vencimento": str(cen.hoje),
             "valor_original": "10", "responsavel_id": cen.admin_id}
    assert client.post(URL, json=corpo, headers=cen.h_leitura).status_code == 403
    assert client.get(URL).status_code == 401


def test_listar_chips_vencido_derivado_e_busca(client, cen):
    vencido = novo_titulo(client, cen, descricao="Parcela 1/2", vencimento=cen.hoje - timedelta(days=7))
    novo_titulo(client, cen, descricao="Mensalidade", vencimento=cen.hoje + timedelta(days=5))
    novo_titulo(client, cen, descricao="Rascunho X", rascunho=True)
    novo_titulo(client, cen, direcao="pagar", descricao="Aluguel")
    r = client.get(URL, params={"direcao": "receber"}, headers=cen.h_admin).json()
    assert r["total"] == 3
    estados = {t["descricao"]: t["estado"] for t in r["itens"]}
    assert estados == {"Parcela 1/2": "vencido", "Mensalidade": "aberto", "Rascunho X": "rascunho"}
    assert next(t for t in r["itens"] if t["id"] == vencido["id"])["dias_atraso"] == 7
    venc = client.get(URL, params={"direcao": "receber", "estado": "vencido"}, headers=cen.h_admin).json()
    assert [t["id"] for t in venc["itens"]] == [vencido["id"]]
    busca = client.get(URL, params={"direcao": "receber", "q": "ponto norte"}, headers=cen.h_admin).json()
    assert busca["total"] == 3
    busca = client.get(URL, params={"direcao": "receber", "q": "mensal"}, headers=cen.h_admin).json()
    assert [t["descricao"] for t in busca["itens"]] == ["Mensalidade"]
    c = client.get(f"{URL}/contagens", params={"direcao": "receber"}, headers=cen.h_admin).json()
    assert c == {"todos": 3, "aberto": 2, "rascunho": 1, "parcial": 0, "liquidado": 0, "cancelado": 0, "vencido": 1}


def test_detalhe_com_origem_da_oportunidade_e_historico(client, db, cen):
    funil = Funil(nome="Serviços B2B")
    db.add(funil)
    db.flush()
    op = Oportunidade(titulo="Projeto de consultoria", funil_id=funil.id, empresa_id=cen.cliente.id,
                      responsavel_id=cen.admin_id, valor_unico=Decimal("24000"))
    db.add(op)
    db.flush()
    t = preparar_recebiveis_do_ganho(db, oportunidade_id=op.id, titulo=op.titulo, empresa_id=cen.cliente.id,
                                     valor=Decimal("24000"), condicao="Parcela única",
                                     primeiro_vencimento=cen.hoje, responsavel_id=cen.admin_id)[0]
    db.commit()
    client.post(f"{URL}/{t.id}/confirmar", headers=cen.h_admin)
    baixa(client, cen, t.id, "1000")
    d = client.get(f"{URL}/{t.id}", headers=cen.h_admin).json()
    assert d["origem"] == {"tipo": "oportunidade", "id": op.id,
                           "rotulo": f"Oportunidade #{op.id} — Projeto de consultoria"}
    assert [(b["valor"], b["estornada"]) for b in d["baixas"]] == [("1000.00", False)]
    assert d["tem_baixa_ativa"] and d["status"] == "parcial"
    manual = novo_titulo(client, cen)
    assert client.get(f"{URL}/{manual['id']}", headers=cen.h_admin).json()["origem"]["rotulo"] == "Lançamento manual"
    assert client.get(f"{URL}/9999", headers=cen.h_admin).status_code == 404


def test_editar_grava_so_o_enviado_e_recusa_com_baixa_ativa(client, cen):
    t = novo_titulo(client, cen, valor="1000", documento="NF 1")
    r = client.patch(f"{URL}/{t['id']}", json={"valor_original": "1500"}, headers=cen.h_admin)
    assert r.status_code == 200 and r.json()["saldo"] == "1500.00" and r.json()["documento"] == "NF 1"
    assert client.patch(f"{URL}/{t['id']}", json={"descricao": None}, headers=cen.h_admin).status_code == 400
    assert baixa(client, cen, t["id"], "100").status_code == 201
    r = client.patch(f"{URL}/{t['id']}", json={"valor_original": "2000"}, headers=cen.h_admin)
    assert r.status_code == 400 and r.json()["detail"] == "Estorne as baixas antes de editar o título"
    assert client.patch(f"{URL}/9999", json={}, headers=cen.h_admin).status_code == 404


def test_editar_aprovacao_exige_alcada(client, cen):
    t = novo_titulo(client, cen, direcao="pagar")
    assert client.patch(f"{URL}/{t['id']}", json={"aprovacao": "aprovado"}, headers=cen.h_fin).status_code == 403
    assert client.patch(f"{URL}/{t['id']}", json={"descricao": "Aluguel nov"}, headers=cen.h_fin).status_code == 200


def test_confirmar_rascunho_nao_e_baixa(client, cen):
    t = novo_titulo(client, cen, rascunho=True, valor="500")
    r = client.post(f"{URL}/{t['id']}/confirmar", headers=cen.h_admin)
    assert r.status_code == 200 and r.json()["status"] == "aberto" and r.json()["saldo"] == "500.00"
    r = client.post(f"{URL}/{t['id']}/confirmar", headers=cen.h_admin)
    assert r.status_code == 400 and "rascunho" in r.json()["detail"]
    assert client.post(f"{URL}/{t['id']}/confirmar", headers=cen.h_leitura).status_code == 403


def test_cancelar_exige_motivo_e_sem_baixa_ativa(client, db, cen):
    t = novo_titulo(client, cen)
    assert client.post(f"{URL}/{t['id']}/cancelar", json={"motivo": ""}, headers=cen.h_admin).status_code == 422
    r = client.post(f"{URL}/{t['id']}/cancelar", json={"motivo": "   "}, headers=cen.h_admin)
    assert r.status_code == 400
    b = baixa(client, cen, t["id"], "100").json()
    r = client.post(f"{URL}/{t['id']}/cancelar", json={"motivo": "Duplicado"}, headers=cen.h_admin)
    assert r.status_code == 400 and r.json()["detail"] == "Estorne as baixas antes de cancelar"
    client.post(f"/api/financeiro/baixas/{b['id']}/estornar", json={"motivo": "Lançado errado"}, headers=cen.h_admin)
    r = client.post(f"{URL}/{t['id']}/cancelar", json={"motivo": "Duplicado"}, headers=cen.h_admin)
    assert r.status_code == 200 and r.json()["status"] == "cancelado"
    assert r.json()["motivo_cancelamento"] == "Duplicado"
    assert client.patch(f"{URL}/{t['id']}", json={"descricao": "x"}, headers=cen.h_admin).status_code == 400
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "titulo.cancelar")).descricao.endswith("Duplicado")


def test_opcoes_para_formularios(client, cen):
    r = client.get(f"{URL}/opcoes", headers=cen.h_fin).json()
    assert {e["nome"] for e in r["empresas"]} == {"Ponto Norte", "Espaço Compartilhado"}
    assert [c["nome"] for c in r["contas"]] == ["Conta operacional", "Reserva"]
    assert r["centros_custo"] == [{"id": cen.centro.id, "nome": "Operação (OP)"}]
