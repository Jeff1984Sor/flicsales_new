"""Regras puras do Núcleo (sem banco, sem FastAPI): campos personalizados, slug e detecção de duplicidade.

Ficam aqui (e não em `app/domain/`) porque o agente do Núcleo só edita `app/modules/nucleo/`. Mesmo contrato do domínio:
violação → `RegraViolada("mensagem PT-BR")` → HTTP 400.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any

from app.domain import RegraViolada
from app.domain.cadastro import chave_de_nome

# "lista" = seleção única; "multipla" = seleção múltipla (valor = lista de opções); "link" = hiperlink http(s).
# "sim_nao" continua aceito (campos antigos), mas a tela não o oferece mais.
TIPOS_CAMPO = ("texto", "numero", "moeda", "data", "sim_nao", "lista", "multipla", "link")
TIPOS_COM_OPCOES = ("lista", "multipla")
OBJETOS_CAMPO = ("empresa", "pessoa", "oportunidade")
ROTULO_TIPO = {"texto": "Texto", "numero": "Número", "moeda": "Moeda", "data": "Data", "sim_nao": "Sim/não",
               "lista": "Seleção única", "multipla": "Seleção múltipla", "link": "Hiperlink"}
SEPARADOR_MULTIPLA = ";"  # planilha e texto: "Opção A; Opção B"
_RX_LINK = re.compile(r"^https?://[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*(:\d+)?(/[^\s]*)?$", re.I)


# ------------------------------------------------------------------------------------------------- campos custom
def slug_de(nome: str) -> str:
    """"Origem do lead" → "origem_do_lead" (minúsculo, sem acento, só [a-z0-9_])."""
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:60] or "campo"


def validar_definicao_campo(*, nome: str | None, tipo: str, objeto: str, opcoes: list[str] | None) -> list[str]:
    """Confere a definição de um campo e devolve as opções limpas (sem vazias nem repetidas)."""
    if not (nome or "").strip():
        raise RegraViolada("Informe o nome do campo.")
    if tipo not in TIPOS_CAMPO:
        raise RegraViolada("Tipo de campo inválido. Use texto, data, número, moeda, seleção única, seleção múltipla "
                           "ou hiperlink.")
    if objeto not in OBJETOS_CAMPO:
        raise RegraViolada("Objeto inválido. Use empresa, pessoa ou oportunidade.")
    limpas: list[str] = []
    for o in opcoes or []:
        o = (o or "").strip()
        if o and o not in limpas:
            limpas.append(o)
    if tipo == "lista" and len(limpas) < 1:
        raise RegraViolada("Campo de seleção única precisa de ao menos uma opção.")
    if tipo == "multipla" and len(limpas) < 1:
        raise RegraViolada("Campo de seleção múltipla precisa de ao menos uma opção.")
    if tipo == "multipla" and any(SEPARADOR_MULTIPLA in o for o in limpas):
        raise RegraViolada("Opção de seleção múltipla não pode ter “;” (é o separador na planilha).")
    return limpas if tipo in TIPOS_COM_OPCOES else []


@dataclass(frozen=True)
class DefCampo:
    """O que a validação precisa saber de um `campo_custom`."""

    slug: str
    nome: str
    tipo: str
    opcoes: tuple[str, ...] = ()
    obrigatorio: bool = False
    arquivado: bool = False


def _vazio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list | tuple) and not v)


def normalizar_link(valor: Any, *, nome: str = "Link") -> str:
    """URL http(s). Sem protocolo, assume https:// ("www.aurora.com.br" → "https://www.aurora.com.br")."""
    if not isinstance(valor, str):
        raise RegraViolada(f"{nome}: informe um endereço começando com http:// ou https://.")
    s = valor.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I) and not re.match(r"^[a-z]+:", s, re.I):
        s = "https://" + s
    if len(s) > 500 or not _RX_LINK.match(s):
        raise RegraViolada(f"{nome}: informe um endereço começando com http:// ou https://.")
    return s


def normalizar_multipla(campo: "DefCampo", valor: Any) -> list[str]:
    """Lista de opções válidas (também aceita texto "A; B"), sem repetição, na ordem das opções do campo."""
    if isinstance(valor, str):
        itens = [x.strip() for x in valor.split(SEPARADOR_MULTIPLA)]
    elif isinstance(valor, list | tuple):
        itens = [x.strip() if isinstance(x, str) else x for x in valor]
    else:
        raise RegraViolada(f"{campo.nome}: escolha uma ou mais opções ({', '.join(campo.opcoes)}).")
    itens = [x for x in itens if not _vazio(x)]
    invalidas = [str(x) for x in itens if x not in campo.opcoes]
    if invalidas:
        raise RegraViolada(f"{campo.nome}: “{invalidas[0]}” não é uma das opções ({', '.join(campo.opcoes)}).")
    return [o for o in campo.opcoes if o in itens]


def normalizar_valor(campo: DefCampo, valor: Any) -> Any:
    """Converte e valida um valor para o tipo do campo. Vazio → None. Moeda vira string decimal ("1234.50");
    seleção múltipla vira lista de opções; link vira URL http(s)."""
    if _vazio(valor):
        return None
    nome = campo.nome
    if campo.tipo == "texto":
        if not isinstance(valor, str | int | float) or isinstance(valor, bool):
            raise RegraViolada(f"{nome}: informe um texto.")
        return str(valor).strip()
    if campo.tipo in ("numero", "moeda"):
        if isinstance(valor, bool):
            raise RegraViolada(f"{nome}: informe um número.")
        try:
            d = Decimal(str(valor).strip().replace(",", "."))
        except InvalidOperation:
            raise RegraViolada(f"{nome}: informe um número.") from None
        if not d.is_finite():
            raise RegraViolada(f"{nome}: informe um número.")
        if campo.tipo == "moeda":
            return str(d.quantize(Decimal("0.01")))
        return int(d) if d == d.to_integral_value() else float(d)
    if campo.tipo == "data":
        try:
            return date.fromisoformat(str(valor)[:10]).isoformat()
        except ValueError:
            raise RegraViolada(f"{nome}: informe a data no formato AAAA-MM-DD.") from None
    if campo.tipo == "sim_nao":
        if isinstance(valor, bool):
            return valor
        texto = str(valor).strip().lower()
        if texto in ("sim", "true", "1"):
            return True
        if texto in ("nao", "não", "false", "0"):
            return False
        raise RegraViolada(f"{nome}: responda sim ou não.")
    if campo.tipo == "lista":
        texto = str(valor).strip()
        if texto not in campo.opcoes:
            raise RegraViolada(f"{nome}: escolha uma das opções ({', '.join(campo.opcoes)}).")
        return texto
    if campo.tipo == "multipla":
        return normalizar_multipla(campo, valor) or None
    if campo.tipo == "link":
        return normalizar_link(valor, nome=nome)
    raise RegraViolada(f"{nome}: tipo de campo desconhecido.")  # pragma: no cover


def validar_campos_custom(definicoes: list[DefCampo], enviados: dict[str, Any] | None,
                          atuais: dict[str, Any] | None = None, *, exigir_obrigatorios: bool = True) -> dict[str, Any]:
    """Junta `enviados` sobre `atuais` (None apaga a chave) validando cada valor enviado.

    - chave enviada que não é campo do objeto (ou está arquivada) → "Campo personalizado desconhecido: x."
    - valores atuais de campos arquivados são preservados sem validar (o arquivamento não apaga dado).
    - `exigir_obrigatorios`: todo campo obrigatório ativo precisa estar preenchido no resultado.
    """
    por_slug = {d.slug: d for d in definicoes}
    resultado = dict(atuais or {})
    for chave, valor in (enviados or {}).items():
        d = por_slug.get(chave)
        if d is None or d.arquivado:
            if chave in resultado and resultado[chave] == valor:
                continue  # o formulário reenviou um valor já gravado de campo arquivado: preserva sem validar
            raise RegraViolada(f"Campo personalizado desconhecido: {chave}.")
        v = normalizar_valor(d, valor)
        if v is None:
            resultado.pop(chave, None)
        else:
            resultado[chave] = v
    if exigir_obrigatorios:
        faltando = [d.nome for d in definicoes if d.obrigatorio and not d.arquivado and _vazio(resultado.get(d.slug))]
        if faltando:
            raise RegraViolada(f"Preencha o campo obrigatório: {', '.join(faltando)}.")
    return resultado


# ------------------------------------------------------------------------------------------------- duplicidades
_SUFIXOS = re.compile(r"\b(ltda|me|epp|eireli|s a|sa|cia|companhia|mei|limitada)\b")


def nome_comparavel(nome: str) -> str:
    """Chave para comparar empresas: sem acento, sem pontuação e sem sufixos societários (Ltda, ME, S/A, EIRELI…)."""
    s = chave_de_nome(nome).replace("&", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = _SUFIXOS.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def so_digitos(doc: str | None) -> str:
    return re.sub(r"\D", "", doc or "")


@dataclass(frozen=True)
class EmpresaComparavel:
    id: int
    nome: str
    documento: str | None = None


@dataclass(frozen=True)
class ParDuplicado:
    a: int
    b: int
    motivo: str
    semelhanca: float


def encontrar_duplicidades(empresas: list[EmpresaComparavel], *, limiar: float = 0.88) -> list[ParDuplicado]:
    """Pares (a < b) de empresas prováveis duplicadas: mesmo documento, mesmo nome comparável ou nomes muito
    parecidos (razão de semelhança ≥ `limiar`). Ordena dos mais certos para os menos certos."""
    pares: dict[tuple[int, int], ParDuplicado] = {}
    lista = sorted(empresas, key=lambda e: e.id)
    chaves = {e.id: nome_comparavel(e.nome) for e in lista}
    docs = {e.id: so_digitos(e.documento) for e in lista}
    for i, a in enumerate(lista):
        for b in lista[i + 1:]:
            par = (a.id, b.id)
            da, db_ = docs[a.id], docs[b.id]
            if len(da) >= 11 and da == db_:
                pares[par] = ParDuplicado(a.id, b.id, "Mesmo documento (CPF/CNPJ)", 1.0)
                continue
            ka, kb = chaves[a.id], chaves[b.id]
            if not ka or not kb:
                continue
            if ka == kb:
                pares[par] = ParDuplicado(a.id, b.id, "Mesmo nome sem sufixos e pontuação", 1.0)
                continue
            if len(da) >= 8 and len(db_) >= 8 and da[:8] == db_[:8]:
                pares[par] = ParDuplicado(a.id, b.id, "Mesma raiz de CNPJ", 0.95)
                continue
            r = SequenceMatcher(None, ka, kb).ratio()
            if r >= limiar:
                pares[par] = ParDuplicado(a.id, b.id, "Nomes muito parecidos", round(r, 2))
    return sorted(pares.values(), key=lambda p: (-p.semelhanca, p.a, p.b))


def valor_corresponde(valor: Any, alvo: str | None) -> bool:
    """Filtro "campo = valor" sobre um valor gravado em `campos_custom` (sem diferenciar maiúsculas). Seleção múltipla
    (lista) corresponde quando a opção está entre as marcadas. Use nos filtros por campo personalizado."""
    a = (alvo or "").strip().lower()
    if isinstance(valor, list | tuple):
        return any(str(v).strip().lower() == a for v in valor)
    return str(valor if valor is not None else "").strip().lower() == a
