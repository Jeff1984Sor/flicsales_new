import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, select, text, update

from app.core import audit, segredos
from app.core.config import Settings
from app.core.models import Auditoria, ConfigEmail, Usuario
from tests.conftest import auth, entrar


# ---------------------------------------------------------------------------------------------- cifra de segredos
def test_cifra_ida_e_volta_e_nao_guarda_em_claro():
    c = segredos.cifrar_texto("senha-do-smtp")
    assert isinstance(c, bytes) and b"senha-do-smtp" not in c
    assert segredos.decifrar_texto(c) == "senha-do-smtp"
    assert segredos.cifrar_texto("senha-do-smtp") != c  # IV aleatório


def test_decifrar_dado_corrompido_ou_de_outra_chave():
    with pytest.raises(segredos.SegredoInvalido):
        segredos.decifrar(b"lixo")
    outra = Fernet(Fernet.generate_key()).encrypt(b"x")
    with pytest.raises(segredos.SegredoInvalido):
        segredos.decifrar(outra)


def test_rotacao_de_master_key(monkeypatch):
    from app.core.config import settings

    velha = settings.master_key
    c = segredos.cifrar_texto("segredo")
    nova = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "master_key", nova)
    with pytest.raises(segredos.SegredoInvalido):
        segredos.decifrar(c)  # sem a chave anterior não abre
    monkeypatch.setattr(settings, "master_key_anterior", velha)
    assert segredos.decifrar_texto(c) == "segredo"  # com a anterior, abre
    recifrado = segredos.recifrar(c)
    monkeypatch.setattr(settings, "master_key_anterior", None)
    assert segredos.decifrar_texto(recifrado) == "segredo"  # e agora só precisa da nova


def test_mascarar():
    assert segredos.mascarar("abcdef123456") == "••••••3456"
    assert segredos.mascarar(None) is None


def test_senha_smtp_fica_cifrada_no_banco_e_nao_volta_na_api(client, db, token_admin):
    h = auth(token_admin)
    corpo = {"remetente_nome": "Flic", "remetente_email": "oi@flic.com", "smtp_host": "smtp.flic.com", "smtp_porta": 587,
             "smtp_usuario": "oi@flic.com", "smtp_senha": "SenhaSecretaSMTP", "copia_padrao": []}
    r = client.put("/api/config/email", headers=h, json=corpo)
    assert r.status_code == 200
    assert r.json()["smtp_senha_definida"] is True and "SenhaSecretaSMTP" not in r.text
    db.expire_all()
    cfg = db.get(ConfigEmail, 1)
    assert b"SenhaSecretaSMTP" not in cfg.smtp_senha_cifrada
    assert segredos.decifrar_texto(cfg.smtp_senha_cifrada) == "SenhaSecretaSMTP"
    # sem enviar a senha, ela é mantida
    corpo.pop("smtp_senha")
    client.put("/api/config/email", headers=h, json=corpo)
    db.expire_all()
    assert segredos.decifrar_texto(db.get(ConfigEmail, 1).smtp_senha_cifrada) == "SenhaSecretaSMTP"
    # e a auditoria não registra o segredo
    textos = " ".join(str(a.antes_json) + str(a.depois_json) + str(a.descricao) for a in db.scalars(select(Auditoria)))
    assert "SenhaSecretaSMTP" not in textos


def test_chave_da_ia_cifrada(client, db, token_admin):
    h = auth(token_admin)
    r = client.put("/api/config/ia", headers=h, json={"ativo": True, "provedor": "openai", "modelo": "gpt-x", "chave": "sk-segredo-1234"})
    assert r.status_code == 200
    assert r.json()["chave_final"] == "1234" and "sk-segredo" not in r.text


# ---------------------------------------------------------------------------------------------- configuração segura
def _base(**kw):
    d = dict(ambiente="hml", jwt_secret="x" * 40, master_key=Fernet.generate_key().decode(), debug=False,
             allowed_hosts=["hml-pilates.exemplo.com"], frontend_url="https://hml-pilates.exemplo.com",
             cors_origins=["https://hml-pilates.exemplo.com"])
    d.update(kw)
    return d


def test_config_hml_valida_aceita_e_dev_default_funciona():
    s = Settings(**_base())
    assert s.ambiente == "hml" and s.fuso == "America/Sao_Paulo"


@pytest.mark.parametrize("mudanca,trecho", [
    ({"jwt_secret": "dev-inseguro-troque-em-producao-0000"}, "JWT_SECRET"),
    ({"jwt_secret": "curta"}, "JWT_SECRET"),
    ({"master_key": "q5w0m9cY3G1o4oE5d2u2x2gVQv0q6Q7k1tq9a0c3Zf8="}, "MASTER_KEY"),
    ({"debug": True}, "DEBUG"),
    ({"allowed_hosts": ["*"]}, "ALLOWED_HOSTS"),
    ({"allowed_hosts": ["localhost"]}, "ALLOWED_HOSTS"),
    ({"frontend_url": "http://x.com"}, "https"),
    ({"cors_origins": ["http://localhost:3000"]}, "CORS_ORIGINS"),
])
def test_config_hml_prod_recusa_inseguro(mudanca, trecho):
    with pytest.raises(ValueError, match=trecho):
        Settings(**_base(**mudanca))
    with pytest.raises(ValueError, match=trecho):
        Settings(**_base(ambiente="prod", **mudanca))


def test_master_key_invalida_e_recusada_ate_em_dev():
    with pytest.raises(ValueError, match="MASTER_KEY"):
        Settings(ambiente="dev", master_key="nao-e-fernet")


def test_jwt_secret_e_master_key_nao_podem_ser_iguais():
    k = Fernet.generate_key().decode()
    with pytest.raises(ValueError, match="diferente"):
        Settings(**_base(jwt_secret=k, master_key=k))


# ---------------------------------------------------------------------------------------------- auditoria imutável
def _registro(db):
    audit.registrar(db, usuario=None, acao="teste.acao", entidade="teste", entidade_id=1, descricao="x")
    db.commit()
    return db.scalar(select(Auditoria))


def test_auditoria_orm_update_e_delete_bloqueados(db):
    a = _registro(db)
    a.descricao = "adulterado"
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()
    db.delete(db.scalar(select(Auditoria)))
    with pytest.raises(PermissionError):
        db.commit()
    db.rollback()


def test_auditoria_sql_direto_e_bulk_bloqueados(db):
    _registro(db)
    for stmt in (update(Auditoria).values(descricao="x"), delete(Auditoria)):
        with pytest.raises(PermissionError):
            db.execute(stmt)
        db.rollback()
    for sql in ("UPDATE auditoria SET descricao='x'", 'delete from "auditoria"', "  DELETE FROM auditoria WHERE id=1"):
        with pytest.raises(PermissionError):
            db.execute(text(sql))
        db.rollback()
    assert db.scalar(select(Auditoria.descricao)) == "x"
    assert db.scalar(select(Auditoria).limit(1)).acao == "teste.acao"


def test_auditoria_continua_aceitando_insert(db):
    _registro(db)
    audit.registrar(db, usuario=None, acao="outra", entidade="teste")
    db.commit()
    assert len(list(db.scalars(select(Auditoria)))) == 2


def test_auditoria_nao_grava_campos_sensiveis(db, admin):
    snap = audit.snapshot(db.get(Usuario, admin.id))
    assert "senha_hash" not in snap and snap["email"] == "admin@exemplo.com"


def test_login_e_acoes_sensiveis_geram_auditoria(client, db, admin):
    entrar(client, "admin", "errada1A")
    h = auth(entrar(client, "admin@exemplo.com").json()["access_token"])
    client.put("/api/config/identidade", headers=h, json={"nome_exibicao": "Novo Nome"})
    acoes = {a.acao for a in db.scalars(select(Auditoria))}
    assert {"auth.login", "identidade.alterar"} <= acoes
    r = client.get("/api/auditoria?acao=identidade", headers=h).json()
    assert r["total"] == 1 and r["itens"][0]["usuario_nome"] == admin.nome
    assert r["itens"][0]["depois_json"]["nome_exibicao"] == "Novo Nome"
