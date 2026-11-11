"""SMTP por usuário (/auth/me/email, /auth/me/envio), escolha do servidor em app.core.email e o serviço único
app.core.envio.enviar_por_usuario (contrato de envio 11/2026). Nenhum e-mail de verdade sai: `smtp_falso`."""

import smtplib

import pytest

from app.core import email as mail
from app.core import envio, segredos
from app.core.config import settings
from app.core.models import Auditoria, ConfigEmail, ConfigEmailUsuario
from app.domain import RegraViolada
from app.modules.nucleo.models import Empresa, Pessoa
from tests.conftest import auth, criar_usuario, entrar

URL = "/api/auth/me/email"
SENHA_SMTP = "SenhaSmtp#9876"
FORM = {"remetente_nome": "Marina Souza", "remetente_email": "marina@minhaempresa.com", "smtp_host": "smtp.marina.com",
        "smtp_porta": 587, "smtp_usuario": "marina@minhaempresa.com", "smtp_senha": SENHA_SMTP, "ativo": True}


def _logar(client, db, login="marina", perfil="Comercial"):
    u = criar_usuario(db, perfil, email=f"{login}@exemplo.com", login=login)
    return u, auth(entrar(client, login).json()["access_token"])


def _org(db, host="smtp.org.com"):
    db.add(ConfigEmail(id=1, remetente_nome="Flic Org", remetente_email="contato@org.com", smtp_host=host,
                       smtp_porta=587, smtp_usuario="org", smtp_senha_cifrada=segredos.cifrar_texto("org-senha"),
                       copia_padrao=[]))
    db.commit()


# ------------------------------------------------------------------------------------------- /auth/me/email
def test_email_do_usuario_salvar_ler_remover_sem_devolver_senha(client, db):
    u, h = _logar(client, db)
    assert client.get(URL).status_code == 401
    r = client.get(URL, headers=h)
    assert r.status_code == 200 and r.json() == {
        "configurado": False, "ativo": False, "remetente_nome": None, "remetente_email": None, "smtp_host": None,
        "smtp_porta": 587, "smtp_usuario": None, "senha_final": None}

    r = client.put(URL, json=FORM, headers=h)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["configurado"] and corpo["ativo"] and corpo["smtp_host"] == "smtp.marina.com"
    assert corpo["senha_final"] == "••••••9876" and SENHA_SMTP not in r.text and "smtp_senha" not in corpo
    assert SENHA_SMTP not in client.get(URL, headers=h).text
    c = db.get(ConfigEmailUsuario, u.id)
    assert c.smtp_senha_cifrada and SENHA_SMTP.encode() not in c.smtp_senha_cifrada
    a = db.query(Auditoria).filter_by(acao="email_usuario.alterar").one()
    assert "senha" in a.descricao and SENHA_SMTP not in str(a.depois_json) and "smtp_senha_cifrada" not in a.depois_json

    # sem senha = mantém a salva; update grava o que veio
    r = client.put(URL, json={**FORM, "smtp_senha": "", "smtp_porta": 465}, headers=h)
    assert r.json()["smtp_porta"] == 465 and r.json()["senha_final"] == "••••••9876"
    db.expire_all()
    assert segredos.decifrar_texto(db.get(ConfigEmailUsuario, u.id).smtp_senha_cifrada) == SENHA_SMTP

    r = client.delete(URL, headers=h)
    assert r.status_code == 200 and r.json()["configurado"] is False
    assert db.query(Auditoria).filter_by(acao="email_usuario.remover").count() == 1
    assert client.delete(URL, headers=h).status_code == 404


def test_email_do_usuario_validacao(client, db):
    _, h = _logar(client, db)
    r = client.put(URL, json={**FORM, "remetente_email": "nao-e-email"}, headers=h)
    assert r.status_code == 422
    r = client.put(URL, json={**FORM, "smtp_porta": 0}, headers=h)
    assert r.status_code == 422
    r = client.put(URL, json={k: v for k, v in FORM.items() if k != "smtp_host"}, headers=h)
    assert r.status_code == 422


def test_cada_um_ve_so_o_seu(client, db):
    _, h_marina = _logar(client, db)
    _, h_lucas = _logar(client, db, "lucas")
    client.put(URL, json=FORM, headers=h_marina)
    assert client.get(URL, headers=h_lucas).json()["configurado"] is False


def test_testar_conexao_faz_login_e_nao_envia(client, db, smtp_falso):
    _, h = _logar(client, db)
    r = client.post(f"{URL}/testar", headers=h)
    assert r.status_code == 400 and "Salve o e-mail de envio" in r.json()["detail"]
    client.put(URL, json=FORM, headers=h)
    r = client.post(f"{URL}/testar", headers=h)
    assert r.status_code == 200 and r.json() == {"ok": True, "mensagem": "Conexão com o servidor de e-mail confirmada."}
    assert smtp_falso.logins == [("smtp.marina.com", 587, "marina@minhaempresa.com", SENHA_SMTP)]
    assert smtp_falso.enviados == []
    # formulário ainda não salvo (senha vazia = a salva)
    r = client.post(f"{URL}/testar", json={**FORM, "smtp_host": "smtp.outro.com", "smtp_senha": ""}, headers=h)
    assert r.json()["ok"] and smtp_falso.logins[-1] == ("smtp.outro.com", 587, "marina@minhaempresa.com", SENHA_SMTP)
    smtp_falso.falha = smtplib.SMTPAuthenticationError(535, b"5.7.8 senha errada SenhaSmtp#9876")
    r = client.post(f"{URL}/testar", headers=h)
    assert r.json()["ok"] is False and "usuário ou a senha" in r.json()["mensagem"]
    assert SENHA_SMTP not in r.text


# ------------------------------------------------------------------------------------------- /auth/me/envio
def test_me_envio_diz_por_onde_sai(client, db, monkeypatch):
    _, h = _logar(client, db)
    assert client.get("/api/auth/me/envio").status_code == 401
    assert client.get("/api/auth/me/envio", headers=h).json() == {
        "pode_enviar": True, "via": "outbox", "remetente": settings.smtp_from,
        "whatsapp": {"pode_enviar": False, "numero": None}}  # WhatsApp (Evolution) não conectado
    monkeypatch.setattr(settings, "ambiente", "prod")
    monkeypatch.setattr(settings, "smtp_host", None)
    assert client.get("/api/auth/me/envio", headers=h).json() == {"pode_enviar": False, "via": None, "remetente": None,
                                                                   "whatsapp": {"pode_enviar": False, "numero": None}}
    _org(db)
    r = client.get("/api/auth/me/envio", headers=h).json()
    assert (r["pode_enviar"], r["via"], r["remetente"]) == (True, "organizacao", "Flic Org <contato@org.com>")
    client.put(URL, json=FORM, headers=h)
    r = client.get("/api/auth/me/envio", headers=h).json()
    assert (r["via"], r["remetente"]) == ("usuario", "Marina Souza <marina@minhaempresa.com>")
    client.put(URL, json={**FORM, "ativo": False}, headers=h)  # inativo: volta para a organização
    assert client.get("/api/auth/me/envio", headers=h).json()["via"] == "organizacao"


# ------------------------------------------------------------------------------------------- app.core.email
def test_usuario_com_smtp_proprio_sai_com_from_dele(client, db, smtp_falso):
    _org(db)
    u, h = _logar(client, db)
    client.put(URL, json=FORM, headers=h)
    db.refresh(u)
    assert mail.enviar(["cliente@x.com"], "Oi", "Corpo", db=db, remetente=u)
    host, msg, para = smtp_falso.enviados[-1]
    assert host == "smtp.marina.com" and msg["From"] == "Marina Souza <marina@minhaempresa.com>"
    assert msg["Reply-To"] is None and para == ["cliente@x.com"]
    assert smtp_falso.logins[-1][2:] == ("marina@minhaempresa.com", SENHA_SMTP)
    # e-mail do sistema continua saindo pela organização
    assert mail.enviar(["x@x.com"], "Senha", "Link", db=db, assinar=True)
    host, msg, _ = smtp_falso.enviados[-1]
    assert host == "smtp.org.com" and msg["From"] == "Flic Org <contato@org.com>"


def test_sem_smtp_proprio_sai_pela_organizacao_com_reply_to(client, db, smtp_falso):
    _org(db)
    u, _ = _logar(client, db)
    assert mail.enviar(["cliente@x.com"], "Oi", "Corpo", db=db, remetente=u, cc=["c@x.com"])
    host, msg, para = smtp_falso.enviados[-1]
    assert host == "smtp.org.com" and msg["From"] == "Flic Org <contato@org.com>"
    assert msg["Reply-To"] == f"{u.nome} <marina@exemplo.com>" and para == ["cliente@x.com", "c@x.com"]


# ------------------------------------------------------------------------------------------- app.core.envio
def test_enviar_por_usuario_valida_e_bloqueia_opt_out(db, smtp_falso):
    _org(db)
    u = criar_usuario(db, "Comercial", email="marina@exemplo.com", login="marina")
    emp = Empresa(nome="Aurora")
    db.add(emp)
    db.flush()
    db.add(Pessoa(nome="Paula Mendes", empresa_id=emp.id, email="paula@aurora.com.br",
                  emails=[{"email": "paula@aurora.com.br", "tipo": "comercial", "principal": True},
                          {"email": "paula.casa@x.com", "tipo": "pessoal", "principal": False}],
                  permissoes_comunicacao=["opt_out"]))
    db.add(Pessoa(nome="Rafael", empresa_id=emp.id, email="rafael@aurora.com.br", permissoes_comunicacao=["email"]))
    db.commit()
    with pytest.raises(RegraViolada, match=r"^Paula Mendes pediu para não receber comunicações \(opt-out\)"):
        envio.enviar_por_usuario(db, u, para=["rafael@aurora.com.br"], cc=["Paula.Casa@x.com"], assunto="Oi",
                                 corpo="Olá")
    assert smtp_falso.enviados == []
    with pytest.raises(RegraViolada, match="ao menos um destinatário"):
        envio.enviar_por_usuario(db, u, para=[], assunto="Oi", corpo="Olá")
    m = envio.enviar_por_usuario(db, u, para=["Rafael@Aurora.com.br"], assunto="Oi", corpo="Olá")
    assert m.para == ["rafael@aurora.com.br"] and len(smtp_falso.enviados) == 1
    assert envio.destinatarios_liberados(db, ["rafael@aurora.com.br", "paula@aurora.com.br"]) == ["rafael@aurora.com.br"]


def test_enviar_por_usuario_sem_smtp_fora_de_dev_e_falha_de_entrega(db, smtp_falso, monkeypatch):
    u = criar_usuario(db, "Comercial", email="marina@exemplo.com", login="marina")
    monkeypatch.setattr(settings, "ambiente", "hml")
    monkeypatch.setattr(settings, "smtp_host", None)
    with pytest.raises(RegraViolada, match="^Configure o e-mail de envio em Configurações › E-mail ou em Minha conta"):
        envio.enviar_por_usuario(db, u, para=["a@x.com"], assunto="Oi", corpo="Olá")
    _org(db)
    smtp_falso.falha = smtplib.SMTPAuthenticationError(535, b"org-senha recusada")
    with pytest.raises(RegraViolada, match="^Não foi possível enviar o e-mail: o servidor recusou o usuário") as exc:
        envio.enviar_por_usuario(db, u, para=["a@x.com"], assunto="Oi", corpo="Olá")
    assert "org-senha" not in str(exc.value)
    smtp_falso.falha = OSError("sem rede")
    with pytest.raises(RegraViolada, match="não foi possível conectar ao servidor"):
        envio.enviar_por_usuario(db, u, para=["a@x.com"], assunto="Oi", corpo="Olá")
