"""Tarefas periódicas do Financeiro (worker, uma vez por organização ativa).

`gerar-competencias-recorrencias`: para cada recorrência ATIVA, gera em RASCUNHO o título da próxima competência
cujo vencimento cai entre hoje e hoje + 30 dias (app.domain.recorrencia.proximas_competencias). Idempotente: a
competência que já tem título não é gerada de novo (domínio + UNIQUE (origem_recorrencia_id, competencia)).
Competências passadas que ficaram sem título não são geradas sozinhas: a tela "Gerar competência" cuida delas.
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, hoje
from app.domain import RegraViolada
from app.domain.recorrencia import proximas_competencias
from app.modules.financeiro import operacoes as op
from app.modules.financeiro.models import Recorrencia
from app.worker import registrar_tarefa

log = logging.getLogger("worker.financeiro")
HORIZONTE_DIAS = 30


def gerar_competencias_pendentes(db: Session, dia: date, horizonte_dias: int = HORIZONTE_DIAS) -> list[int]:
    """Gera os títulos devidos e devolve os ids criados. Faz commit por título (uma falha não derruba as outras)."""
    criados: list[int] = []
    for rec in list(db.scalars(select(Recorrencia).where(Recorrencia.situacao == "ativa").order_by(Recorrencia.id))):
        comps = proximas_competencias(situacao=rec.situacao, inicio=rec.inicio, fim=rec.fim,
                                      frequencia=rec.frequencia, dia_vencimento=rec.dia_vencimento, hoje=dia,
                                      horizonte_dias=horizonte_dias, existentes=op.competencias_geradas(db, rec.id))
        for comp in comps:
            try:
                t = op.gerar_competencia(db, rec, comp, None)
                db.commit()
                criados.append(t.id)
            except (RegraViolada, IntegrityError) as e:  # outra execução gerou antes: segue
                db.rollback()
                log.info("Recorrência %s / %s não gerada: %s", rec.id, comp, e)
    return criados


def _tarefa() -> None:
    with SessionLocal() as db:
        criados = gerar_competencias_pendentes(db, hoje())
        if criados:
            log.info("Recorrências: %d título(s) em rascunho gerado(s)", len(criados))


registrar_tarefa("gerar-competencias-recorrencias", 6 * 3600, _tarefa)
