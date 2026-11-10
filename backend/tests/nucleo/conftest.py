"""Fixtures do Núcleo: um cliente HTTP já autenticado por perfil (Gestor, Comercial, Financeiro, Somente leitura)."""

import pytest

from tests.conftest import auth, criar_usuario, entrar


class Api:
    """Atalho: api.get("/nucleo/empresas") → client.get("/api/nucleo/empresas", headers=Bearer)."""

    def __init__(self, client, token: str, usuario):
        self.client, self.h, self.usuario = client, auth(token), usuario

    def get(self, caminho, **kw):
        return self.client.get("/api" + caminho, headers=self.h, **kw)

    def post(self, caminho, json=None, **kw):
        return self.client.post("/api" + caminho, json=json, headers=self.h, **kw)

    def patch(self, caminho, json=None, **kw):
        return self.client.patch("/api" + caminho, json=json, headers=self.h, **kw)

    def delete(self, caminho, **kw):
        return self.client.delete("/api" + caminho, headers=self.h, **kw)


def _api(client, db, perfil, login):
    u = criar_usuario(db, perfil, email=f"{login}@exemplo.com", login=login)
    return Api(client, entrar(client, login).json()["access_token"], u)


@pytest.fixture
def gestor(client, admin, token_admin):
    return Api(client, token_admin, admin)


@pytest.fixture
def comercial(client, db):
    return _api(client, db, "Comercial", "marina")


@pytest.fixture
def financeiro(client, db):
    return _api(client, db, "Financeiro", "fin")


@pytest.fixture
def leitura(client, db):
    return _api(client, db, "Somente leitura", "leitor")
