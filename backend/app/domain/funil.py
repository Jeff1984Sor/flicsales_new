"""Funil e oportunidades: etapas, forecast ponderado, tempo na etapa, ganho e perda.

- Funil: ≥ 2 etapas únicas; "Ganha" e "Perdida" são resultados finais, não etapas.
- Probabilidade da etapa é parâmetro (0–100), não previsão de IA. Forecast ponderado = Σ valor × probabilidade.
- Perdida exige motivo; nada é excluído, só encerrado. Ganha não muda valor sem revisão financeira.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain import RegraViolada
from app.domain.cadastro import chave_de_nome
from app.domain.dinheiro import ZERO, arredondar, dinheiro

RESULTADOS = ("aberta", "ganha", "perdida")
NOMES_PROIBIDOS = {"ganha", "perdida", "ganho", "perdido"}
MSG_ETAPAS = "Defina pelo menos duas etapas únicas, sem Ganha ou Perdida"


@dataclass(frozen=True)
class ItemForecast:
    valor: Decimal
    probabilidade: int  # 0–100


def validar_etapas(nomes: list[str]) -> list[str]:
    limpos = [" ".join((n or "").split()) for n in nomes]
    chaves = [chave_de_nome(n) for n in limpos]
    if (len(limpos) < 2 or any(not n for n in limpos) or len(set(chaves)) != len(chaves)
            or any(c in NOMES_PROIBIDOS for c in chaves)):
        raise RegraViolada(MSG_ETAPAS)
    return limpos


def validar_probabilidade(p: int) -> int:
    if not isinstance(p, int) or not 0 <= p <= 100:
        raise RegraViolada("A probabilidade da etapa vai de 0 a 100%.")
    return p


def validar_limite_dias(dias: int | None) -> int | None:
    if dias is not None and (not isinstance(dias, int) or dias < 1):
        raise RegraViolada("O limite de dias da etapa deve ser um número inteiro positivo.")
    return dias


def forecast_ponderado(itens: list[ItemForecast]) -> Decimal:
    total = sum((dinheiro(i.valor) * Decimal(validar_probabilidade(i.probabilidade)) / 100 for i in itens), ZERO)
    return arredondar(total)


def dias_na_etapa(entrou_em: date | None, hoje: date) -> int:
    return max((hoje - entrou_em).days, 0) if entrou_em else 0


def alem_do_limite(entrou_em: date | None, limite_dias: int | None, hoje: date) -> bool:
    """Passou do limite da etapa? (Dias na etapa > limite.)"""
    return bool(limite_dias) and dias_na_etapa(entrou_em, hoje) > limite_dias


def validar_perda(motivo: str | None) -> str:
    if not (motivo or "").strip():
        raise RegraViolada("Informe o motivo da perda")
    return motivo.strip()


def validar_alteracao_valor(resultado: str) -> None:
    """Ganha não muda de valor por aqui: o ajuste é revisão financeira dos títulos de origem."""
    if resultado == "ganha":
        raise RegraViolada("Venda ganha: ajuste valores por revisão financeira, preservando títulos de origem")


def validar_valores(valor_unico, valor_recorrente_mensal) -> tuple[Decimal, Decimal]:
    u = dinheiro(valor_unico if valor_unico is not None else 0)
    m = dinheiro(valor_recorrente_mensal if valor_recorrente_mensal is not None else 0)
    if u < 0 or m < 0:
        raise RegraViolada("Valores da oportunidade não podem ser negativos.")
    return u, m
