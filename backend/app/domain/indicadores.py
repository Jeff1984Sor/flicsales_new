"""Indicadores calculados em CÓDIGO, com fórmula visível. A IA interpreta evidências, não inventa número.
Sem ranking de pessoas.

conversão = ganhas ÷ (ganhas + perdidas)          ex.: 8 ÷ 24 = 33,3%
ticket    = receita ganha ÷ vendas ganhas         ex.: 160.000 ÷ 8 = 20.000
ciclo     = mediana de dias entre criação e ganho
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from app.domain.dinheiro import arredondar, dinheiro

FORMULAS = {
    "conversao": "ganhas ÷ (ganhas + perdidas) no período",
    "receita_ganha": "soma do valor único das oportunidades ganhas no período",
    "ticket_medio": "receita ganha ÷ quantidade de vendas ganhas",
    "ciclo_mediano": "mediana de dias entre a criação e o ganho",
    "forecast_ponderado": "Σ valor único × probabilidade da etapa (oportunidades abertas)",
}


def conversao(ganhas: int, perdidas: int) -> Decimal | None:
    """Percentual com 1 casa (33,3). None sem oportunidades encerradas."""
    encerradas = ganhas + perdidas
    if encerradas <= 0:
        return None
    return (Decimal(ganhas) * 100 / Decimal(encerradas)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def ticket_medio(receita, vendas: int) -> Decimal | None:
    if vendas <= 0:
        return None
    return arredondar(dinheiro(receita) / vendas)


def ciclo_mediano(pares: list[tuple[date, date]]) -> Decimal | None:
    """Mediana de dias (criação, ganho). None sem vendas."""
    dias = [(g - c).days for c, g in pares]
    if not dias:
        return None
    return Decimal(str(median(dias))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def apuracao_meta(realizado, alvo) -> Decimal | None:
    """% da meta atingida (1 casa)."""
    a = Decimal(str(alvo))
    if a <= 0:
        return None
    return (Decimal(str(realizado)) * 100 / a).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
