"""Fixtures da Orquestração: organização de demonstração (seed), tokens por perfil e IA FALSA injetável.

Nenhum teste chama provedor real: `ia_falsa` injeta um gerador que devolve o que o teste mandar e guarda os prompts.
"""

from collections.abc import Callable
from typing import Any

import pytest

from app import seed
from app.core.db import hoje
from app.modules.orquestracao.ia import gateway
from tests.conftest import auth, entrar


@pytest.fixture
def demo(db):
    seed.semear(db, hoje())
    return db


def token(client, login: str) -> dict:
    r = entrar(client, login, seed.SENHA_DEMO)
    assert r.status_code == 200, r.text
    return auth(r.json()["access_token"])


@pytest.fixture
def gestor(client, demo):
    return token(client, "francine")


@pytest.fixture
def comercial(client, demo):
    return token(client, "marina")


@pytest.fixture
def financeiro(client, demo):
    return token(client, "fin")


class IAFalsa:
    def __init__(self) -> None:
        self.respostas: list[Any] = []
        self.chamadas: list[tuple[str, str]] = []
        self.funcao: Callable[[str, str], Any] | None = None

    def __call__(self, db, sistema: str, usuario: str) -> Any:
        self.chamadas.append((sistema, usuario))
        if self.funcao:
            return self.funcao(sistema, usuario)
        return self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]


RESPOSTA_OK = {
    "titulo": "Aurora pede validação de escopo",
    "analise": "Aurora tem R$ 24.000,00 em negociação; ainda não é recebível.",
    "proxima_acao": "Confirmar entregáveis e condição de pagamento.",
    "evidencias": [{"fonte": "Comercial › Oportunidades › #1", "trecho": "Projeto de consultoria · R$ 24.000,00"}],
    "limites": ["Não existe compromisso confirmado de fechamento."],
    "acoes_sugeridas": [{"tipo": "criar_atividade", "rotulo": "Criar tarefa após revisão",
                         "payload": {"assunto": "Validar entregáveis · Aurora", "tipo": "tarefa"}}],
}


@pytest.fixture
def ia_falsa():
    falsa = IAFalsa()
    falsa.respostas = [RESPOSTA_OK]
    gateway.definir_gerador(falsa)
    yield falsa
    gateway.definir_gerador(None)
