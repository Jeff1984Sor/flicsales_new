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


@pytest.fixture
def sem_acesso(client, db):
    """Usuário com perfil sem nenhuma permissão (para provar o 403)."""
    from app.core.models import PerfilAcesso, Usuario
    from app.core.security import hash_senha
    from tests.conftest import SENHA

    p = PerfilAcesso(nome="Sem acesso", permissoes=[])
    db.add(p)
    db.flush()
    u = Usuario(nome="Sem acesso", email="nada@exemplo.com", login="nada", perfil_acesso_id=p.id,
                senha_hash=hash_senha(SENHA))
    db.add(u)
    db.commit()
    return Api(client, entrar(client, "nada").json()["access_token"], u)


class RedeFalsa:
    """Provedores externos falsos (nunca rede real): `rede.rotas["brasilapi.com.br/api/cnpj"] = (200, {...})`.
    A chave é um trecho da URL; valor (status, json) ou uma exceção httpx para simular queda."""

    def __init__(self):
        self.rotas: dict[str, object] = {}
        self.chamadas: list[str] = []

    def __call__(self, request):
        import httpx

        url = str(request.url)
        self.chamadas.append(url)
        for trecho, resposta in self.rotas.items():
            if trecho in url:
                if isinstance(resposta, Exception):
                    raise resposta
                status, corpo = resposta
                return httpx.Response(status, json=corpo)
        raise httpx.ConnectError("sem rede nos testes", request=request)


@pytest.fixture
def rede(monkeypatch):
    import httpx

    from app.modules.nucleo import consultas

    falsa = RedeFalsa()
    consultas.limpar_cache()
    monkeypatch.setattr(consultas, "TRANSPORTE", httpx.MockTransport(falsa))
    yield falsa
    consultas.limpar_cache()
