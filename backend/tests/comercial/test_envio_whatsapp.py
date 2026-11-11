"""WhatsApp no Comercial: Comunicações e Propostas (contrato proposta + WhatsApp 11/2026, parte B3). A Evolution é
FALSA (tests/evolution_falsa.py): nada sai da máquina."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.db import hoje
from app.core.models import Auditoria
from app.modules.comercial import servico as sv
from app.modules.comercial.models import Comunicacao, ModeloComunicacao, OportunidadeEvento, Proposta
from app.modules.nucleo.models import Pessoa
from tests import evolution_falsa as ef
from tests.comercial.conftest import oportunidade

API = "/api/comercial"
ZAP = {"para": ["(11) 99999-0000"], "texto": "Olá, Paula! Seguem os próximos passos."}


@pytest.fixture
def evo():
    with ef.instalada() as f:
        yield f


@pytest.fixture
def conectado(demo, evo):
    ef.conectar(demo)
    return evo


def _optout(db, nome="Paula Mendes", fone="(11) 99999-0000"):
    p = db.scalar(select(Pessoa).where(Pessoa.nome == nome))
    p.telefones = [{"numero": fone, "tipo": "whatsapp", "principal": True}]
    p.permissoes_comunicacao = ["opt_out"]
    db.commit()
    return p


def _ultima(db) -> Comunicacao | None:
    return db.scalar(select(Comunicacao).where(Comunicacao.canal == "whatsapp").order_by(Comunicacao.id.desc()))


# ------------------------------------------------------------------------------------------- comunicações
def test_enviar_whatsapp_registra_comunicacao_evento_e_auditoria(client, demo, marina, conectado):
    op = oportunidade(demo, "Projeto de consultoria")
    modelo = ModeloComunicacao(nome="Zap", canal="whatsapp", finalidade="follow_up", conteudo="Oi",
                               classificacao="comercial")
    demo.add(modelo)
    demo.commit()
    r = client.post(f"{API}/comunicacoes/enviar-whatsapp", headers=marina,
                    json={**ZAP, "oportunidade_id": op.id, "modelo_id": modelo.id})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True and out["enviado_para"] == ["5511999990000"]
    assert out["registro"].startswith("Comunicação #") and out["registro"].endswith("(WhatsApp).")
    assert conectado.enviados == [{"number": "5511999990000", "text": f"{ZAP['texto']}\n\n— Marina Costa"}]
    c = _ultima(demo)
    assert c.oportunidade_id == op.id and c.empresa_id == op.empresa_id and c.data == hoje()
    assert c.conteudo.startswith(f"Para: +55 (11) 99999-0000\n\n{ZAP['texto']}\n\n— ")
    ev = demo.scalar(select(OportunidadeEvento).where(OportunidadeEvento.oportunidade_id == op.id)
                     .order_by(OportunidadeEvento.id.desc()))
    assert ev.texto == "WhatsApp enviado para +55 (11) 99999-0000"
    a = demo.scalar(select(Auditoria).where(Auditoria.acao == "comunicacao.enviar_whatsapp"))
    assert a.entidade_id == str(c.id) and a.depois_json["para"] == ["5511999990000"]
    assert ef.CHAVE not in str(a.depois_json)


def test_validacao_opt_out_e_sem_whatsapp(client, demo, marina, evo):
    op = oportunidade(demo, "Projeto de consultoria")
    antes = _ultima(demo)
    url = f"{API}/comunicacoes/enviar-whatsapp"
    r = client.post(url, headers=marina, json={**ZAP, "oportunidade_id": op.id})
    assert r.status_code == 400 and r.json()["detail"] == "Configure o WhatsApp em Núcleo › Integrações."
    ef.conectar(demo)
    r = client.post(url, headers=marina, json={**ZAP, "para": [], "oportunidade_id": op.id})
    assert r.status_code == 400 and "ao menos um telefone" in r.json()["detail"]
    r = client.post(url, headers=marina, json={**ZAP, "para": ["123"], "oportunidade_id": op.id})
    assert r.status_code == 400 and "Telefone inválido para WhatsApp" in r.json()["detail"]
    r = client.post(url, headers=marina, json={**ZAP, "texto": " ", "oportunidade_id": op.id})
    assert r.status_code == 400 and "Escreva a mensagem" in r.json()["detail"]
    r = client.post(url, headers=marina, json={**ZAP, "para": "11999990000"})
    assert r.status_code == 422
    r = client.post(url, headers=marina, json={**ZAP, "oportunidade_id": 9999})
    assert r.status_code == 400 and r.json()["detail"] == "Oportunidade não encontrada."
    _optout(demo)
    r = client.post(url, headers=marina, json={**ZAP, "para": ["+55 11 99999-0000"], "oportunidade_id": op.id})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Paula Mendes pediu para não receber comunicações (opt-out).")
    evo_falha = evo
    evo_falha.status_envio = 400
    r = client.post(url, headers=marina, json={**ZAP, "para": ["21 98888-7777"], "oportunidade_id": op.id})
    assert r.status_code == 400 and r.json()["detail"].startswith("Não foi possível enviar pelo WhatsApp:")
    assert ef.CHAVE not in r.text
    assert _ultima(demo) is antes  # nada registrado
    assert demo.scalar(select(Auditoria).where(Auditoria.acao == "comunicacao.enviar_whatsapp")) is None


def test_permissao_e_escopo_so_meus(client, demo, financeiro, leitura, marina, so_meus, conectado):
    op_lucas = oportunidade(demo, "Expansão de operação")
    url = f"{API}/comunicacoes/enviar-whatsapp"
    assert client.post(url, headers=financeiro, json=ZAP).status_code == 403
    assert client.post(url, headers=leitura, json=ZAP).status_code == 403
    r = client.post(url, headers=marina, json={**ZAP, "oportunidade_id": op_lucas.id})
    assert r.status_code == 400 and r.json()["detail"] == "Oportunidade não encontrada."
    r = client.post(url, headers=marina, json={**ZAP, "empresa_id": op_lucas.empresa_id})
    assert r.status_code == 400 and "Vincule a mensagem" in r.json()["detail"]
    assert conectado.enviados == []


# ------------------------------------------------------------------------------------------- propostas
def _proposta(client, cab, op_id, **kw):
    corpo = {"titulo": "Proposta consultoria", "oportunidade_id": op_id, "escopo": "Diagnóstico",
             "quantidade": "1", "preco_unitario": "24000", "desconto_pct": "0",
             "validade": (hoje() + timedelta(days=15)).isoformat(), "condicao": "2 parcelas", **kw}
    r = client.post(f"{API}/propostas", headers=cab, json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def test_proposta_por_whatsapp_manda_pdf_e_marca_enviada(client, demo, marina, conectado, monkeypatch):
    monkeypatch.setattr(sv, "gerar_pdf_proposta", lambda db, p: b"%PDF-falso")
    op = oportunidade(demo, "Projeto de consultoria")
    p = _proposta(client, marina, op.id)
    r = client.post(f"{API}/propostas/{p['id']}/enviar-whatsapp", headers=marina, json=ZAP)
    assert r.status_code == 200, r.text
    reg = r.json()["registro"]
    assert "Proposta marcada como Enviada." in reg and f"PDF enviado como documento: proposta-{p['id']}-v1.pdf." in reg
    doc = conectado.enviados[0]
    assert doc["mediatype"] == "document" and doc["mimetype"] == "application/pdf" and doc["media"] == "JVBERi1mYWxzbw=="
    assert doc["fileName"] == f"proposta-{p['id']}-v1.pdf" and doc["caption"].startswith(ZAP["texto"])
    demo.expire_all()
    assert demo.get(Proposta, p["id"]).status == "enviada"
    c = _ultima(demo)
    assert c.oportunidade_id == op.id and c.titulo == "Proposta Proposta consultoria v1"
    a = demo.scalar(select(Auditoria).where(Auditoria.acao == "proposta.enviar_whatsapp"))
    assert a.antes_json == {"status": "rascunho"} and a.depois_json["status"] == "enviada"
    assert a.depois_json["comunicacao_id"] == c.id and a.depois_json["pdf"] is True
    # sem PDF: só texto
    r = client.post(f"{API}/propostas/{p['id']}/enviar-whatsapp", headers=marina, json={**ZAP, "anexar_pdf": False})
    assert r.status_code == 200 and "PDF" not in r.json()["registro"]
    assert conectado.enviados[1].keys() == {"number", "text"}


def test_proposta_com_desconto_mantem_status(client, demo, marina, conectado, monkeypatch):
    monkeypatch.setattr(sv, "gerar_pdf_proposta", lambda db, p: b"%PDF-falso")
    op = oportunidade(demo, "Projeto de consultoria")
    p = _proposta(client, marina, op.id, desconto_pct="10", justificativa_desconto="Cliente estratégico")
    r = client.post(f"{API}/propostas/{p['id']}/enviar-whatsapp", headers=marina, json=ZAP)
    assert r.status_code == 200 and "Status mantido: Rascunho." in r.json()["registro"]


def test_proposta_404_403_e_opt_out(client, demo, marina, financeiro, leitura, conectado, monkeypatch):
    monkeypatch.setattr(sv, "gerar_pdf_proposta", lambda db, p: b"%PDF-falso")
    op = oportunidade(demo, "Projeto de consultoria")
    p = _proposta(client, marina, op.id)
    url = f"{API}/propostas/{p['id']}/enviar-whatsapp"
    assert client.post(f"{API}/propostas/9999/enviar-whatsapp", headers=marina, json=ZAP).status_code == 404
    assert client.post(url, headers=financeiro, json=ZAP).status_code == 403
    assert client.post(url, headers=leitura, json=ZAP).status_code == 403
    _optout(demo)
    r = client.post(url, headers=marina, json=ZAP)
    assert r.status_code == 400 and "opt-out" in r.json()["detail"]
    demo.expire_all()
    assert demo.get(Proposta, p["id"]).status == "rascunho" and conectado.enviados == []
