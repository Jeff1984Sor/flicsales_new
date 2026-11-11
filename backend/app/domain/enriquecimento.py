"""Enriquecimento de cadastros: lista branca de campos por objeto e normalização/validação de cada valor sugerido.

Funções puras (sem banco, sem relógio). A IA (ou a consulta de CNPJ/CEP) SUGERE; aqui se decide o que sobrevive:
- campo fora da lista branca do objeto → descartado;
- valor que não passa na validação do tipo (e-mail, CEP, UF, CNPJ/CPF, telefone, dinheiro > 0, opção de lista…) → descartado;
- valor igual ao atual → descartado (não é sugestão).

`normalizar(espec, valor)` devolve o valor pronto para o formulário (str, bool ou None se inválido).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ",
       "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO")

OBJETOS = ("empresa", "fornecedor", "pessoa", "produto", "categoria", "centro_custo", "conta")


@dataclass(frozen=True)
class Campo:
    """Campo editável que a IA pode sugerir. `tipo`: texto | texto_longo | email | telefone | cep | uf | documento |
    site | opcao | multipla | dinheiro | numero | moeda | data | sim_nao. `multipla` = lista de `opcoes`."""

    nome: str
    rotulo: str
    tipo: str = "texto"
    max_len: int = 200
    opcoes: tuple[str, ...] = field(default_factory=tuple)


ENDERECO = (
    Campo("cep", "CEP", "cep"),
    Campo("logradouro", "Logradouro", max_len=200),
    Campo("numero", "Número", max_len=20),
    Campo("complemento", "Complemento", max_len=100),
    Campo("bairro", "Bairro", max_len=100),
    Campo("cidade", "Cidade", max_len=100),
    Campo("uf", "UF", "uf"),
)

_EMPRESA = (
    Campo("nome", "Nome", max_len=200),
    Campo("nome_fantasia", "Nome fantasia", max_len=200),
    Campo("documento", "CNPJ/CPF", "documento"),
    Campo("segmento", "Segmento", max_len=100),
    Campo("porte", "Porte", max_len=30),
    Campo("site", "Site", "site", max_len=300),
    # "E-mail financeiro" saiu da tela (contrato Núcleo parte 2, §1): a coluna fica no banco, a IA não sugere mais
    Campo("telefone", "Telefone", "telefone"),
    Campo("origem", "Origem", max_len=100),
    Campo("observacoes", "Observações", "texto_longo", max_len=4000),
    *ENDERECO,
)

CAMPOS_FIXOS: dict[str, tuple[Campo, ...]] = {
    "empresa": _EMPRESA,
    "fornecedor": (*_EMPRESA, Campo("condicao_habitual", "Condição habitual", max_len=200)),
    "pessoa": (
        Campo("nome", "Nome", max_len=200),
        Campo("cargo", "Cargo / papel na compra", max_len=120),
        Campo("email", "E-mail", "email"),
        Campo("telefone", "Telefone", "telefone"),
        Campo("canal_preferido", "Canal preferido", "opcao", opcoes=("email", "ligacao", "whatsapp")),
        Campo("observacoes", "Observações", "texto_longo", max_len=4000),
        *ENDERECO,
    ),
    "produto": (
        Campo("nome", "Nome", max_len=200),
        Campo("tipo", "Tipo", "opcao", opcoes=("servico", "produto")),
        Campo("codigo", "Código", max_len=50),
        Campo("unidade", "Unidade", max_len=30),
        Campo("preco_referencia", "Preço de referência", "dinheiro"),
        Campo("recorrente", "Recorrente", "sim_nao"),
        # recorrência (contrato Núcleo parte 2, §3); desconto NÃO entra: a IA não sugere desconto
        Campo("frequencia", "Frequência", "opcao", opcoes=("diaria", "semanal", "mensal", "semestral", "anual")),
        Campo("intervalo", "Intervalo (a cada N)", "numero"),
        Campo("dias_semana", "Dias da semana", "multipla", opcoes=("seg", "ter", "qua", "qui", "sex", "sab", "dom")),
        Campo("descricao", "Descrição", "texto_longo", max_len=4000),
    ),
    "categoria": (
        Campo("nome", "Nome", max_len=120),
        Campo("natureza", "Natureza", "opcao", opcoes=("receita", "despesa")),
    ),
    "centro_custo": (
        Campo("nome", "Nome", max_len=120),
        Campo("codigo", "Código", max_len=20),
    ),
    # saldo inicial e data-base da conta são fatos do banco: a IA não sugere número de saldo
    "conta": (
        Campo("nome", "Nome", max_len=120),
        Campo("instituicao", "Instituição", max_len=120),
    ),
}

# objeto do enriquecimento → objeto dos campos personalizados (CampoCustom.objeto)
OBJETO_CUSTOM = {"empresa": "empresa", "fornecedor": "empresa", "pessoa": "pessoa", "produto": "produto"}
PREFIXO_CUSTOM = "campos_custom."
# tipo do campo personalizado → tipo do enriquecimento (seleção múltipla = lista de opções; hiperlink = site/url)
_TIPO_CUSTOM = {"texto": "texto", "numero": "numero", "moeda": "moeda", "data": "data", "sim_nao": "sim_nao",
                "lista": "opcao", "multipla": "multipla", "link": "site"}


def campo_custom(slug: str, nome: str, tipo: str, opcoes: list[str] | None = None) -> Campo:
    return Campo(PREFIXO_CUSTOM + slug, nome, _TIPO_CUSTOM.get(tipo, "texto"), max_len=500,
                 opcoes=tuple(opcoes or ()) if tipo in ("lista", "multipla") else ())


def lista_branca(objeto: str, customs: list[Campo] | None = None) -> dict[str, Campo]:
    if objeto not in CAMPOS_FIXOS:
        raise ValueError(f"Objeto sem enriquecimento: {objeto}")
    return {c.nome: c for c in (*CAMPOS_FIXOS[objeto], *(customs or []))}


# ------------------------------------------------------------------------------------------------ validadores
_RX_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_RX_SITE = re.compile(r"^https?://[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+(:\d+)?(/[^\s]*)?$")


def so_digitos(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def cnpj_valido(digitos: str) -> bool:
    if len(digitos) != 14 or len(set(digitos)) == 1 or not digitos.isdigit():
        return False

    def dv(base: str) -> str:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
        r = sum(int(a) * b for a, b in zip(base, pesos, strict=True)) % 11
        return "0" if r < 2 else str(11 - r)

    return digitos[12] == dv(digitos[:12]) and digitos[13] == dv(digitos[:13])


def cpf_valido(digitos: str) -> bool:
    if len(digitos) != 11 or len(set(digitos)) == 1 or not digitos.isdigit():
        return False
    for n in (9, 10):
        s = sum(int(digitos[i]) * (n + 1 - i) for i in range(n))
        if digitos[n] != str((s * 10) % 11 % 10):
            return False
    return True


def formatar_cnpj(d: str) -> str:
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()


def _decimal(v: Any) -> Decimal | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        texto = str(v)
    else:
        texto = re.sub(r"[R$\s]", "", str(v or ""))
        if "," in texto:  # formato brasileiro: 1.234,56
            texto = texto.replace(".", "").replace(",", ".")
    try:
        d = Decimal(texto)
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _texto(v: Any, max_len: int, *, multilinha: bool = False) -> str | None:
    if v is None or isinstance(v, (dict, list, bool)):
        return None
    s = str(v).strip()
    if not multilinha:
        s = re.sub(r"\s+", " ", s)
    if not s or len(s) > max_len:
        return None
    return s


def _itens_multipla(v: Any, opcoes: tuple[str, ...]) -> list[Any] | None:
    """Lista enviada, ou texto "A; B" / "A, B" / "['A', 'B']" quebrado nos itens. Vírgula só separa quando não há
    ";" e o texto inteiro não é uma das opções (opção pode ter vírgula). None se não der para ler."""
    if isinstance(v, (list, tuple)):
        return list(v)
    if not isinstance(v, str):
        return None
    s = v.strip().strip("[]")
    if _sem_acento(s) in {_sem_acento(o) for o in opcoes}:
        return [s]
    sep = r"[;|\n]" if re.search(r"[;|\n]", s) else r","
    return [x.strip().strip("'\"") for x in re.split(sep, s)]


def normalizar(c: Campo, v: Any) -> Any:
    """Valor normalizado, ou None se inválido (a sugestão é descartada)."""
    t = c.tipo
    if t == "multipla":  # todas as opções precisam existir no campo; sai na ordem das opções, sem repetição
        itens = _itens_multipla(v, c.opcoes)
        if itens is None:
            return None
        escolhidas = set()
        for item in itens:
            if item is None or (isinstance(item, str) and not item.strip()):
                continue
            if not isinstance(item, str):
                return None
            alvo = _sem_acento(item)
            o = next((o for o in c.opcoes if _sem_acento(o) == alvo), None)
            if o is None:
                return None
            escolhidas.add(o)
        return [o for o in c.opcoes if o in escolhidas] or None
    if t == "sim_nao":
        if isinstance(v, bool):
            return v
        s = _sem_acento(str(v or ""))
        return True if s in ("sim", "s", "true", "1", "yes") else False if s in ("nao", "n", "false", "0", "no") else None
    if t in ("dinheiro", "moeda", "numero"):
        d = _decimal(v)
        if d is None:
            return None
        if t == "dinheiro" and d <= 0:
            return None
        if t == "moeda" and d < 0:
            return None
        if t in ("dinheiro", "moeda"):
            d = d.quantize(Decimal("0.01"))
            return None if abs(d) >= Decimal("1e13") else str(d)
        return format(d.normalize(), "f")
    s = _texto(v, c.max_len, multilinha=(t == "texto_longo"))
    if s is None:
        return None
    if t in ("texto", "texto_longo"):
        return s
    if t == "email":
        s = s.lower()
        return s if _RX_EMAIL.match(s) else None
    if t == "telefone":
        d = so_digitos(s)
        if d.startswith("55") and len(d) in (12, 13):
            d = d[2:]
        if len(d) == 10:
            return f"({d[:2]}) {d[2:6]}-{d[6:]}"
        if len(d) == 11:
            return f"({d[:2]}) {d[2:7]}-{d[7:]}"
        return None
    if t == "cep":
        d = so_digitos(s)
        return f"{d[:5]}-{d[5:]}" if len(d) == 8 and re.fullmatch(r"[\d.\-\s]+", s) else None
    if t == "uf":
        u = s.upper()
        return u if u in UFS else None
    if t == "documento":
        d = so_digitos(s)
        if cnpj_valido(d):
            return formatar_cnpj(d)
        if cpf_valido(d):
            return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
        return None
    if t == "site":
        u = s if re.match(r"^https?://", s, re.I) else "https://" + s
        return u if _RX_SITE.match(u) and len(u) <= c.max_len else None
    if t == "opcao":
        alvo = _sem_acento(s)
        return next((o for o in c.opcoes if _sem_acento(o) == alvo), None)
    if t == "data":
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s) or None
        if m:
            a, mes, dia = (int(x) for x in m.groups())
        else:
            m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s)
            if not m:
                return None
            dia, mes, a = (int(x) for x in m.groups())
        try:
            return date(a, mes, dia).isoformat()
        except ValueError:
            return None
    return None


def igual(c: Campo, atual: Any, sugerido: Any) -> bool:
    """O sugerido já é o valor atual? Compara o valor como está no formulário (sem caixa/acentos/espaços nas pontas):
    "11222333000181" → "11.222.333/0001-81" CONTA como sugestão (padronizar formato é útil)."""
    if atual is None or atual == "" or atual == []:
        return False
    if c.tipo == "multipla":
        return normalizar(c, atual) == sugerido
    if isinstance(sugerido, bool) or isinstance(atual, bool):
        return normalizar(c, atual) == sugerido
    if c.tipo in ("dinheiro", "moeda", "numero"):
        return normalizar(c, atual) == sugerido
    return _sem_acento(re.sub(r"\s+", " ", str(atual))) == _sem_acento(str(sugerido))
