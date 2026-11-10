"""Proposta: quantidade > 0, desconto 0–100%, desconto > 0 exige justificativa.
total = quantidade × preço unitário × (1 − desconto/100). "Aceita" não fecha a oportunidade sozinha."""

from decimal import Decimal, InvalidOperation

from app.domain import RegraViolada
from app.domain.dinheiro import arredondar, dinheiro

STATUS = ("rascunho", "em_aprovacao", "aprovada_internamente", "enviada", "aceita", "recusada")
MSG_QTD_DESCONTO = "Quantidade deve ser positiva e desconto entre 0 e 100%"


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise RegraViolada(MSG_QTD_DESCONTO) from None


def calcular_total(quantidade, preco_unitario, desconto_pct=0) -> Decimal:
    q, d = _dec(quantidade), _dec(desconto_pct or 0)
    return arredondar(q * dinheiro(preco_unitario) * (Decimal(1) - d / 100))


def validar_proposta(*, quantidade, preco_unitario, desconto_pct, justificativa_desconto: str | None) -> Decimal:
    """Devolve o total calculado."""
    q, d = _dec(quantidade), _dec(desconto_pct or 0)
    if q <= 0 or d < 0 or d > 100:
        raise RegraViolada(MSG_QTD_DESCONTO)
    if dinheiro(preco_unitario) < 0:
        raise RegraViolada("O preço unitário não pode ser negativo.")
    if d > 0 and not (justificativa_desconto or "").strip():
        raise RegraViolada("Registre a justificativa do desconto")
    return calcular_total(q, preco_unitario, d)


def exige_aprovacao_desconto(desconto_pct) -> bool:
    """Desconto > 0 passa por Aprovações (FIN-06) antes de enviar."""
    return _dec(desconto_pct or 0) > 0


def proxima_versao(versoes_existentes: list[int]) -> int:
    """Duplicar proposta incrementa a versão."""
    return max(versoes_existentes, default=0) + 1
