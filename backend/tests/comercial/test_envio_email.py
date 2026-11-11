"""✉ Enviar e-mail no Comercial: Comunicações e Propostas (contrato de envio 11/2026). Nada sai da máquina: a fixture
`emails` captura o envio do core."""

from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.db import hoje
from app.core.models import Auditoria
from app.modules.comercial.models import Comunicacao, ModeloComunicacao, OportunidadeEvento, Proposta
from app.modules.nucleo.models import Pessoa
from tests.comercial.conftest import oportunidade

API = "/api/comercial"
EMAIL = {"para": ["paula@aurora.demo"], "assunto": "Próximos passos", "corpo": "Olá, Paula! Seguem os próximos passos."}


def _optout(db, nome="Paula Mendes", email="paula@aurora.demo"):
    p = db.scalar(select(Pessoa).where(Pessoa.nome == nome))
    p.email = email
    p.emails = [{"email": email, "tipo": "comercial", "principal": True}]
    p.permissoes_comunicacao = ["opt_out"]
    db.commit()
    return p


# ------------------------------------------------------------------------------------------- comunicações
def test_enviar_email_registra_comunicacao_historico_e_auditoria(client, demo, marina, emails):
    op = oportunidade(demo, "Projeto de consultoria")
    modelo = ModeloComunicacao(nome="Follow-up", canal="email", finalidade="follow_up", conteudo="Oi",
                               classificacao="geral")
    demo.add(modelo)
    demo.commit()
    r = client.post(f"{API}/comunicacoes/enviar-email", headers=marina,
                    json={**EMAIL, "cc": ["Gestor@Aurora.demo"], "oportunidade_id": op.id, "modelo_id": modelo.id})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True and out["enviado_para"] == ["paula@aurora.demo", "gestor@aurora.demo"]
    assert out["registro"].startswith("Comunicação #")
    assert emails == [(["paula@aurora.demo"], "Próximos passos", EMAIL["corpo"])]
    c = demo.scalar(select(Comunicacao).where(Comunicacao.titulo == "Próximos passos"))
    assert c.canal == "email" and c.oportunidade_id == op.id and c.empresa_id == op.empresa_id and c.data == hoje()
    assert c.conteudo == f"Para: paula@aurora.demo\nCc: gestor@aurora.demo\n\n{EMAIL['corpo']}"
    ev = demo.scalar(select(OportunidadeEvento).where(OportunidadeEvento.oportunidade_id == op.id)
                     .order_by(OportunidadeEvento.id.desc()))
    assert ev.texto == "E-mail enviado para paula@aurora.demo: Próximos passos"
    a = demo.scalar(select(Auditoria).where(Auditoria.acao == "comunicacao.enviar_email"))
    assert a.entidade_id == str(c.id)
    assert a.depois_json["para"] == ["paula@aurora.demo"] and a.depois_json["modelo_id"] == modelo.id
    # aparece na lista de comunicações
    assert any(x["id"] == c.id for x in client.get(f"{API}/comunicacoes", headers=marina).json())


def test_enviar_email_so_com_empresa(client, demo, gestor, emails):
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/comunicacoes/enviar-email", headers=gestor, json={**EMAIL, "empresa_id": op.empresa_id})
    assert r.status_code == 200
    c = demo.scalar(select(Comunicacao).where(Comunicacao.titulo == "Próximos passos"))
    assert c.empresa_id == op.empresa_id and c.oportunidade_id is None


def test_opt_out_bloqueia_e_nada_e_registrado(client, demo, marina, emails):
    _optout(demo)
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/comunicacoes/enviar-email", headers=marina, json={**EMAIL, "oportunidade_id": op.id})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Paula Mendes pediu para não receber comunicações (opt-out).")
    assert emails == [] and demo.scalar(select(Comunicacao).where(Comunicacao.titulo == "Próximos passos")) is None
    assert demo.scalar(select(Auditoria).where(Auditoria.acao == "comunicacao.enviar_email")) is None


def test_validacao_e_sem_smtp_fora_de_dev(client, demo, marina, monkeypatch, emails):
    op = oportunidade(demo, "Projeto de consultoria")
    url = f"{API}/comunicacoes/enviar-email"
    r = client.post(url, headers=marina, json={**EMAIL, "para": [], "oportunidade_id": op.id})
    assert r.status_code == 400 and "ao menos um destinatário" in r.json()["detail"]
    r = client.post(url, headers=marina, json={**EMAIL, "para": ["paula"], "oportunidade_id": op.id})
    assert r.status_code == 400 and "E-mail inválido" in r.json()["detail"]
    r = client.post(url, headers=marina, json={**EMAIL, "assunto": "", "oportunidade_id": op.id})
    assert r.status_code == 400 and "assunto" in r.json()["detail"]
    r = client.post(url, headers=marina, json={**EMAIL, "para": "paula@aurora.demo"})
    assert r.status_code == 422
    r = client.post(url, headers=marina, json={**EMAIL, "oportunidade_id": 9999})
    assert r.status_code == 400 and r.json()["detail"] == "Oportunidade não encontrada."
    r = client.post(url, headers=marina, json={**EMAIL, "oportunidade_id": op.id, "modelo_id": 9999})
    assert r.status_code == 400 and "Modelo de comunicação não encontrado" in r.json()["detail"]
    monkeypatch.setattr(settings, "ambiente", "prod")
    monkeypatch.setattr(settings, "smtp_host", None)
    r = client.post(url, headers=marina, json={**EMAIL, "oportunidade_id": op.id})
    assert r.status_code == 400
    assert r.json()["detail"] == "Configure o e-mail de envio em Configurações › E-mail ou em Minha conta."
    assert emails == []


def test_permissao_e_escopo_so_meus(client, demo, financeiro, leitura, marina, so_meus, emails):
    op_lucas = oportunidade(demo, "Expansão de operação")
    url = f"{API}/comunicacoes/enviar-email"
    assert client.post(url, headers=financeiro, json=EMAIL).status_code == 403
    assert client.post(url, headers=leitura, json=EMAIL).status_code == 403
    r = client.post(url, headers=marina, json={**EMAIL, "oportunidade_id": op_lucas.id})
    assert r.status_code == 400 and r.json()["detail"] == "Oportunidade não encontrada."
    r = client.post(url, headers=marina, json={**EMAIL, "empresa_id": op_lucas.empresa_id})
    assert r.status_code == 400 and "Vincule o e-mail" in r.json()["detail"]
    assert emails == []


# ------------------------------------------------------------------------------------------- propostas
def _proposta(client, cab, op_id, **kw):
    corpo = {"titulo": "Proposta consultoria", "oportunidade_id": op_id, "escopo": "Diagnóstico",
             "quantidade": "1", "preco_unitario": "24000", "desconto_pct": "0",
             "validade": (hoje() + timedelta(days=15)).isoformat(), "condicao": "2 parcelas", **kw}
    r = client.post(f"{API}/propostas", headers=cab, json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def test_enviar_proposta_marca_enviada_e_registra(client, demo, marina, emails):
    op = oportunidade(demo, "Projeto de consultoria")
    p = _proposta(client, marina, op.id)
    r = client.post(f"{API}/propostas/{p['id']}/enviar-email", headers=marina, json=EMAIL)
    assert r.status_code == 200, r.text
    reg = r.json()["registro"]
    assert "Proposta marcada como Enviada." in reg and f"PDF anexado: proposta-{p['id']}-v1.pdf." in reg
    demo.expire_all()
    assert demo.get(Proposta, p["id"]).status == "enviada"
    c = demo.scalar(select(Comunicacao).where(Comunicacao.titulo == "Próximos passos"))
    assert c.canal == "email" and c.oportunidade_id == op.id
    a = demo.scalar(select(Auditoria).where(Auditoria.acao == "proposta.enviar_email"))
    assert a.antes_json == {"status": "rascunho"} and a.depois_json["status"] == "enviada"
    assert a.depois_json["comunicacao_id"] == c.id
    assert len(emails) == 1
    # sem pedir PDF: o registro não fala dele
    r = client.post(f"{API}/propostas/{p['id']}/enviar-email", headers=marina, json={**EMAIL, "anexar_pdf": False})
    assert r.status_code == 200 and "PDF" not in r.json()["registro"] and "Status mantido: Enviada." in r.json()["registro"]


def test_proposta_com_desconto_sem_aprovacao_mantem_status(client, demo, marina, emails):
    op = oportunidade(demo, "Projeto de consultoria")
    p = _proposta(client, marina, op.id, desconto_pct="10", justificativa_desconto="Cliente estratégico")
    r = client.post(f"{API}/propostas/{p['id']}/enviar-email", headers=marina, json=EMAIL)
    assert r.status_code == 200 and "Status mantido: Rascunho." in r.json()["registro"]
    demo.expire_all()
    assert demo.get(Proposta, p["id"]).status == "rascunho"


def test_proposta_404_403_e_opt_out(client, demo, marina, financeiro, leitura, emails):
    op = oportunidade(demo, "Projeto de consultoria")
    p = _proposta(client, marina, op.id)
    assert client.post(f"{API}/propostas/9999/enviar-email", headers=marina, json=EMAIL).status_code == 404
    assert client.post(f"{API}/propostas/{p['id']}/enviar-email", headers=financeiro, json=EMAIL).status_code == 403
    assert client.post(f"{API}/propostas/{p['id']}/enviar-email", headers=leitura, json=EMAIL).status_code == 403
    _optout(demo)
    r = client.post(f"{API}/propostas/{p['id']}/enviar-email", headers=marina, json=EMAIL)
    assert r.status_code == 400 and "opt-out" in r.json()["detail"]
    demo.expire_all()
    assert demo.get(Proposta, p["id"]).status == "rascunho" and emails == []
