"""Tarefas do worker da Orquestração: o motor de automações roda a cada 5 minutos, uma vez por organização ativa.

Idempotente (chave única por automação+registro+ocorrência): rodar de novo, ou em dois workers, não duplica.
"""

import logging

from app.core.db import SessionLocal, hoje
from app.modules.orquestracao import motor
from app.worker import registrar_tarefa

log = logging.getLogger(__name__)
INTERVALO_S = 300


def rodar_automacoes() -> dict[str, int]:
    with SessionLocal() as db:
        contagem = motor.executar(db, hoje())
    if contagem:
        log.info("Automações: %s", contagem)
    return contagem


registrar_tarefa("automacoes", INTERVALO_S, rodar_automacoes)
