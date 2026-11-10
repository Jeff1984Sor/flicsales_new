"""Isolamento entre organizações sob ataque: tokens forjados/adulterados, token de uma organização no endereço de
outra, slug forjado no link de redefinição, host falso."""

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from tests.conftest import SENHA
from tests.tenancy.conftest import HOST_ALFA, HOST_BETA, entrar


def _assinar(payload: dict, segredo: str | None = None) -> str:
    agora = datetime.now(UTC)
    base = {"iat": agora, "exp": agora + timedelta(minutes=10), "jti": "x" * 32}
    return jwt.encode({**base, **payload}, segredo or settings.jwt_secret, algorithm="HS256")


def _payload(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


def test_token_sem_organizacao_nao_vale_no_modo_multi(multi, client):
    p = _payload(entrar(client, "ana", host=HOST_ALFA).json()["access_token"])
    p.pop("org")
    sem = {"Authorization": f"Bearer {_assinar(p)}"}
    assert client.get("/api/auth/me", headers=sem).status_code == 401
    assert client.get("/api/auth/me", headers={**sem, "X-Forwarded-Host": HOST_ALFA}).status_code == 401
    assert client.get("/api/auth/me", headers={**sem, "X-Forwarded-Host": HOST_BETA}).status_code == 401


def test_token_adulterado_ou_com_outra_chave(multi, client):
    token = entrar(client, "ana", host=HOST_ALFA).json()["access_token"]
    cab, _corpo, sig = token.split(".")
    p = _payload(token)
    p["org"] = "beta"
    corpo_falso = base64.urlsafe_b64encode(json.dumps(p, default=str).encode()).rstrip(b"=").decode()
    for falso in (f"{cab}.{corpo_falso}.{sig}", _assinar({**p, "org": "beta"}, segredo="outra-chave-" + "x" * 32)):
        h = {"Authorization": f"Bearer {falso}"}
        assert client.get("/api/auth/me", headers=h).status_code == 401
        assert client.get("/api/auth/me", headers={**h, "X-Forwarded-Host": HOST_BETA}).status_code == 401


def test_token_da_alfa_no_endereco_da_beta_so_ve_a_alfa(multi, client):
    alfa = entrar(client, "ana", host=HOST_ALFA).json()
    h = {"Authorization": f"Bearer {alfa['access_token']}", "X-Forwarded-Host": HOST_BETA, "Host": HOST_BETA}
    usuarios = {u["email"] for u in client.get("/api/config/usuarios", headers=h).json()}
    assert "ana@alfa.com" in usuarios and not any(e.endswith("@beta.com") for e in usuarios)
    r = client.post("/api/auth/refresh", json={"refresh_token": alfa["refresh_token"]}, headers={"X-Forwarded-Host": HOST_BETA})
    assert r.status_code == 200 and r.json()["usuario"]["organizacao"]["slug"] == "alfa"


def test_token_de_organizacao_que_ficou_inativa(multi, client):
    beta = entrar(client, "bia").json()
    try:
        multi.definir_status("beta", "inativo")
        assert client.post("/api/auth/refresh", json={"refresh_token": beta["refresh_token"]}).status_code == 401
        h = {"Authorization": f"Bearer {beta['access_token']}", "X-Forwarded-Host": HOST_ALFA}
        assert client.get("/api/auth/me", headers=h).status_code == 401
    finally:
        multi.definir_status("beta", "ativo")


def test_slug_forjado_no_link_de_redefinicao(multi, client, emails):
    client.post("/api/auth/forgot", json={"identificador": "carlos"})
    token = emails[-1][2].split("token=")[1].split()[0]
    slug, aleatorio = token.split(".", 1)
    assert slug == "alfa"
    for forjado in (f"beta.{aleatorio}", f"inexistente.{aleatorio}", aleatorio, f"alfa.{aleatorio}x", "."):
        r = client.post("/api/auth/reset", json={"token": forjado, "senha": "Outra@Senha9"})
        assert r.status_code == 400, forjado
    assert client.post("/api/auth/reset", json={"token": token, "senha": SENHA}).status_code == 200


def test_forgot_e_codigo_no_login_ambiguo_nao_revelam(multi, client):
    a = client.post("/api/auth/forgot", json={"identificador": "ana"})
    b = client.post("/api/auth/forgot", json={"identificador": "ninguem"})
    assert a.json() == b.json() and a.status_code == b.status_code == 200
    r = client.post("/api/auth/reset-codigo", json={"identificador": "ana", "codigo": "123456", "senha": SENHA})
    assert r.status_code == 400


def test_host_falso(multi, client):
    assert client.get("/api/public/identidade", headers={"Host": "beta.flicsales.test.evil.com"}).status_code == 400
    assert client.get("/api/public/identidade", headers={"X-Forwarded-Host": "evil.com"}).status_code == 401
    assert entrar(client, "carlos", host=HOST_BETA).status_code == 401


def test_primeiro_acesso_forjado_ou_reaproveitado(multi, client):
    from app.core import tenancy
    from app.core.security import criar_token

    # link para uma organização que já tem Gestor: não cria um segundo
    with tenancy.usando(multi.por_slug("alfa")):
        tk = criar_token("alfa", "primeiro", {"email": "intruso@x.com"})
    dados = {"token": tk, "nome": "Intruso", "email": "intruso@x.com", "login": "intruso", "senha": SENHA}
    assert client.post("/api/auth/primeiro-acesso", json=dados).status_code == 409
    # sem organização no token, outro tipo de token ou outra chave: inválido
    sem_org = _assinar({"sub": "beta", "typ": "primeiro"})
    access = entrar(client, "ana", host=HOST_ALFA).json()["access_token"]
    outra = _assinar({"sub": "beta", "typ": "primeiro", "org": "beta"}, segredo="outra-chave-" + "y" * 32)
    for t in (sem_org, access, outra):
        assert client.post("/api/auth/primeiro-acesso", json={**dados, "token": t}).status_code == 400
        assert client.get("/api/auth/primeiro-acesso", params={"token": t}).status_code in (400, 401)
