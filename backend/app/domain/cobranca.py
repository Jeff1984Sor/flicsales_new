"""Cobranças e acordos: acompanhamento de um título A RECEBER (nunca a pagar).

- Situações: em acompanhamento · promessa de pagamento · em contestação · resolvida.
- Promessa de pagamento exige data prometida; valor prometido, se informado, é positivo e não supera o saldo aberto.
- Histórico/acordo é obrigatório (é o registro do que foi combinado).
- "Em contestação" SUSPENDE a cobrança automática do título (a automação de cobrança deve respeitar), assim como
  título liquidado, cancelado ou ainda em rascunho ("suspende ao receber/cancelar/contestar").
"""

from datetime import date
from decimal import Decimal

from app.domain import RegraViolada
from app.domain.dinheiro import dinheiro
from app.domain.titulos import EM_ABERTO

SITUACOES = ("em_acompanhamento", "promessa_pagamento", "em_contestacao", "resolvida")
ROTULOS_SITUACAO = {"em_acompanhamento": "Em acompanhamento", "promessa_pagamento": "Promessa de pagamento",
                    "em_contestacao": "Em contestação", "resolvida": "Resolvida"}
CANAIS = ("email", "ligacao", "whatsapp")


def validar_cobranca(*, titulo_direcao: str, titulo_status: str, titulo_saldo: Decimal, situacao: str, canal: str,
                     data_prometida: date | None, valor_prometido, historico: str | None,
                     nova: bool = True) -> Decimal | None:
    """Valida a cobrança/acordo. Devolve o valor prometido normalizado (ou None).
    `nova=False` (edição) permite registrar o desfecho mesmo depois de o título ser liquidado/cancelado."""
    if titulo_direcao != "receber":
        raise RegraViolada("Cobrança é ligada a um título a receber.")
    if nova and titulo_status not in EM_ABERTO:
        raise RegraViolada("Só títulos confirmados com saldo em aberto entram em cobrança.")
    if situacao not in SITUACOES:
        raise RegraViolada("Situação inválida.")
    if canal not in CANAIS:
        raise RegraViolada("Canal inválido: use e-mail, ligação ou WhatsApp.")
    if not (historico or "").strip():
        raise RegraViolada("Registre o histórico ou o acordo.")
    if situacao == "promessa_pagamento" and data_prometida is None:
        raise RegraViolada("Promessa de pagamento exige a data prometida.")
    if valor_prometido is None or valor_prometido == "":
        return None
    v = dinheiro(valor_prometido)
    if v <= 0 or (nova and v > dinheiro(titulo_saldo)):
        raise RegraViolada("Valor prometido deve ser positivo e não superar o saldo do título.")
    return v


def cobranca_suspensa(*, titulo_status: str, situacoes: list[str]) -> bool:
    """A automação de cobrança NÃO deve agir: título recebido/cancelado/rascunho ou com cobrança em contestação."""
    if titulo_status in ("liquidado", "cancelado", "rascunho"):
        return True
    return "em_contestacao" in situacoes
