"""Caixa gerencial: saldo por conta, projeção e transferências. O pipeline comercial NUNCA compõe saldo.

saldo da conta  = saldo inicial + recebimentos − pagamentos (baixas não estornadas) − transferências enviadas
                  + transferências recebidas
projeção        = saldo + entradas abertas − saídas abertas (títulos aberto/parcial pelo SALDO aberto; rascunho,
                  cancelado e liquidado ficam fora)
Ex. do protótipo: 25.000 + 19.300 − 7.200 = 37.100.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain import RegraViolada
from app.domain.dinheiro import ZERO, arredondar, dinheiro
from app.domain.titulos import EM_ABERTO


@dataclass(frozen=True)
class Conta:
    id: int
    saldo_inicial: Decimal
    data_base: date


@dataclass(frozen=True)
class Movimento:
    """Baixa de um título: direção do título ('receber' entra, 'pagar' sai)."""

    conta_id: int
    direcao: str
    valor: Decimal
    estornada: bool = False


@dataclass(frozen=True)
class TransferenciaInfo:
    conta_origem_id: int
    conta_destino_id: int
    valor: Decimal


@dataclass(frozen=True)
class TituloAberto:
    direcao: str
    status: str
    saldo: Decimal


@dataclass(frozen=True)
class Projecao:
    saldo_atual: Decimal
    entradas_abertas: Decimal
    saidas_abertas: Decimal
    saldo_projetado: Decimal
    formula: str


def saldo_por_conta(contas: list[Conta], movimentos: list[Movimento],
                    transferencias: list[TransferenciaInfo]) -> dict[int, Decimal]:
    saldos = {c.id: dinheiro(c.saldo_inicial) for c in contas}
    for m in movimentos:
        if m.estornada or m.conta_id not in saldos:
            continue
        sinal = 1 if m.direcao == "receber" else -1
        saldos[m.conta_id] += sinal * dinheiro(m.valor)
    for t in transferencias:
        if t.conta_origem_id in saldos:
            saldos[t.conta_origem_id] -= dinheiro(t.valor)
        if t.conta_destino_id in saldos:
            saldos[t.conta_destino_id] += dinheiro(t.valor)
    return {k: arredondar(v) for k, v in saldos.items()}


def saldo_gerencial(contas: list[Conta], movimentos: list[Movimento],
                    transferencias: list[TransferenciaInfo]) -> Decimal:
    """Soma das contas (transferência entre contas não altera o total: não é receita nem despesa)."""
    return arredondar(sum(saldo_por_conta(contas, movimentos, transferencias).values(), ZERO))


def projecao(saldo_atual: Decimal, titulos: list[TituloAberto]) -> Projecao:
    entradas = sum((dinheiro(t.saldo) for t in titulos if t.status in EM_ABERTO and t.direcao == "receber"), ZERO)
    saidas = sum((dinheiro(t.saldo) for t in titulos if t.status in EM_ABERTO and t.direcao == "pagar"), ZERO)
    s = dinheiro(saldo_atual)
    final = arredondar(s + entradas - saidas)
    return Projecao(s, arredondar(entradas), arredondar(saidas), final,
                    "saldo gerencial + entradas abertas − saídas abertas")


def validar_transferencia(*, origem: Conta | None, destino: Conta | None, valor, data: date, hoje: date) -> Decimal:
    v = dinheiro(valor) if valor is not None else ZERO
    if origem is None or destino is None or origem.id == destino.id or v <= 0:
        raise RegraViolada("Selecione contas diferentes e valor positivo")
    if data < max(origem.data_base, destino.data_base) or data > hoje:
        raise RegraViolada("Data deve respeitar as datas-base das contas e hoje")
    return v


def validar_edicao_conta(*, tem_movimento: bool, muda_saldo_inicial: bool, muda_data_base: bool) -> None:
    """Conta com movimento preserva saldo inicial e data-base."""
    if tem_movimento and (muda_saldo_inicial or muda_data_base):
        raise RegraViolada("Conta com movimentos: preserve saldo inicial e data-base.")
