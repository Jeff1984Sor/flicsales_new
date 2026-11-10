"""Fechamento (oportunidade ganha) → recebíveis em RASCUNHO. Venda ≠ recebimento ≠ caixa.

"O fechamento prepara recebíveis em rascunho. Não registra pagamento nem movimenta o caixa."
Idempotente por (oportunidade, parcela): ganhar de novo não duplica — `parcelas_do_fechamento` devolve só as parcelas
que ainda não existem (a UNIQUE uq_titulo_oportunidade_parcela é a última barreira no banco).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain import RegraViolada
from app.domain.dinheiro import dividir_em_parcelas, positivo, somar_meses

# condição comercial (rótulo da tela) → número de parcelas mensais iguais
CONDICOES: dict[str, int] = {
    "Parcela única": 1,
    "2 parcelas iguais": 2,
    "3 parcelas iguais": 3,
    "4 parcelas iguais": 4,
    "6 parcelas iguais": 6,
    "12 parcelas iguais": 12,
}


@dataclass(frozen=True)
class ParcelaRascunho:
    oportunidade_id: int
    empresa_id: int
    parcela: int
    parcelas_total: int
    descricao: str
    valor: Decimal
    vencimento: date
    direcao: str = "receber"
    status: str = "rascunho"


def numero_de_parcelas(condicao: str | int) -> int:
    if isinstance(condicao, int):
        n = condicao
    elif condicao in CONDICOES:
        n = CONDICOES[condicao]
    else:
        raise RegraViolada("Condição comercial desconhecida.")
    if n < 1 or n > 60:
        raise RegraViolada("Informe de 1 a 60 parcelas.")
    return n


def validar_ganho(resultado: str) -> None:
    if resultado == "ganha":
        raise RegraViolada("Esta venda já foi processada")
    if resultado == "perdida":
        raise RegraViolada("Oportunidade perdida não pode ser ganha. Reabra antes.")


def parcelas_do_fechamento(*, oportunidade_id: int, titulo: str, empresa_id: int | None, valor, condicao: str | int,
                           primeiro_vencimento: date | None, existentes: set[int] | None = None) -> list[ParcelaRascunho]:
    """As parcelas (em rascunho) a criar. `existentes` = números de parcela já gerados para esta oportunidade.
    Vencimentos mensais a partir do primeiro; a última parcela absorve os centavos."""
    if empresa_id is None:
        raise RegraViolada("Informe a empresa para preparar os recebíveis.")
    total = positivo(valor, "Informe o valor acordado.")
    if primeiro_vencimento is None:
        raise RegraViolada("Informe o primeiro vencimento.")
    n = numero_de_parcelas(condicao)
    ja = existentes or set()
    valores = dividir_em_parcelas(total, n)
    return [
        ParcelaRascunho(
            oportunidade_id=oportunidade_id, empresa_id=empresa_id, parcela=i, parcelas_total=n,
            descricao=f"{titulo} • {i}/{n}", valor=valores[i - 1], vencimento=somar_meses(primeiro_vencimento, i - 1))
        for i in range(1, n + 1) if i not in ja
    ]
