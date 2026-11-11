"""Classificação dos modelos de comunicação (contrato Núcleo parte 2, §6). Função pura.

`classificacao` comercial | financeiro | geral. Cada área enxerga a sua classificação + "geral"; as automações (e a
Governança de ajustes) enxergam todas.
"""

from app.domain import RegraViolada

CLASSIFICACOES = ("comercial", "financeiro", "geral")
CONTEXTOS = {"comercial": ("comercial", "geral"), "financeiro": ("financeiro", "geral"),
             "automacoes": CLASSIFICACOES, "todos": CLASSIFICACOES}


def classificacoes_do_filtro(classificacao: list[str] | str | None = None, contexto: str | None = None) -> tuple[str, ...]:
    """Classificações a listar. `contexto` (comercial|financeiro|automacoes|todos) tem precedência; `classificacao`
    aceita lista ou texto separado por vírgula ("comercial,geral"). Nada informado = todas."""
    if contexto:
        if contexto not in CONTEXTOS:
            raise RegraViolada("Contexto inválido. Use comercial, financeiro, automacoes ou todos.")
        return CONTEXTOS[contexto]
    if not classificacao:
        return CLASSIFICACOES
    itens = classificacao.split(",") if isinstance(classificacao, str) else [
        p for c in classificacao for p in str(c).split(",")]
    limpos = [i.strip().lower() for i in itens if i and i.strip()]
    invalidas = [i for i in limpos if i not in CLASSIFICACOES]
    if invalidas:
        raise RegraViolada(f"Classificação inválida: {invalidas[0]}. Use comercial, financeiro ou geral.")
    return tuple(c for c in CLASSIFICACOES if c in limpos) or CLASSIFICACOES
