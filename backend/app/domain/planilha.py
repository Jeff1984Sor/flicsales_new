"""Leitura de células de planilha de migração (.xlsx ou .csv) — funções puras.

Cada função recebe o valor cru da célula (texto do CSV ou o tipo que o Excel guardou: int, float, datetime) e devolve o
valor do cadastro, `None` para célula vazia, ou levanta `RegraViolada` com a mensagem que vai para a lista de erros da
importação (linha/coluna ficam por conta de quem chama).
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain import RegraViolada
from app.domain.cadastro import chave_de_nome

MARCA_EXEMPLO = "EXEMPLO"
SIM = {"sim", "s", "yes", "y", "true", "verdadeiro", "1", "x"}
NAO = {"nao", "n", "no", "false", "falso", "0"}


def vazia(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def chave_cabecalho(cabecalho: Any) -> str:
    """"Nome *" / " NOME" / "Nome*" → "nome" (sem acento, sem asterisco de obrigatória)."""
    return chave_de_nome(str(cabecalho or "").replace("*", " "))


def linha_de_exemplo(primeira_celula: Any) -> bool:
    """A linha de exemplo do modelo começa com "EXEMPLO" na 1ª coluna e é ignorada na importação."""
    return isinstance(primeira_celula, str) and primeira_celula.strip().upper().startswith(MARCA_EXEMPLO)


def texto(valor: Any, *, max_len: int | None = None) -> str | None:
    """Texto limpo. Número inteiro guardado pelo Excel (1.1999e10) volta a texto sem ",0"."""
    if vazia(valor):
        return None
    if isinstance(valor, bool):
        valor = "Sim" if valor else "Não"
    elif isinstance(valor, float) and valor.is_integer():
        valor = str(int(valor))
    elif isinstance(valor, datetime | date):
        valor = valor.strftime("%d/%m/%Y")
    s = re.sub(r"\s+", " ", str(valor)).strip()
    if max_len is not None and len(s) > max_len:
        raise RegraViolada(f"Texto maior que {max_len} caracteres.")
    return s or None


def digitos(valor: Any, *, tamanhos: tuple[int, ...] = ()) -> str | None:
    """Só os dígitos. Se o Excel guardou como número (perdendo zeros à esquerda), completa com zeros até o menor
    tamanho esperado que caiba (ex.: CEP 1310100 → 01310100)."""
    if vazia(valor):
        return None
    numero = isinstance(valor, int | float) and not isinstance(valor, bool)
    d = re.sub(r"\D", "", str(int(valor)) if numero else str(valor))
    if numero and tamanhos:
        for t in sorted(tamanhos):
            if len(d) <= t:
                return d.zfill(t)
    return d


def decimal(valor: Any, *, minimo: Decimal | None = None) -> Decimal | None:
    """"1.234,56", "1234,56", "1234.56", "R$ 1.234,56" ou número do Excel → Decimal com 2 casas."""
    if vazia(valor):
        return None
    if isinstance(valor, bool):
        raise RegraViolada("Informe um número (ex.: 1.234,56).")
    if isinstance(valor, int | float | Decimal):
        d = Decimal(str(valor))
    else:
        s = re.sub(r"[R$\s]", "", str(valor))
        negativo = s.startswith("-")
        s = s.lstrip("-+")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".") if s.count(",") == 1 else ""
        elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", s):
            s = s.replace(".", "")  # 1.500 / 1.234.567 = separador de milhar (padrão BR)
        if not re.fullmatch(r"\d+(\.\d+)?", s):
            raise RegraViolada("Informe um número (ex.: 1.234,56).")
        d = Decimal(("-" if negativo else "") + s)
    try:
        d = d.quantize(Decimal("0.01"))
    except InvalidOperation:
        raise RegraViolada("Informe um número (ex.: 1.234,56).") from None
    if minimo is not None and d < minimo:
        raise RegraViolada(f"O valor não pode ser menor que {str(minimo).replace('.', ',')}.")
    return d


def data(valor: Any) -> date | None:
    """DD/MM/AAAA, AAAA-MM-DD ou data do Excel."""
    if vazia(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    for padrao, ordem in ((r"(\d{1,2})/(\d{1,2})/(\d{4})", "dma"), (r"(\d{4})-(\d{1,2})-(\d{1,2})", "amd")):
        m = re.fullmatch(padrao, s[:10] if ordem == "amd" else s)
        if m:
            a, b, c = (int(x) for x in m.groups())
            try:
                return date(c, b, a) if ordem == "dma" else date(a, b, c)
            except ValueError:
                break
    raise RegraViolada("Informe a data como DD/MM/AAAA.")


def sim_nao(valor: Any) -> bool | None:
    if vazia(valor):
        return None
    if isinstance(valor, bool):
        return valor
    s = chave_de_nome(texto(valor) or "")
    if s in SIM:
        return True
    if s in NAO:
        return False
    raise RegraViolada("Responda Sim ou Não.")


def opcao(valor: Any, opcoes: dict[str, str]) -> str | None:
    """`opcoes` = {rótulo exibido: valor gravado}. Aceita o rótulo ou o valor, sem acento e sem diferenciar
    maiúsculas ("ligação", "Ligacao", "ligacao" → "ligacao")."""
    if vazia(valor):
        return None
    alvo = chave_de_nome(texto(valor) or "")
    for rotulo, gravado in opcoes.items():
        if alvo in (chave_de_nome(rotulo), chave_de_nome(gravado)):
            return gravado
    raise RegraViolada(f"Use uma das opções: {', '.join(opcoes)}.")


def lista(valor: Any, opcoes: dict[str, str]) -> list[str] | None:
    """Várias opções na mesma célula, separadas por vírgula, ponto e vírgula ou barra."""
    if vazia(valor):
        return None
    itens = [x for x in re.split(r"[,;/|]", str(valor)) if x.strip()]
    out: list[str] = []
    for item in itens:
        v = opcao(item, opcoes)
        if v and v not in out:
            out.append(v)
    return out or None
