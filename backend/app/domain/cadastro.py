"""Cadastro único compartilhado (empresa, pessoa, produto): nome obrigatório e sem duplicidade.

A empresa é UM cadastro para os três módulos; o nome basta para começar. "Aurora Consultoria", " aurora  consultoria"
e "Aurora Consultória" são a mesma empresa: a chave normalizada (`chave_de_nome`) é única no banco.
"""

import re
import unicodedata

from app.domain import RegraViolada

PAPEIS_EMPRESA = ("prospect", "cliente", "fornecedor", "parceiro")


def chave_de_nome(nome: str) -> str:
    """Minúsculas, sem acento, espaços colapsados. Usada na UNIQUE `empresa.nome_chave`."""
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def validar_nome(nome: str | None, *, o_que: str = "o nome") -> str:
    limpo = re.sub(r"\s+", " ", (nome or "")).strip()
    if not limpo:
        raise RegraViolada(f"Informe {o_que}.")
    return limpo


def validar_nome_unico(nome: str, chaves_existentes: set[str]) -> None:
    """`chaves_existentes` = chaves das OUTRAS empresas (exclua a própria ao renomear)."""
    if chave_de_nome(nome) in chaves_existentes:
        raise RegraViolada("Já existe empresa com este nome")


def validar_papeis(papeis: list[str]) -> list[str]:
    desconhecidos = [p for p in papeis if p not in PAPEIS_EMPRESA]
    if desconhecidos:
        raise RegraViolada(f"Papel de empresa desconhecido: {', '.join(desconhecidos)}.")
    return [p for p in PAPEIS_EMPRESA if p in papeis]
