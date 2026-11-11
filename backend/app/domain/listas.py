"""Listas da Governança de ajustes (contrato Núcleo parte 2, §6): segmentos e portes da empresa e motivos de perda da
oportunidade. Funções puras. Nada se exclui: opção usada é inativada. `empresa.segmento`, `empresa.porte` e
`oportunidade.motivo_perda` continuam texto (a lista só alimenta os selects).
"""

import re

from app.domain import RegraViolada
from app.domain.cadastro import chave_de_nome

TIPOS = ("segmento", "porte", "motivo_perda")
ROTULO = {"segmento": "segmento", "porte": "porte", "motivo_perda": "motivo de perda"}
LIMITE_NOME = {"segmento": 100, "porte": 30, "motivo_perda": 120}

# valores iniciais (a migração 0006 também traz os valores já usados nos dados)
PADROES: dict[str, tuple[str, ...]] = {
    "porte": ("ME", "EPP", "Médio", "Grande"),
    "segmento": ("Consultoria", "Serviços", "Gestão", "Tecnologia", "Indústria", "Varejo", "Saúde", "Educação"),
    "motivo_perda": ("Preço", "Concorrente", "Sem orçamento", "Sem resposta", "Fora do momento", "Escopo não atende"),
}


def validar_tipo(tipo: str) -> str:
    if tipo not in TIPOS:
        raise RegraViolada("Lista inválida. Use segmento, porte ou motivo_perda.")
    return tipo


def validar_nome_opcao(tipo: str, nome: str | None, nomes_existentes: list[str]) -> str:
    """Nome limpo e sem repetição na lista (sem diferenciar maiúsculas nem acento). `nomes_existentes` = os OUTROS."""
    validar_tipo(tipo)
    limpo = re.sub(r"\s+", " ", nome or "").strip()
    if not limpo:
        raise RegraViolada(f"Informe o nome do {ROTULO[tipo]}.")
    if len(limpo) > LIMITE_NOME[tipo]:
        raise RegraViolada(f"Nome do {ROTULO[tipo]} com até {LIMITE_NOME[tipo]} caracteres.")
    chave = chave_de_nome(limpo)
    if any(chave_de_nome(n) == chave for n in nomes_existentes):
        raise RegraViolada(f"Já existe {ROTULO[tipo]} “{limpo}” nesta lista (veja também os inativos).")
    return limpo


def validar_reordenacao(ids_atuais: list[int], ids_enviados: list[int]) -> list[int]:
    """A nova ordem precisa ter exatamente os mesmos itens da lista (sem faltar, sobrar ou repetir)."""
    if len(set(ids_enviados)) != len(ids_enviados):
        raise RegraViolada("A nova ordem tem itens repetidos. Atualize a tela e tente de novo.")
    if set(ids_enviados) != set(ids_atuais):
        raise RegraViolada("A nova ordem não bate com a lista atual. Atualize a tela e tente de novo.")
    return ids_enviados


def iniciais(tipo: str, usados: list[str | None]) -> list[str]:
    """Opções para semear: padrões + valores já usados nos dados (limpos, sem repetição, dentro do limite)."""
    validar_tipo(tipo)
    out: list[str] = []
    chaves: set[str] = set()
    for v in (*PADROES[tipo], *sorted({u for u in usados if u}, key=chave_de_nome)):
        limpo = re.sub(r"\s+", " ", v or "").strip()
        if not limpo or len(limpo) > LIMITE_NOME[tipo] or chave_de_nome(limpo) in chaves:
            continue
        chaves.add(chave_de_nome(limpo))
        out.append(limpo)
    return out
