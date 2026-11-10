"""Um banco por organização, em SQLite: um controle próprio (tenancy.forcar_controle) e duas organizações provisionadas.

Tudo fica isolado: ao sair, o controle volta a ser detectado (não existe nos testes → um banco só), os engines das
organizações são fechados e o cache é limpo; os outros testes do projeto continuam no modo de sempre.

Organizações (todas com a senha SENHA):
- alfa  (alfa.flicsales.test): logins "ana" (Gestor) e "carlos" (Comercial)
- beta  (beta.flicsales.test): logins "ana" (Gestor) e "bia" (Financeiro)
"ana" existe nas duas: no endereço principal o login é ambíguo.
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from app.core import tenancy
from tests.conftest import SENHA

HOST_ALFA = "alfa.flicsales.test"
HOST_BETA = "beta.flicsales.test"


def _apagar_bancos(*slugs: str) -> None:
    from app.controle import service

    tenancy.descartar_engines()
    for slug in slugs:
        url = tenancy.url_do_banco(service.nome_do_banco(slug)).removeprefix("sqlite:///")
        for sufixo in ("", "-wal", "-shm"):
            Path(url + sufixo).unlink(missing_ok=True)


@contextmanager
def controle_proprio():
    """Liga o modo multi com um banco de controle novo (e desliga ao sair)."""
    from app.controle import models, service

    pasta = Path(tempfile.mkdtemp(prefix="flicsales-controle-"))
    tenancy.forcar_controle(f"sqlite:///{(pasta / 'controle.db').as_posix()}")
    models.reiniciar_engine()
    service.limpar_cache()
    try:
        service.migrar_controle()
        yield
    finally:
        tenancy.forcar_controle(None)
        models.reiniciar_engine()
        service.limpar_cache()
        tenancy.descartar_engines()


def _usuario(slug: str, perfil: str, login: str) -> None:
    from app.controle import service
    from app.core import perfis
    from app.core.db import SessionLocal
    from app.core.models import Usuario
    from app.core.security import hash_senha

    with tenancy.usando(service.por_slug(slug)), SessionLocal() as db:
        p = perfis.garantir_padrao(db)[perfil]
        db.add(Usuario(nome=f"{login.title()} {slug}", email=f"{login}@{slug}.com", login=login,
                       perfil_acesso_id=p.id, senha_hash=hash_senha(SENHA)))
        db.commit()


@pytest.fixture(scope="module")
def multi():
    """Controle + organizações alfa e beta (provisionadas de verdade: banco, migrations, Gestor)."""
    import app.controle.sincronia  # noqa: F401
    from app.controle import service

    _apagar_bancos("alfa", "beta", "gama", "epsilon")
    with controle_proprio():
        service.provisionar("alfa", "Organização Alfa", admin_email="ana@alfa.com", admin_nome="Ana Alfa",
                            admin_login="ana", admin_senha=SENHA, dominios=[HOST_ALFA])
        service.provisionar("beta", "Organização Beta", admin_email="ana@beta.com", admin_nome="Ana Beta",
                            admin_login="ana", admin_senha=SENHA, dominios=[HOST_BETA])
        _usuario("alfa", "Comercial", "carlos")
        _usuario("beta", "Financeiro", "bia")
        yield service
    _apagar_bancos("alfa", "beta", "gama", "epsilon")


def entrar(client, login, senha=SENHA, host=None):
    headers = {"X-Forwarded-Host": host} if host else {}
    return client.post("/api/auth/login", json={"identificador": login, "senha": senha}, headers=headers)


def bearer(r) -> dict:
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
