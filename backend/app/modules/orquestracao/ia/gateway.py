"""Gateway da IA para a orquestração. Usa `app.core.ia` (OpenAI/Gemini configurados na tela) sem alterá-lo.

Nos testes, injete um gerador falso: `gateway.definir_gerador(lambda db, sistema, usuario: {...})` — com ele a IA conta
como ligada e nenhum provedor real é chamado. `definir_gerador(None)` volta ao provedor configurado.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core import ia as core_ia

Gerador = Callable[[Session, str, str], dict[str, Any]]
_gerador: Gerador | None = None


def definir_gerador(fn: Gerador | None) -> None:
    global _gerador
    _gerador = fn


def ligada(db: Session) -> bool:
    return _gerador is not None or core_ia.ligada(db)


def descricao(db: Session) -> tuple[str | None, str | None]:
    """(provedor, modelo) para registrar na mensagem."""
    if _gerador is not None:
        return "teste", "falso"
    cfg = core_ia.config(db)
    return cfg.provedor, cfg.modelo


def gerar(db: Session, sistema: str, usuario: str) -> Any:
    """Levanta `core_ia.IAIndisponivel` (mensagem pronta) se a IA estiver desligada ou falhar."""
    if _gerador is not None:
        return _gerador(db, sistema, usuario)
    p = core_ia.provedor_ativo(db)
    return core_ia.gerar_json(p, sistema, usuario)
