"""Produtos e serviços (contrato Núcleo parte 2, §3): desconto padrão e recorrência. Funções puras.

Desconto: `desconto_tipo` percentual|valor e `desconto_valor` andam juntos (os dois ou nenhum). Percentual 0–100;
valor ≥ 0 e ≤ preço de referência (quando há preço).

Recorrência (só com `recorrente=True`): `frequencia` diaria|semanal|mensal|semestral|anual, `intervalo` ≥ 1 ("a cada
N dias/semanas/meses/anos"; semestral é sempre 1) e `dias_semana` (seg…dom, obrigatório na semanal; vazio nas
outras). `recorrente=False` limpa os três. `descrever_recorrencia` dá o texto pronto para a tela.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain import RegraViolada

TIPOS_DESCONTO = ("percentual", "valor")
FREQUENCIAS = ("diaria", "semanal", "mensal", "semestral", "anual")
DIAS_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
ROTULO_FREQUENCIA = {"diaria": "Diária", "semanal": "Semanal", "mensal": "Mensal", "semestral": "Semestral",
                     "anual": "Anual"}
FREQUENCIA_PADRAO = "mensal"
_CEM = Decimal("100")
_CENTAVO = Decimal("0.01")


def _decimal(v: Any, o_que: str) -> Decimal:
    if isinstance(v, bool):
        raise RegraViolada(f"Informe {o_que} como número.")
    try:
        d = Decimal(str(v).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise RegraViolada(f"Informe {o_que} como número.") from None
    if not d.is_finite():
        raise RegraViolada(f"Informe {o_que} como número.")
    return d


def validar_desconto(tipo: str | None, valor: Any, preco_referencia: Decimal | None) -> tuple[str | None, Decimal | None]:
    """(tipo, valor) prontos para gravar. Os dois vazios = sem desconto."""
    vazio_valor = valor is None or (isinstance(valor, str) and not valor.strip())
    tipo = (tipo or "").strip().lower() or None
    if tipo is None and vazio_valor:
        return None, None
    if tipo is None:
        raise RegraViolada("Escolha o tipo do desconto (percentual ou valor) ou apague o valor.")
    if tipo not in TIPOS_DESCONTO:
        raise RegraViolada("Tipo de desconto inválido. Use percentual ou valor.")
    if vazio_valor:
        raise RegraViolada("Informe o valor do desconto ou tire o tipo do desconto.")
    d = _decimal(valor, "o desconto").quantize(_CENTAVO)
    if d < 0:
        raise RegraViolada("O desconto não pode ser negativo.")
    if tipo == "percentual" and d > _CEM:
        raise RegraViolada("Desconto percentual vai de 0 a 100%.")
    if tipo == "valor" and preco_referencia is not None and d > Decimal(preco_referencia):
        raise RegraViolada("O desconto não pode passar do preço de referência.")
    return tipo, d


@dataclass(frozen=True)
class Recorrencia:
    frequencia: str | None
    intervalo: int | None
    dias_semana: list[str]


def validar_dias_semana(dias: list[Any] | None) -> list[str]:
    limpos = []
    for d in dias or []:
        s = str(d or "").strip().lower()[:3].replace("sáb", "sab")
        if not s:
            continue
        if s not in DIAS_SEMANA:
            raise RegraViolada(f"Dia da semana inválido: {d}. Use seg, ter, qua, qui, sex, sab ou dom.")
        limpos.append(s)
    return [d for d in DIAS_SEMANA if d in limpos]


def validar_recorrencia(recorrente: bool, frequencia: str | None, intervalo: Any,
                        dias_semana: list[Any] | None) -> Recorrencia:
    """Estado final da recorrência. Recorrente sem frequência assume mensal a cada 1 mês."""
    if not recorrente:
        return Recorrencia(None, None, [])
    freq = (frequencia or "").strip().lower() or FREQUENCIA_PADRAO
    if freq not in FREQUENCIAS:
        raise RegraViolada("Frequência inválida. Use diária, semanal, mensal, semestral ou anual.")
    if intervalo is None or (isinstance(intervalo, str) and not intervalo.strip()):
        n = 1
    else:
        try:
            n = int(str(intervalo).strip())
        except ValueError:
            raise RegraViolada("O intervalo da recorrência precisa ser um número inteiro (a cada N).") from None
        if isinstance(intervalo, bool) or n < 1:
            raise RegraViolada("O intervalo da recorrência precisa ser 1 ou mais.")
        if n > 999:
            raise RegraViolada("O intervalo da recorrência vai até 999.")
    if freq == "semestral":
        n = 1
    dias = validar_dias_semana(dias_semana) if freq == "semanal" else []
    if freq == "semanal" and not dias:
        raise RegraViolada("Na recorrência semanal, escolha ao menos um dia da semana.")
    return Recorrencia(freq, n, dias)


_UNIDADE = {"diaria": ("dia", "dias", "Todo dia"), "semanal": ("semana", "semanas", "Toda semana"),
            "mensal": ("mês", "meses", "Todo mês"), "anual": ("ano", "anos", "Todo ano")}


def descrever_recorrencia(recorrente: bool, frequencia: str | None, intervalo: int | None,
                          dias_semana: list[str] | None) -> str | None:
    """"Todo dia", "A cada 2 dias", "Toda semana: seg, qua", "A cada 2 meses", "Semestral", "A cada 3 anos"…
    None quando não é recorrente; "Recorrente" para dado antigo sem frequência."""
    if not recorrente:
        return None
    if not frequencia:
        return "Recorrente"
    if frequencia == "semestral":
        return "Semestral"
    _, varios, todo =_UNIDADE.get(frequencia, ("período", "períodos", "Recorrente"))
    n = intervalo or 1
    texto = todo if n == 1 else f"A cada {n} {varios}"
    if frequencia == "semanal" and dias_semana:
        texto += ": " + ", ".join(d for d in DIAS_SEMANA if d in dias_semana)
    return texto
