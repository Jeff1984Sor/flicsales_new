"""Critério de aceite (parte comercial): oportunidade com empresa nova pelo nome → próxima ação → ganho em 2 parcelas
→ 2 títulos em RASCUNHO → ganhar de novo dá 400 e não duplica."""

from datetime import timedelta

from sqlalchemy import select

from app.core.db import hoje
from app.modules.comercial.models import OportunidadeEvento
from app.modules.financeiro.models import Titulo
from app.modules.nucleo.models import Empresa
from tests.comercial.conftest import funil_demo


def test_da_oportunidade_ao_recebivel_em_rascunho(client, demo, marina):
    db = demo
    funil = funil_demo(db)

    # 1. oportunidade com empresa NOVA, informada só pelo nome
    r = client.post("/api/comercial/oportunidades", headers=marina, json={
        "titulo": "Implantação Boreal", "funil_id": funil.id, "empresa_nome": "Boreal Engenharia",
        "valor_unico": "30000", "interesse": "Alto"})
    assert r.status_code == 201, r.text
    op = r.json()
    assert op["etapa_nome"] == "Entrada" and op["resultado"] == "aberta"
    empresa = db.scalar(select(Empresa).where(Empresa.nome == "Boreal Engenharia"))
    assert empresa is not None and empresa.papel_prospect and op["empresa_id"] == empresa.id

    # 2. registrar a próxima ação
    prazo = (hoje() + timedelta(days=2)).isoformat()
    r = client.patch(f"/api/comercial/oportunidades/{op['id']}", headers=marina,
                     json={"proxima_acao": "Enviar contrato", "proxima_acao_prazo": prazo})
    assert r.status_code == 200, r.text
    assert r.json()["proxima_acao"] == "Enviar contrato"

    # 3. ganhar com 2 parcelas
    venc = (hoje() + timedelta(days=10)).isoformat()
    corpo = {"valor": "30000", "condicao": "2 parcelas iguais", "primeiro_vencimento": venc}
    r = client.post(f"/api/comercial/oportunidades/{op['id']}/ganhar", headers=marina, json=corpo)
    assert r.status_code == 200, r.text
    ganho = r.json()
    assert ganho["oportunidade"]["resultado"] == "ganha"
    assert ganho["mensagem"] == "Venda ganha. Revise os recebíveis antes de confirmar."
    assert len(ganho["recebiveis"]) == 2

    # 4. dois títulos a receber em rascunho, da empresa certa, sem tocar no caixa
    db.expire_all()
    titulos = list(db.scalars(select(Titulo).where(Titulo.origem_oportunidade_id == op["id"]).order_by(Titulo.parcela)))
    assert [(t.parcela, t.status, t.direcao, str(t.valor_original)) for t in titulos] == [
        (1, "rascunho", "receber", "15000.00"), (2, "rascunho", "receber", "15000.00")]
    assert all(t.empresa_id == empresa.id for t in titulos)

    # 5. ganhar de novo: 400 e nada duplicado
    r = client.post(f"/api/comercial/oportunidades/{op['id']}/ganhar", headers=marina, json=corpo)
    assert r.status_code == 400
    assert r.json()["detail"] == "Esta venda já foi processada"
    assert db.scalar(select(Titulo.id).where(Titulo.origem_oportunidade_id == op["id"], Titulo.parcela == 3)) is None
    assert len(list(db.scalars(select(Titulo).where(Titulo.origem_oportunidade_id == op["id"])))) == 2

    # histórico compartilhado registra o caminho (o motor de automações lê estes tipos)
    tipos = [e.tipo for e in db.scalars(select(OportunidadeEvento).where(
        OportunidadeEvento.oportunidade_id == op["id"]).order_by(OportunidadeEvento.id))]
    assert tipos == ["criada", "proxima_acao", "ganha"]
