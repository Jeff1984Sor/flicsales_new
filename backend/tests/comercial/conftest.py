"""Fixtures do Comercial: organização de demonstração (seed) e cabeçalhos de login por perfil."""

import pytest
from sqlalchemy import select

from app import seed
from app.core.db import hoje
from app.core.models import PerfilAcesso, Usuario
from app.modules.comercial.models import Etapa, Funil, Oportunidade
from tests.conftest import auth, criar_usuario, entrar

SENHA_DEMO = seed.SENHA_DEMO


@pytest.fixture
def demo(db):
    seed.semear(db, hoje())
    return db


def _cab(client, login: str, senha: str = SENHA_DEMO) -> dict:
    r = entrar(client, login, senha)
    assert r.status_code == 200, r.text
    return auth(r.json()["access_token"])


@pytest.fixture
def gestor(client, demo):
    return _cab(client, "francine")


@pytest.fixture
def marina(client, demo):
    return _cab(client, "marina")


@pytest.fixture
def financeiro(client, demo):
    return _cab(client, "fin")


@pytest.fixture
def leitura(client, demo):
    criar_usuario(demo, "Somente leitura", email="leitura@exemplo.com", login="leitura")
    return _cab(client, "leitura", "Senha@Forte1")


@pytest.fixture
def so_meus(demo):
    """Liga "só meus registros" no perfil Comercial (Marina e Lucas)."""
    p = demo.scalar(select(PerfilAcesso).where(PerfilAcesso.nome == "Comercial"))
    p.somente_meus_registros = True
    demo.commit()
    return p


def usuario(db, login: str) -> Usuario:
    return db.scalar(select(Usuario).where(Usuario.login == login))


def funil_demo(db) -> Funil:
    return db.scalar(select(Funil).where(Funil.nome == seed.FUNIL_DEMO))


def etapa(db, nome: str) -> Etapa:
    return db.scalar(select(Etapa).where(Etapa.nome == nome))


def oportunidade(db, titulo: str) -> Oportunidade:
    return db.scalar(select(Oportunidade).where(Oportunidade.titulo == titulo))
