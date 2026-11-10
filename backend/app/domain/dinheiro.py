"""Dinheiro: sempre Decimal, 2 casas, ROUND_HALF_UP. Nunca float."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.domain import RegraViolada

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")


def dinheiro(valor: Decimal | int | str | None) -> Decimal:
    """Converte para Decimal com 2 casas (ROUND_HALF_UP). `float` é recusado (perde centavos); use str."""
    if valor is None:
        raise RegraViolada("Informe o valor.")
    if isinstance(valor, float):
        raise TypeError("Use Decimal ou str para dinheiro, nunca float.")
    try:
        return Decimal(str(valor).strip().replace(",", ".") if isinstance(valor, str) else valor).quantize(
            CENTAVO, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise RegraViolada("Valor inválido.") from None


def arredondar(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def positivo(valor: Decimal | int | str | None, mensagem: str = "O valor deve ser positivo") -> Decimal:
    v = dinheiro(valor)
    if v <= 0:
        raise RegraViolada(mensagem)
    return v


def dividir_em_parcelas(total: Decimal | int | str, n: int) -> list[Decimal]:
    """Divide `total` em `n` parcelas iguais (ROUND_HALF_UP); a ÚLTIMA absorve a diferença de centavos.
    A soma das parcelas é sempre exatamente o total. Ex.: 100,00 / 3 = 33,33 + 33,33 + 33,34."""
    t = positivo(total)
    if not isinstance(n, int) or n < 1:
        raise RegraViolada("Informe ao menos uma parcela.")
    base = arredondar(t / n)
    parcelas = [base] * (n - 1) + [t - base * (n - 1)]
    if any(p <= 0 for p in parcelas):
        raise RegraViolada(f"Valor insuficiente para {n} parcelas.")
    return parcelas


def somar_meses(d: date, meses: int) -> date:
    """Mesmo dia `meses` depois; se o mês não tem o dia (31/01 + 1), usa o último dia do mês."""
    import calendar

    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def formatar_brl(valor: Decimal) -> str:
    """R$ 1.234,56 (para textos de evidência; a tela formata por conta própria)."""
    v = arredondar(valor)
    sinal = "-" if v < 0 else ""
    inteiro, _, cent = f"{abs(v):.2f}".partition(".")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}R$ {'.'.join(grupos)},{cent}"
