"""Um banco por organização (cliente da FlicSales). Portado do MayaFit/MayaJus (app/core/tenancy.py).

Sem o banco de controle (`BANCO_CONTROLE`, padrão `flicsalesos_controle`; no mesmo servidor do DATABASE_URL; no
SQLite, `data/<BANCO_CONTROLE>.db`) o sistema
roda com um banco só e a pasta `storage/` (dev e testes). Quando ele existe, o modo liga sozinho (nada no .env): o
banco de controle (app/controle) diz quais organizações existem e em qual banco mora cada uma; a organização do pedido
atual fica numa ContextVar e é ela que decide o banco de toda sessão (`SessionLocal`, `get_db`) e a pasta dos
arquivos. Quem define:

- a API, a cada pedido (app/core/organizacao_http.py): pelo token (claim `org`) ou pelo endereço da organização;
- o login, pelo endereço ou pelo catálogo de logins do controle;
- o worker, que percorre as organizações ativas.

A organização "principal" (banco = None) usa o `DATABASE_URL` e a pasta `storage/`.
Módulos de negócio NÃO têm `tenant_id`: o isolamento é o banco.
"""

import contextvars
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from app.core.config import settings


@dataclass(frozen=True)
class Organizacao:
    slug: str
    banco: str | None  # None = o banco principal (DATABASE_URL)


class OrganizacaoNaoIdentificada(RuntimeError):
    """Pedido sem organização no modo multi: vira 401 "Sessão expirada" (main.py)."""


def banco_controle() -> str:
    """Nome do banco de controle (BANCO_CONTROLE no .env; padrão `flicsalesos_controle`)."""
    return settings.banco_controle


def __getattr__(nome: str) -> Any:
    """Compatibilidade: `tenancy.BANCO_CONTROLE` (lido pelo deploy/instalar.sh) agora vem do .env."""
    if nome == "BANCO_CONTROLE":
        return banco_controle()
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")


CLAIM = "org"  # claim do JWT com o slug da organização

_atual: contextvars.ContextVar[Organizacao | None] = contextvars.ContextVar("organizacao", default=None)
_engines: dict[str, Engine] = {}
_trava = threading.Lock()
_url_forcada: str | None = None  # testes apontam para um controle próprio
_multi: bool | None = None


def forcar_controle(url: str | None) -> None:
    """Testes: usa este banco de controle (None = volta a detectar)."""
    global _url_forcada, _multi
    _url_forcada, _multi = url, None


def url_controle() -> str:
    return _url_forcada or url_do_banco(banco_controle())


def _controle_existe() -> bool:
    from sqlalchemy import text

    from app.core.db import engine

    url = make_url(url_do_banco(banco_controle()))
    if url.get_backend_name() == "sqlite":
        return Path(url.database or "").exists()
    with engine.connect() as conn:  # se o servidor estiver fora, falha alto (não liga o modo errado)
        return bool(conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": banco_controle()}))


def multi() -> bool:
    """Um banco por organização? Liga sozinho quando o banco de controle existe (decidido uma vez por processo)."""
    global _multi
    if _multi is None:
        _multi = _url_forcada is not None or _controle_existe()
    return _multi


def atual() -> Organizacao | None:
    return _atual.get()


def definir(org: Organizacao | None) -> contextvars.Token:
    return _atual.set(org)


def resetar(token: contextvars.Token) -> None:
    _atual.reset(token)


@contextmanager
def usando(org: Organizacao | None) -> Iterator[None]:
    token = _atual.set(org)
    try:
        yield
    finally:
        _atual.reset(token)


def url_do_banco(banco: str) -> str:
    """Mesmo servidor e credenciais do DATABASE_URL, outro banco (no SQLite, outro arquivo ao lado)."""
    url = make_url(settings.database_url)
    if url.get_backend_name() == "sqlite":
        return f"sqlite:///{Path(url.database or 'data/flicsales.db').with_name(f'{banco}.db').as_posix()}"
    return url.set(database=banco).render_as_string(hide_password=False)


def engine_do(banco: str | None) -> Engine:
    from app.core.db import engine, ligar_pragmas_sqlite

    if banco is None:
        return engine
    with _trava:
        if banco not in _engines:
            url = url_do_banco(banco)
            if url.startswith("sqlite"):
                e = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
                ligar_pragmas_sqlite(e)
            else:  # servidor compartilhado: poucas conexões por organização
                e = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=3, pool_recycle=1800)
            _engines[banco] = e
        return _engines[banco]


def descartar_engines() -> None:
    """Testes/CLI: fecha as conexões dos bancos das organizações."""
    with _trava:
        for e in _engines.values():
            e.dispose()
        _engines.clear()


def engine_atual() -> Engine:
    org = atual()
    if org is None:
        if multi():
            raise OrganizacaoNaoIdentificada("Organização não identificada para este acesso.")
        return engine_do(None)
    return engine_do(org.banco)


def pasta_base() -> Path:
    """Raiz dos arquivos da organização atual (a principal em storage/, as demais em storage/organizacoes/<slug>)."""
    org = atual()
    if org is None or org.banco is None:
        return Path(settings.storage_dir)
    return Path(settings.storage_dir) / "organizacoes" / org.slug


def com_organizacao(fn: Callable) -> Callable:
    """Leva a organização atual para outra thread (ThreadPoolExecutor/threading não copiam a ContextVar)."""
    ctx = contextvars.copy_context()
    return lambda *a, **kw: ctx.run(fn, *a, **kw)


def claims() -> dict[str, Any]:
    """A organização que viaja nos tokens emitidos agora (`org`). Vazio com um banco só."""
    org = atual()
    return {CLAIM: org.slug} if org is not None and multi() else {}


def token_da_organizacao_atual(payload: dict[str, Any]) -> bool:
    """O token foi emitido para a organização deste pedido? (Sempre True com um banco só.)"""
    if not multi():
        return True
    org = atual()
    return org is not None and payload.get(CLAIM) == org.slug
