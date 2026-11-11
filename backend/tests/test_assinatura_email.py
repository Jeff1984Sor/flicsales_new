"""Assinatura de e-mail por usuário (contrato 11/2026, E.5): PATCH /auth/me, imagem (POST/GET/DELETE
/auth/me/assinatura-imagem) e uso no envio (app.core.email)."""

import email
from email import policy

from app.core import email as mail
from app.core import storage
from app.core.models import Auditoria, Identidade
from tests.conftest import auth, criar_usuario, entrar

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _token(client, db, login="marina"):
    u = criar_usuario(db, "Comercial", email=f"{login}@exemplo.com", login=login)
    return u, auth(entrar(client, login).json()["access_token"])


def test_assinatura_texto_no_me(client, db):
    u, h = _token(client, db)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["assinatura_email"] is None and me["assinatura_imagem_url"] is None
    r = client.patch("/api/auth/me", json={"assinatura_email": "  Marina Souza\nComercial  "}, headers=h)
    assert r.status_code == 200 and r.json()["assinatura_email"] == "Marina Souza\nComercial"
    a = db.query(Auditoria).filter_by(acao="usuario.alterar_proprio").one()
    assert a.antes_json == {"assinatura_email": None} and a.depois_json["assinatura_email"].startswith("Marina")
    assert client.patch("/api/auth/me", json={"telefone": "11999990000"}, headers=h).json()["assinatura_email"]
    assert client.patch("/api/auth/me", json={"assinatura_email": ""}, headers=h).json()["assinatura_email"] is None
    r = client.patch("/api/auth/me", json={"assinatura_email": "x" * 4001}, headers=h)
    assert r.status_code == 422


def test_assinatura_imagem_enviar_ver_remover(client, db):
    u, h = _token(client, db)
    assert client.get("/api/auth/me/assinatura-imagem", headers=h).status_code == 404
    assert client.delete("/api/auth/me/assinatura-imagem", headers=h).status_code == 404
    r = client.post("/api/auth/me/assinatura-imagem", files={"arquivo": ("ass.png", PNG, "image/png")}, headers=h)
    assert r.status_code == 200, r.text
    url = r.json()["assinatura_imagem_url"]
    assert url.startswith("/auth/me/assinatura-imagem?v=")
    img = client.get("/api" + url, headers=h)
    assert img.status_code == 200 and img.content == PNG
    assert db.query(Auditoria).filter_by(acao="usuario.assinatura_imagem").count() == 1
    r = client.delete("/api/auth/me/assinatura-imagem", headers=h)
    assert r.status_code == 200 and r.json()["assinatura_imagem_url"] is None
    assert client.get("/api/auth/me/assinatura-imagem", headers=h).status_code == 404


def test_assinatura_imagem_validacoes_e_login(client, db):
    _, h = _token(client, db)
    grande = PNG + b"\x00" * (1024 * 1024)
    r = client.post("/api/auth/me/assinatura-imagem", files={"arquivo": ("a.png", grande, "image/png")}, headers=h)
    assert r.status_code == 400 and "1 MB" in r.json()["detail"]
    r = client.post("/api/auth/me/assinatura-imagem", files={"arquivo": ("a.gif", b"GIF89a", "image/gif")}, headers=h)
    assert r.status_code == 400 and "JPEG, JPG, PNG" in r.json()["detail"]
    r = client.post("/api/auth/me/assinatura-imagem", files={"arquivo": ("a.png", b"nao e png", "image/png")}, headers=h)
    assert r.status_code == 400
    assert client.get("/api/auth/me/assinatura-imagem").status_code == 401
    assert client.post("/api/auth/me/assinatura-imagem", files={"arquivo": ("a.png", PNG, "image/png")}).status_code == 401


def _ultima_mensagem():
    arqs = sorted((storage.raiz() / "outbox").glob("*.eml"))
    return email.message_from_bytes(arqs[-1].read_bytes(), policy=policy.default)


def test_envio_usa_assinatura_do_usuario_ou_da_identidade(db, client):
    db.add(Identidade(id=1, nome_exibicao="Flic", assinatura_email="Equipe Flic"))
    u, h = _token(client, db)
    db.commit()
    # sem assinatura própria: a da Identidade
    assert mail.enviar(["x@exemplo.com"], "Oi", "Corpo", db=db, remetente=u)
    assert "-- \nEquipe Flic" in _ultima_mensagem().get_body(("plain",)).get_content()
    # com texto e imagem próprios: a do usuário, imagem inline (CID)
    client.patch("/api/auth/me", json={"assinatura_email": "Marina"}, headers=h)
    client.post("/api/auth/me/assinatura-imagem", files={"arquivo": ("a.png", PNG, "image/png")}, headers=h)
    db.refresh(u)
    assert mail.enviar(["x@exemplo.com"], "Oi", "Corpo", db=db, remetente=u)
    msg = _ultima_mensagem()
    texto = msg.get_body(("plain",)).get_content()
    assert "-- \nMarina" in texto and "Equipe Flic" not in texto
    html = msg.get_body(("html",)).get_content()
    assert 'src="cid:assinatura"' in html
    imagens = [p for p in msg.walk() if p.get_content_type() == "image/png"]
    assert len(imagens) == 1 and imagens[0]["Content-ID"] == "<assinatura>" and imagens[0].get_content() == PNG
    # e-mail do sistema: sempre a da Identidade
    assert mail.enviar(["x@exemplo.com"], "Senha", "Link", db=db, assinar=True)
    assert "-- \nEquipe Flic" in _ultima_mensagem().get_body(("plain",)).get_content()
    # sem pedir assinatura: nada muda
    assert mail.enviar(["x@exemplo.com"], "Teste", "Só isto", db=db)
    assert _ultima_mensagem().get_body(("plain",)).get_content().strip() == "Só isto"
