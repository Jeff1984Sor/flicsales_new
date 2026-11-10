from datetime import timedelta

import jwt
from sqlalchemy import select

from app.core import auth_service
from app.core.db import agora
from app.core.models import RecuperacaoSenha, RefreshToken, Usuario
from app.core.security import criar_token, hash_senha
from tests.conftest import SENHA, auth, criar_usuario, entrar


# ---------------------------------------------------------------------------------------------- login
def test_login_so_pelo_login(client, admin):
    assert entrar(client, "ADMIN").status_code == 200  # login sem diferenciar maiúsculas
    r = entrar(client, "admin")
    corpo = r.json()
    assert corpo["usuario"]["administrador"] is True
    assert corpo["token_type"] == "bearer" and corpo["refresh_token"]


def test_login_por_email_nao_funciona(client, admin):
    """Decisão do Jefferson: ninguém entra com e-mail, só com o login."""
    r = client.post("/api/auth/login", json={"identificador": "admin@exemplo.com", "senha": SENHA})
    assert r.status_code == 401


def test_login_nao_revela_se_a_conta_existe(client, admin):
    a = entrar(client, "admin@exemplo.com", "errada1A")
    b = entrar(client, "nao.existe@exemplo.com", "errada1A")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_usuario_sem_acesso_ao_sistema_ou_inativo_nao_entra(client, db):
    criar_usuario(db, "Comercial", email="prof@exemplo.com", acesso_sistema=False)
    criar_usuario(db, "Comercial", email="off@exemplo.com", ativo=False)
    criar_usuario(db, "Comercial", email="semsenha@exemplo.com", senha=None)
    for e in ("prof@exemplo.com", "off@exemplo.com", "semsenha@exemplo.com"):
        assert entrar(client, e).status_code == 401


def test_bloqueio_apos_5_falhas_mesmo_com_senha_certa(client, db, admin):
    for _ in range(5):
        assert entrar(client, "admin", "errada1A").status_code == 401
    u = db.scalar(select(Usuario).where(Usuario.login == "admin"))
    assert u.bloqueado_ate is not None and u.bloqueado_ate > agora()
    r = entrar(client, "admin", SENHA)  # senha correta, mas bloqueado: mesma resposta genérica
    assert r.status_code == 401
    # passados os 15 minutos, volta a entrar
    u.bloqueado_ate = agora() - timedelta(seconds=1)
    db.commit()
    assert entrar(client, "admin", SENHA).status_code == 200


def test_login_bem_sucedido_zera_tentativas(client, db, admin):
    for _ in range(3):
        entrar(client, "admin", "errada1A")
    assert entrar(client, "admin").status_code == 200
    db.expire_all()
    assert db.scalar(select(Usuario.tentativas_falhas).where(Usuario.login == "admin")) == 0


# ---------------------------------------------------------------------------------------------- tokens
def test_rotas_exigem_token_valido(client, admin):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth("lixo")).status_code == 401
    # refresh token não vale como access token
    refresh = entrar(client, "admin").json()["refresh_token"]
    assert client.get("/api/auth/me", headers=auth(refresh)).status_code == 401


def test_token_expirado_e_recusado(client, admin):
    expirado = jwt.encode({"sub": str(admin.id), "typ": "access", "tv": 0, "jti": "x", "exp": agora() - timedelta(minutes=1)},
                          __import__("app.core.config", fromlist=["settings"]).settings.jwt_secret, algorithm="HS256")
    assert client.get("/api/auth/me", headers=auth(expirado)).status_code == 401


def test_access_dura_30_min_e_refresh_14_dias(admin):
    from app.core.security import decodificar_token

    a = decodificar_token(criar_token("1", "access"), "access")
    r = decodificar_token(criar_token("1", "refresh"), "refresh")
    assert a["exp"] - a["iat"] == 30 * 60
    assert r["exp"] - r["iat"] == 14 * 24 * 3600


def test_refresh_rotaciona_e_reuso_derruba_todas_as_sessoes(client, db, admin):
    t1 = entrar(client, "admin").json()
    r = client.post("/api/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert r.status_code == 200
    t2 = r.json()
    assert t2["refresh_token"] != t1["refresh_token"]
    assert client.get("/api/auth/me", headers=auth(t2["access_token"])).status_code == 200

    # reuso do refresh antigo FORA da janela de tolerância = roubo presumido: tudo é derrubado
    antigo = db.get(RefreshToken, jwt.decode(t1["refresh_token"], options={"verify_signature": False})["jti"])
    antigo.usado_em = agora() - timedelta(minutes=5)
    db.commit()
    assert client.post("/api/auth/refresh", json={"refresh_token": t1["refresh_token"]}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": t2["refresh_token"]}).status_code == 401
    assert client.get("/api/auth/me", headers=auth(t2["access_token"])).status_code == 401


def test_reuso_imediato_do_refresh_nao_derruba_a_sessao(client, admin):
    """Duas abas renovando quase juntas: a segunda falha, mas a sessão da primeira continua."""
    t1 = entrar(client, "admin").json()
    t2 = client.post("/api/auth/refresh", json={"refresh_token": t1["refresh_token"]}).json()
    assert client.post("/api/auth/refresh", json={"refresh_token": t1["refresh_token"]}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": t2["refresh_token"]}).status_code == 200


def test_refresh_forjado_ou_sem_registro_e_recusado(client, admin):
    assert client.post("/api/auth/refresh", json={"refresh_token": "lixo"}).status_code == 401
    sem_registro = criar_token(str(admin.id), "refresh", {"tv": 0})
    assert client.post("/api/auth/refresh", json={"refresh_token": sem_registro}).status_code == 401


# ---------------------------------------------------------------------------------------------- troca de senha
def test_trocar_senha_exige_senha_atual_e_invalida_sessoes_antigas(client, db, admin):
    t = entrar(client, "admin").json()
    h = auth(t["access_token"])
    r = client.post("/api/auth/trocar-senha", headers=h, json={"senha_atual": "errada1A", "nova_senha": "Nova@Senha9"})
    assert r.status_code == 400
    r = client.post("/api/auth/trocar-senha", headers=h, json={"senha_atual": SENHA, "nova_senha": "fraca"})
    assert r.status_code == 400
    r = client.post("/api/auth/trocar-senha", headers=h, json={"senha_atual": SENHA, "nova_senha": "Nova@Senha9"})
    assert r.status_code == 200
    novo = r.json()
    # sessão antiga (access e refresh) morreu; a nova funciona
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401
    assert client.get("/api/auth/me", headers=auth(novo["access_token"])).status_code == 200
    assert entrar(client, "admin", SENHA).status_code == 401
    assert entrar(client, "admin", "Nova@Senha9").status_code == 200


def test_logout_encerra_todas_as_sessoes(client, admin):
    t = entrar(client, "admin").json()
    assert client.post("/api/auth/logout", headers=auth(t["access_token"])).status_code == 200
    assert client.get("/api/auth/me", headers=auth(t["access_token"])).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401


def test_desativar_ou_trocar_perfil_derruba_a_sessao(client, db, token_admin):
    criar_usuario(db, "Comercial", email="prof@exemplo.com")
    tp = entrar(client, "prof@exemplo.com").json()["access_token"]
    uid = db.scalar(select(Usuario.id).where(Usuario.email == "prof@exemplo.com"))
    assert client.get("/api/auth/me", headers=auth(tp)).status_code == 200
    assert client.delete(f"/api/config/usuarios/{uid}", headers=auth(token_admin)).status_code == 200
    assert client.get("/api/auth/me", headers=auth(tp)).status_code == 401


# ---------------------------------------------------------------------------------------------- recuperação por e-mail
def test_forgot_resposta_igual_exista_ou_nao(client, admin, emails):
    a = client.post("/api/auth/forgot", json={"identificador": "admin"})
    b = client.post("/api/auth/forgot", json={"identificador": "ninguem"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert len(emails) == 1 and emails[0][0] == ["admin@exemplo.com"]


def _token_do_email(emails) -> str:
    corpo = emails[-1][2]
    return corpo.split("token=")[1].split()[0]


def test_reset_por_email_uso_unico_e_invalida_sessoes(client, db, admin, emails):
    antiga = entrar(client, "admin").json()
    client.post("/api/auth/forgot", json={"identificador": "admin"})
    token = _token_do_email(emails)
    linha = db.scalar(select(RecuperacaoSenha))
    assert token not in linha.digest and linha.canal == "email"  # só o digest fica no banco

    assert client.post("/api/auth/reset", json={"token": token, "senha": "fraca"}).status_code == 400
    assert client.post("/api/auth/reset", json={"token": token, "senha": "Outra@Senha7"}).status_code == 200
    assert client.post("/api/auth/reset", json={"token": token, "senha": "Outra@Senha8"}).status_code == 400  # uso único
    assert entrar(client, "admin", "Outra@Senha7").status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": antiga["refresh_token"]}).status_code == 401


def test_reset_com_token_expirado_ou_falso(client, db, admin, emails):
    client.post("/api/auth/forgot", json={"identificador": "admin"})
    token = _token_do_email(emails)
    linha = db.scalar(select(RecuperacaoSenha))
    linha.expira_em = agora() - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/auth/reset", json={"token": token, "senha": "Outra@Senha7"}).status_code == 400
    assert client.post("/api/auth/reset", json={"token": "inventado", "senha": "Outra@Senha7"}).status_code == 400


def test_novo_pedido_invalida_o_link_anterior(client, admin, emails):
    client.post("/api/auth/forgot", json={"identificador": "admin"})
    velho = _token_do_email(emails)
    client.post("/api/auth/forgot", json={"identificador": "admin"})
    novo = _token_do_email(emails)
    assert client.post("/api/auth/reset", json={"token": velho, "senha": "Outra@Senha7"}).status_code == 400
    assert client.post("/api/auth/reset", json={"token": novo, "senha": "Outra@Senha7"}).status_code == 200


def test_reset_desbloqueia_conta(client, db, admin, emails):
    for _ in range(5):
        entrar(client, "admin", "errada1A")
    client.post("/api/auth/forgot", json={"identificador": "admin"})
    client.post("/api/auth/reset", json={"token": _token_do_email(emails), "senha": "Outra@Senha7"})
    assert entrar(client, "admin", "Outra@Senha7").status_code == 200


# ---------------------------------------------------------------------------------------------- recuperação por WhatsApp
def _codigo(zap) -> str:
    texto = zap.enviadas[-1][1]
    return next(p for p in texto.replace(".", " ").split() if p.isdigit() and len(p) == 6)


def test_codigo_whatsapp_fluxo_completo(client, db, zap):
    criar_usuario(db, "Financeiro", email="rec@exemplo.com", telefone="(11) 98888-7777")
    r = client.post("/api/auth/forgot-codigo", json={"identificador": "rec"})
    assert r.status_code == 200
    fone, _ = zap.enviadas[0]
    assert fone == "5511988887777"
    codigo = _codigo(zap)
    r = client.post("/api/auth/reset-codigo", json={"identificador": "rec", "codigo": codigo, "senha": "Zap@Senha77"})
    assert r.status_code == 200
    assert entrar(client, "rec@exemplo.com", "Zap@Senha77").status_code == 200
    # código de uso único
    r = client.post("/api/auth/reset-codigo", json={"identificador": "rec", "codigo": codigo, "senha": "Zap@Senha78"})
    assert r.status_code == 400


def test_codigo_whatsapp_limite_de_tentativas(client, db, zap):
    criar_usuario(db, "Financeiro", email="rec@exemplo.com", telefone="11988887777")
    client.post("/api/auth/forgot-codigo", json={"identificador": "rec"})
    certo = _codigo(zap)
    errado = "000000" if certo != "000000" else "111111"
    for _ in range(5):
        r = client.post("/api/auth/reset-codigo", json={"identificador": "rec", "codigo": errado, "senha": "Zap@Senha77"})
        assert r.status_code == 400
    # esgotadas as tentativas, nem o código certo funciona mais
    r = client.post("/api/auth/reset-codigo", json={"identificador": "rec", "codigo": certo, "senha": "Zap@Senha77"})
    assert r.status_code == 400


def test_codigo_whatsapp_expirado(client, db, zap):
    criar_usuario(db, "Financeiro", email="rec@exemplo.com", telefone="11988887777")
    client.post("/api/auth/forgot-codigo", json={"identificador": "rec"})
    codigo = _codigo(zap)
    linha = db.scalar(select(RecuperacaoSenha))
    linha.expira_em = agora() - timedelta(seconds=1)
    db.commit()
    r = client.post("/api/auth/reset-codigo", json={"identificador": "rec", "codigo": codigo, "senha": "Zap@Senha77"})
    assert r.status_code == 400


def test_codigo_whatsapp_nao_revela_conta_nem_telefone(client, db, zap):
    criar_usuario(db, "Financeiro", email="semfone@exemplo.com")
    a = client.post("/api/auth/forgot-codigo", json={"identificador": "semfone"})
    b = client.post("/api/auth/forgot-codigo", json={"identificador": "nao.existe"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert zap.enviadas == []
    r1 = client.post("/api/auth/reset-codigo", json={"identificador": "nao.existe", "codigo": "123456", "senha": "Zap@Senha77"})
    r2 = client.post("/api/auth/reset-codigo", json={"identificador": "semfone", "codigo": "123456", "senha": "Zap@Senha77"})
    assert r1.status_code == r2.status_code == 400 and r1.json() == r2.json()


def test_normalizacao_minima_de_telefone():
    assert auth_service.telefone_whatsapp("(11) 98888-7777") == "5511988887777"
    assert auth_service.telefone_whatsapp("+55 11 3888-7777") == "551138887777"
    assert auth_service.telefone_whatsapp("123") is None
    assert auth_service.telefone_whatsapp(None) is None


def test_hash_senha_gera_argon2():
    assert hash_senha("Abc12345").startswith("$argon2")
