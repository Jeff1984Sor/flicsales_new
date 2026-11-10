"""Recorrência: um título em RASCUNHO por competência (AAAA-MM), sem duplicar, só dentro da vigência e alinhado à
frequência (mensal/trimestral/anual, contada a partir do mês de início). Dia de vencimento 1–28."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain import RegraViolada
from app.domain.dinheiro import dinheiro

FREQUENCIAS = {"mensal": 1, "trimestral": 3, "anual": 12}
SITUACOES = ("ativa", "pausada", "cancelada")
_COMP = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class TituloDaCompetencia:
    recorrencia_id: int
    competencia: str
    vencimento: date
    valor: Decimal
    status: str = "rascunho"


def _mes(competencia: str) -> int:
    m = _COMP.match(competencia or "")
    if not m:
        raise RegraViolada("Competência inválida (use AAAA-MM).")
    return int(m.group(1)) * 12 + int(m.group(2)) - 1


def competencia_de(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def validar_recorrencia(*, valor_ciclo, dia_vencimento: int, inicio: date, fim: date, frequencia: str) -> Decimal:
    try:
        v = dinheiro(valor_ciclo)
    except RegraViolada:
        v = Decimal("0")
    if v <= 0 or not isinstance(dia_vencimento, int) or not 1 <= dia_vencimento <= 28:
        raise RegraViolada("Informe valor positivo e dia inteiro entre 1 e 28")
    if fim < inicio:
        raise RegraViolada("A data final deve ser igual ou posterior ao início")
    if frequencia not in FREQUENCIAS:
        raise RegraViolada("Frequência inválida: use mensal, trimestral ou anual.")
    return v


def validar_competencia(*, situacao: str, inicio: date, fim: date, frequencia: str, competencia: str,
                        existentes: set[str]) -> None:
    """Ordem das mensagens igual à do protótipo: vigência → duplicidade → frequência."""
    if situacao != "ativa":
        raise RegraViolada("A recorrência deve estar ativa")
    mes = _mes(competencia)
    if mes < _mes(competencia_de(inicio)) or mes > _mes(competencia_de(fim)):
        raise RegraViolada("Competência fora da vigência")
    if competencia in existentes:
        raise RegraViolada("Título desta competência já existe")
    if (mes - _mes(competencia_de(inicio))) % FREQUENCIAS[frequencia] != 0:
        raise RegraViolada("Competência incompatível com a frequência")


def vencimento_da_competencia(competencia: str, dia_vencimento: int) -> date:
    mes = _mes(competencia)
    return date(mes // 12, mes % 12 + 1, dia_vencimento)


def titulo_da_competencia(*, recorrencia_id: int, situacao: str, inicio: date, fim: date, frequencia: str,
                          dia_vencimento: int, valor_ciclo, competencia: str,
                          existentes: set[str]) -> TituloDaCompetencia:
    validar_competencia(situacao=situacao, inicio=inicio, fim=fim, frequencia=frequencia, competencia=competencia,
                        existentes=existentes)
    return TituloDaCompetencia(recorrencia_id, competencia, vencimento_da_competencia(competencia, dia_vencimento),
                               dinheiro(valor_ciclo))


def competencias_a_gerar(*, situacao: str, inicio: date, fim: date, frequencia: str, ate: date,
                         existentes: set[str]) -> list[str]:
    """Competências devidas até `ate` (inclusive) que ainda não têm título (para o worker)."""
    if situacao != "ativa" or frequencia not in FREQUENCIAS:
        return []
    passo = FREQUENCIAS[frequencia]
    primeiro, ultimo = _mes(competencia_de(inicio)), min(_mes(competencia_de(fim)), _mes(competencia_de(ate)))
    out = []
    for mes in range(primeiro, ultimo + 1, passo):
        comp = f"{mes // 12:04d}-{mes % 12 + 1:02d}"
        if comp not in existentes:
            out.append(comp)
    return out
