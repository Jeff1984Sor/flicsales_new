"""Títulos a receber/a pagar, baixas e estornos (regras 1–4 do CLAUDE.md).

- status guardado: rascunho | aberto | parcial | liquidado | cancelado; "vencido" é DERIVADO (status_exibido).
- Confirmar título (rascunho → aberto) NÃO é baixa.
- Baixa: valor > 0 e ≤ saldo aberto; data entre a data-base da conta e hoje; conta cadastrada; a pagar só aprovado.
- Baixa nunca é apagada: corrigir é ESTORNAR (com motivo). Estorno devolve o valor ao saldo.
- Título com baixa ativa não tem valor editado nem é cancelado (estorne antes). Cancelar exige motivo.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain import RegraViolada
from app.domain.dinheiro import ZERO, arredondar, dinheiro

DIRECOES = ("receber", "pagar")
STATUS = ("rascunho", "aberto", "parcial", "liquidado", "cancelado")
STATUS_EXIBIVEIS = (*STATUS, "vencido")
EM_ABERTO = ("aberto", "parcial")  # contam na projeção de caixa e podem receber baixa
FORMAS = ("pix", "boleto", "transferencia", "cartao", "dinheiro", "outra")
APROVACOES = ("pendente", "aprovado")

MSG_VALOR_POSITIVO = "O valor deve ser positivo"
MSG_BAIXA_VALOR = "Valor deve ser positivo e não superar o saldo"
MSG_BAIXA_CONTA = "Selecione uma conta cadastrada"
MSG_BAIXA_DATA = "Data da baixa deve estar entre a data-base da conta e hoje"
MSG_APROVACAO = "Aprove o pagamento no controle de aprovações primeiro"
MSG_ESTORNE_EDITAR = "Estorne as baixas antes de editar o título"
MSG_ESTORNE_CANCELAR = "Estorne as baixas antes de cancelar"


@dataclass(frozen=True)
class BaixaInfo:
    valor: Decimal
    estornada: bool = False


def validar_direcao(direcao: str) -> str:
    if direcao not in DIRECOES:
        raise RegraViolada("Direção inválida: use receber ou pagar.")
    return direcao


def validar_valor(valor) -> Decimal:
    v = dinheiro(valor)
    if v <= 0:
        raise RegraViolada(MSG_VALOR_POSITIVO)
    return v


def exige_aprovacao(direcao: str) -> bool:
    """Conta a pagar só recebe baixa se aprovada (alçada em Aprovações)."""
    return direcao == "pagar"


def aprovacao_inicial(direcao: str) -> str | None:
    return "pendente" if exige_aprovacao(direcao) else None


def saldo_aberto(valor_original: Decimal, baixas: list[BaixaInfo]) -> Decimal:
    """valor original − baixas não estornadas."""
    pago = sum((dinheiro(b.valor) for b in baixas if not b.estornada), ZERO)
    return arredondar(dinheiro(valor_original) - pago)


def tem_baixa_ativa(baixas: list[BaixaInfo]) -> bool:
    return any(not b.estornada for b in baixas)


def status_por_saldo(status_atual: str, valor_original: Decimal, saldo: Decimal) -> str:
    """Recalcula o status de um título confirmado a partir do saldo. Rascunho e cancelado não mudam por aqui."""
    if status_atual in ("rascunho", "cancelado"):
        return status_atual
    if saldo <= 0:
        return "liquidado"
    if saldo < dinheiro(valor_original):
        return "parcial"
    return "aberto"


def status_exibido(status: str, vencimento: date, hoje: date) -> str:
    """O que a tela mostra: aberto/parcial com vencimento antes de hoje vira "vencido"."""
    if status in EM_ABERTO and vencimento < hoje:
        return "vencido"
    return status


def dias_em_atraso(status: str, vencimento: date, hoje: date) -> int:
    return (hoje - vencimento).days if status_exibido(status, vencimento, hoje) == "vencido" else 0


def validar_confirmacao(status: str) -> str:
    """Rascunho → aberto ("Recebível confirmado, sem baixa financeira"). Devolve o novo status."""
    if status != "rascunho":
        raise RegraViolada("Só títulos em rascunho podem ser confirmados.")
    return "aberto"


def validar_aprovacao(direcao: str, status: str, aprovacao: str | None) -> str:
    """Aprovação de conta a pagar (alçada). Devolve "aprovado"."""
    if direcao != "pagar":
        raise RegraViolada("Só contas a pagar passam por aprovação.")
    if status == "cancelado":
        raise RegraViolada("Título cancelado não pode ser aprovado.")
    if aprovacao == "aprovado":
        raise RegraViolada("Este pagamento já está aprovado.")
    return "aprovado"


def validar_baixa(*, direcao: str, status: str, aprovacao: str | None, saldo: Decimal, valor, data: date,
                  data_base_conta: date | None, hoje: date) -> Decimal:
    """Valida um recebimento/pagamento gerencial. `data_base_conta=None` = conta não cadastrada/inativa.
    Devolve o valor normalizado."""
    if status == "rascunho":
        raise RegraViolada("Confirme o título antes de registrar a baixa.")
    if status == "cancelado":
        raise RegraViolada("Título cancelado não recebe baixa.")
    if exige_aprovacao(direcao) and aprovacao != "aprovado":
        raise RegraViolada(MSG_APROVACAO)
    v = dinheiro(valor)
    if v <= 0 or v > dinheiro(saldo):
        raise RegraViolada(MSG_BAIXA_VALOR)
    if data_base_conta is None:
        raise RegraViolada(MSG_BAIXA_CONTA)
    if data < data_base_conta or data > hoje:
        raise RegraViolada(MSG_BAIXA_DATA)
    return v


def aplicar_baixa(*, valor_original: Decimal, saldo: Decimal, status: str, valor: Decimal) -> tuple[Decimal, str]:
    """(novo saldo, novo status) depois de uma baixa JÁ validada. Parcial mantém o saldo restante."""
    novo = arredondar(dinheiro(saldo) - dinheiro(valor))
    if novo < 0:
        raise RegraViolada(MSG_BAIXA_VALOR)
    return novo, status_por_saldo(status, valor_original, novo)


def aplicar_estorno(*, valor_original: Decimal, saldo: Decimal, status: str, valor_baixa: Decimal,
                    ja_estornada: bool, motivo: str | None) -> tuple[Decimal, str]:
    """(novo saldo, novo status) ao estornar uma baixa. A baixa fica no histórico com `estornada=True`."""
    if ja_estornada:
        raise RegraViolada("Esta baixa já foi estornada.")
    if not (motivo or "").strip():
        raise RegraViolada("Informe o motivo do estorno.")
    if status == "cancelado":
        raise RegraViolada("Título cancelado não tem baixa a estornar.")
    novo = arredondar(dinheiro(saldo) + dinheiro(valor_baixa))
    if novo > dinheiro(valor_original):
        raise RegraViolada("O estorno não pode deixar o saldo acima do valor original.")
    return novo, status_por_saldo(status, valor_original, novo)


def validar_edicao_valor(*, tem_baixa_ativa: bool, status: str, novo_valor) -> Decimal:
    """Título com baixa ativa não muda de valor. Devolve o valor normalizado (o saldo volta a ser o valor)."""
    if tem_baixa_ativa:
        raise RegraViolada(MSG_ESTORNE_EDITAR)
    if status in ("cancelado", "liquidado"):
        raise RegraViolada("Título cancelado ou liquidado não muda de valor.")
    return validar_valor(novo_valor)


def pode_editar_valor(tem_baixa_ativa: bool) -> bool:
    return not tem_baixa_ativa


def validar_cancelamento(*, status: str, tem_baixa_ativa: bool, motivo: str | None) -> str:
    """Devolve "cancelado". Nada é apagado: o título fica com motivo e data."""
    if status == "cancelado":
        raise RegraViolada("Este título já está cancelado.")
    if tem_baixa_ativa:
        raise RegraViolada(MSG_ESTORNE_CANCELAR)
    if not (motivo or "").strip():
        raise RegraViolada("Informe o motivo do cancelamento.")
    return "cancelado"


def pode_cancelar(status: str, tem_baixa_ativa: bool) -> bool:
    return status != "cancelado" and not tem_baixa_ativa


# ---------------------------------------------------------------- aging (Dashboards financeiros)
FAIXAS_AGING = ("a_vencer", "1_30", "31_60", "61_90", "90_mais")
ROTULOS_AGING = {"a_vencer": "A vencer", "1_30": "Vencidos 1–30 dias", "31_60": "Vencidos 31–60 dias",
                 "61_90": "Vencidos 61–90 dias", "90_mais": "Vencidos há mais de 90 dias"}


@dataclass(frozen=True)
class TituloAging:
    direcao: str
    status: str
    vencimento: date
    saldo: Decimal


@dataclass(frozen=True)
class FaixaAging:
    faixa: str
    rotulo: str
    valor: Decimal
    quantidade: int


def faixa_aging(vencimento: date, hoje: date) -> str:
    """A vencer (vence hoje ou depois) · 1–30 · 31–60 · 61–90 · 90+ dias de atraso."""
    dias = (hoje - vencimento).days
    if dias <= 0:
        return "a_vencer"
    if dias <= 30:
        return "1_30"
    if dias <= 60:
        return "31_60"
    if dias <= 90:
        return "61_90"
    return "90_mais"


def aging(titulos: list[TituloAging], hoje: date, direcao: str = "receber") -> list[FaixaAging]:
    """Saldo aberto por faixa de atraso. Só títulos confirmados em aberto (aberto/parcial) com saldo > 0;
    rascunho, cancelado e liquidado ficam fora. O pipeline comercial nunca entra aqui."""
    valores = dict.fromkeys(FAIXAS_AGING, ZERO)
    qtd = dict.fromkeys(FAIXAS_AGING, 0)
    for t in titulos:
        if t.direcao != direcao or t.status not in EM_ABERTO or dinheiro(t.saldo) <= 0:
            continue
        f = faixa_aging(t.vencimento, hoje)
        valores[f] += dinheiro(t.saldo)
        qtd[f] += 1
    return [FaixaAging(f, ROTULOS_AGING[f], arredondar(valores[f]), qtd[f]) for f in FAIXAS_AGING]
