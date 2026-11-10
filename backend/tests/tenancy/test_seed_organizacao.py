"""`python -m app.seed --organizacao <slug>`: popula UMA organização com os dados do protótipo fora do dev
(em prod só com --forcar), idempotente e sem criar usuários além dos de demonstração."""

import pytest
from sqlalchemy import func, select

from app import seed
from app.core import tenancy
from app.core.config import settings
from app.core.db import SessionLocal, hoje
from app.core.models import Usuario
from app.modules.comercial.models import Funil, Oportunidade
from tests.conftest import SENHA
from tests.tenancy.conftest import _apagar_bancos, controle_proprio, entrar


@pytest.fixture
def org_demo():
    from app.controle import service

    _apagar_bancos("vitrine")
    try:
        with controle_proprio():
            import app.controle.sincronia  # noqa: F401

            service.provisionar("vitrine", "Vitrine", admin_email="ana@vitrine.com", admin_login="ana",
                                admin_senha=SENHA, dominios=["vitrine.flicsales.test"])
            yield service
    finally:
        _apagar_bancos("vitrine")


def _contar(modelo):
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(modelo))


def test_popula_so_a_organizacao_pedida_e_e_idempotente(org_demo, client, monkeypatch):
    monkeypatch.setattr(settings, "ambiente", "hml")
    assert seed.popular_organizacao("vitrine", hoje=hoje()) is True
    assert seed.popular_organizacao("vitrine", hoje=hoje()) is False  # de novo: nada duplica
    with tenancy.usando(org_demo.por_slug("vitrine")):
        assert _contar(Funil) == 1 and _contar(Oportunidade) > 0
        with SessionLocal() as db:
            logins = set(db.scalars(select(Usuario.login)))
    assert logins == {"ana", "francine", "marina", "lucas", "fin"}  # só o Gestor da organização + os de demo
    with tenancy.engine_do(None).connect() as conn:  # o banco principal não foi tocado
        assert conn.scalar(select(func.count()).select_from(Funil)) == 0
    # os logins de demo entram pelo endereço da organização com a senha de demonstração
    r = entrar(client, "marina", seed.SENHA_DEMO, host="vitrine.flicsales.test")
    assert r.status_code == 200, r.text


def test_em_prod_exige_forcar(org_demo, monkeypatch):
    monkeypatch.setattr(settings, "ambiente", "prod")
    with pytest.raises(seed.SeedRecusado, match="--forcar"):
        seed.popular_organizacao("vitrine")
    assert seed.popular_organizacao("vitrine", forcar=True, hoje=hoje()) is True


def test_organizacao_inexistente_ou_sem_controle(org_demo):
    with pytest.raises(seed.SeedRecusado, match="não existe"):
        seed.popular_organizacao("nao-existe")


def test_sem_controle_recusa():
    with pytest.raises(seed.SeedRecusado, match="controle"):
        seed.popular_organizacao("qualquer")


def test_cli_recusa_em_prod_sem_forcar(monkeypatch):
    monkeypatch.setattr(settings, "ambiente", "prod")
    with pytest.raises(SystemExit, match="--forcar"):
        seed.main(["--organizacao", "vitrine"])
