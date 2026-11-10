"""Worker (systemd `flicsales-worker`): tarefas periódicas fora do ciclo das requisições.

Cada módulo registra suas tarefas com `registrar_tarefa` em `app/modules/<nome>/tarefas.py` (ex.: gerar competências
de recorrências, executar automações, lembretes de vencimento). Não há broker: o estado fica no banco.
Rodar: `uv run python -m app.worker`.

Um banco por organização (app.core.tenancy): cada tarefa roda uma vez para CADA organização ativa, dentro de
`tenancy.usando(org)` (a lista é relida a cada volta; cada organização tem o seu relógio). Tarefas do banco de controle
(`global_=True`) rodam uma vez só, sem organização. Com um banco só, tudo roda uma vez.
"""

import importlib
import logging
import pkgutil
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import app.controle.sincronia  # noqa: F401  (catálogo de logins do controle)
import app.modules as modulos_pkg
from app.core import tenancy
from app.core.db import SessionLocal
from app.core.ratelimit import LimiteBanco

log = logging.getLogger("worker")
_parar = threading.Event()


@dataclass
class Tarefa:
    nome: str
    intervalo_s: float
    fn: Callable[[], None]
    proxima: float = field(default=0.0)
    global_: bool = False  # True = tarefa do banco de controle: uma vez só, sem organização
    proximas: dict[str, float] = field(default_factory=dict)  # um banco por organização: o relógio de cada uma


TAREFAS: list[Tarefa] = []


def registrar_tarefa(nome: str, intervalo_s: float, fn: Callable[[], None], *, global_: bool = False) -> None:
    TAREFAS.append(Tarefa(nome, intervalo_s, fn, global_=global_))


def _limpar_rate_limit() -> None:
    with SessionLocal() as db:
        LimiteBanco.limpar_antigos(db)


registrar_tarefa("limpar-rate-limit", 3600, _limpar_rate_limit)


def _descobrir_tarefas() -> None:
    """Módulos podem expor `app/modules/<nome>/tarefas.py` que chama `registrar_tarefa` ao ser importado."""
    for info in pkgutil.iter_modules(modulos_pkg.__path__):
        try:
            importlib.import_module(f"app.modules.{info.name}.tarefas")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{info.name}.tarefas":
                raise


def _organizacoes() -> list:
    """As organizações ativas do controle (relidas a cada volta)."""
    from app.controle import service

    return service.ativas()


def _rodar(tarefa: Tarefa, rotulo: str, feitas: list[str]) -> None:
    try:
        tarefa.fn()
        feitas.append(rotulo)
    except Exception:
        log.exception("Tarefa '%s' falhou", rotulo)


def executar_pendentes(agora_s: float | None = None) -> list[str]:
    """Roda as tarefas vencidas; uma falha não derruba as demais. Devolve os nomes executados (testável); no modo um
    banco por organização, as tarefas por organização aparecem como "nome@slug"."""
    t = time.monotonic() if agora_s is None else agora_s
    feitas: list[str] = []
    multi = tenancy.multi()
    orgs = _organizacoes() if multi else []
    for tarefa in TAREFAS:
        if tarefa.global_ or not multi:
            if t < tarefa.proxima:
                continue
            tarefa.proxima = t + tarefa.intervalo_s
            with tenancy.usando(None):
                _rodar(tarefa, tarefa.nome, feitas)
            continue
        for org in orgs:
            if t < tarefa.proximas.get(org.slug, 0.0):
                continue
            tarefa.proximas[org.slug] = t + tarefa.intervalo_s
            with tenancy.usando(org):
                _rodar(tarefa, f"{tarefa.nome}@{org.slug}", feitas)
    return feitas


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    signal.signal(signal.SIGTERM, lambda *_: _parar.set())
    signal.signal(signal.SIGINT, lambda *_: _parar.set())
    _descobrir_tarefas()
    log.info("Worker iniciado com %d tarefa(s)", len(TAREFAS))
    while not _parar.is_set():
        executar_pendentes()
        _parar.wait(5)
    log.info("Worker encerrado")


if __name__ == "__main__":
    # `python -m app.worker` roda este arquivo como `__main__`, um módulo DIFERENTE de `app.worker`; as tarefas dos
    # módulos se registram em `app.worker.TAREFAS`.
    import app.worker

    app.worker.main()
