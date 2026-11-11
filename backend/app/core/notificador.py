"""Envio de texto por WhatsApp (ou outro canal) usado pelo core, ex.: código de recuperação de senha.

A implementação real é a Evolution API (`app.modules.orquestracao.evolution.NotificadorEvolution`), registrada com
`definir_notificador` quando a API carrega os módulos (app/modules/orquestracao/routes.py). Ela lê a configuração
(Núcleo › Integrações › WhatsApp) do banco da organização do pedido atual. Sem módulo/conexão, o envio só registra no
log que não há canal configurado (sem o texto: pode conter um código).
"""

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Notificador(Protocol):
    def enviar_texto(self, telefone: str, texto: str) -> bool:
        """Envia `texto` para `telefone` (só dígitos, com DDI). Devolve True se foi aceito para envio."""
        ...


class NotificadorIndisponivel:
    def enviar_texto(self, telefone: str, texto: str) -> bool:
        log.warning("Notificador (WhatsApp) não configurado: mensagem não enviada.")
        return False


class NotificadorMemoria:
    """Falso para testes: guarda o que seria enviado."""

    def __init__(self) -> None:
        self.enviadas: list[tuple[str, str]] = []

    def enviar_texto(self, telefone: str, texto: str) -> bool:
        self.enviadas.append((telefone, texto))
        return True


_atual: Notificador = NotificadorIndisponivel()


def definir_notificador(n: Notificador) -> None:
    global _atual
    _atual = n


def get_notificador() -> Notificador:
    return _atual
