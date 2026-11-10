"""Consultas públicas de cadastro (CNPJ e CEP), sempre no servidor: o navegador nunca chama provedor externo.

Sem chave de API. Timeout de 8 s por provedor, fallback entre provedores e cache em memória por 24 h (só respostas
encontradas). Assinaturas estáveis — outros módulos (ex.: o "Enriquecer com IA" da orquestração) importam daqui:

- `consultar_cnpj(cnpj: str, db: Session | None = None) -> dict`
    {"documento", "nome", "nome_fantasia", "segmento", "porte" (ME|EPP|Demais|None), "situacao", "abertura"
     (AAAA-MM-DD), "telefone", "email_financeiro", "cep", "logradouro", "numero", "complemento", "bairro", "cidade",
     "uf", "fonte", "socios": [{"nome", "qualificacao", "documento", "data_entrada", "faixa_etaria"}],
     "cnae_principal" ("6201-5/01 · Descrição"), "cnaes_secundarios" [str], "natureza_juridica", "capital_social"
     ("10000.00" | None)} — com `db`, também "empresa_existente": {"id", "nome"} | None (mesmo CNPJ já cadastrado).
- `consultar_cep(cep: str) -> dict`  {"cep", "logradouro", "bairro", "cidade", "uf", "fonte"}

Erros: documento/CEP inválido → `RegraViolada` (400); não encontrado → `ConsultaNaoEncontrada` (LookupError, 404);
todos os provedores fora → `ConsultaIndisponivel` (502). As duas exceções herdam de `ErroConsulta` e trazem
`mensagem` pronta para o usuário.

Nos testes, troque o transporte HTTP: `consultas.TRANSPORTE = httpx.MockTransport(handler)` e `consultas.limpar_cache()`.
"""

import copy
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.domain.cadastro import formatar_cnpj, so_digitos, validar_cep, validar_cnpj

TIMEOUT_S = 8.0
CACHE_S = 24 * 3600
TRANSPORTE: httpx.BaseTransport | None = None  # None = rede de verdade; testes injetam httpx.MockTransport

_cache: dict[str, tuple[float, dict]] = {}


class ErroConsulta(Exception):
    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class ConsultaNaoEncontrada(ErroConsulta, LookupError):
    """O provedor respondeu que o CNPJ/CEP não existe (HTTP 404)."""


class ConsultaIndisponivel(ErroConsulta):
    """Nenhum provedor respondeu (fora do ar, lento, limite de uso) — HTTP 502."""


class _NaoAchou(Exception):
    pass


def limpar_cache() -> None:
    _cache.clear()


def _do_cache(chave: str) -> dict | None:
    item = _cache.get(chave)
    if item and item[0] > time.monotonic():
        return copy.deepcopy(item[1])
    _cache.pop(chave, None)
    return None


def _guardar(chave: str, dados: dict) -> None:
    _cache[chave] = (time.monotonic() + CACHE_S, copy.deepcopy(dados))


def _get_json(url: str) -> Any:
    """GET com timeout. 404 (ou 400 de "não existe") → _NaoAchou; outros problemas → httpx.HTTPError/ValueError."""
    with httpx.Client(timeout=TIMEOUT_S, transport=TRANSPORTE, follow_redirects=True,
                      headers={"Accept": "application/json", "User-Agent": "FlicSalesOS/1.0"}) as c:
        r = c.get(url)
    if r.status_code == 404:
        raise _NaoAchou
    r.raise_for_status()
    return r.json()


def _executar(provedores, *, nao_encontrado: str, indisponivel: str) -> dict:
    achou_nao = False
    for funcao in provedores:
        try:
            return funcao()
        except _NaoAchou:
            achou_nao = True
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            continue
    if achou_nao:
        raise ConsultaNaoEncontrada(nao_encontrado)
    raise ConsultaIndisponivel(indisponivel)


def _texto(v: Any) -> str | None:
    if v is None:
        return None
    s = " ".join(str(v).split())
    return s or None


def _titulo(v: Any) -> str | None:
    """"AVENIDA PAULISTA" → "Avenida Paulista" (preposições minúsculas)."""
    s = _texto(v)
    if not s:
        return None
    pequenas = {"de", "da", "do", "das", "dos", "e"}
    palavras = s.lower().split(" ")
    return " ".join(p if (i and p in pequenas) else p[:1].upper() + p[1:] for i, p in enumerate(palavras))


def _telefone(v: Any) -> str | None:
    d = so_digitos(v)
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    return _texto(v)


def _email(v: Any) -> str | None:
    s = _texto(v)
    return s.lower() if s and "@" in s else None


def _porte(v: Any) -> str | None:
    s = (_texto(v) or "").upper()
    if s in ("ME", "MICRO EMPRESA", "MICROEMPRESA", "01", "1"):
        return "ME"
    if s in ("EPP", "EMPRESA DE PEQUENO PORTE", "03", "3"):
        return "EPP"
    if s in ("DEMAIS", "05", "5"):
        return "Demais"
    return None


def _cep(v: Any) -> str | None:
    d = so_digitos(v)
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else None


def _uf(v: Any) -> str | None:
    s = (_texto(v) or "").upper()
    return s if len(s) == 2 else None


def _cnae(codigo: Any, descricao: Any) -> str | None:
    """6201501 + "Desenvolvimento…" → "6201-5/01 · Desenvolvimento…"."""
    d = so_digitos(codigo)
    desc = _texto(descricao)
    if not d:
        return desc
    d = d.zfill(7)
    cod = f"{d[:4]}-{d[4]}/{d[5:7]}"
    return f"{cod} · {desc}" if desc else cod


def _capital(v: Any) -> str | None:
    if v in (None, ""):
        return None
    try:
        return str(Decimal(str(v)).quantize(Decimal("0.01")))
    except InvalidOperation:
        return None


def _data_iso(v: Any) -> str | None:
    s = _texto(v)
    return s[:10] if s and len(s) >= 10 and s[4] == "-" else None


# ================================================================================================= CNPJ
def _cnpj_brasilapi(digitos: str) -> dict:
    j = _get_json(f"https://brasilapi.com.br/api/cnpj/v1/{digitos}")
    tipo = _texto(j.get("descricao_tipo_de_logradouro"))
    logradouro = " ".join(x for x in (tipo, _texto(j.get("logradouro"))) if x)
    return {
        "nome": _texto(j.get("razao_social")),
        "nome_fantasia": _texto(j.get("nome_fantasia")),
        "segmento": _texto(j.get("cnae_fiscal_descricao")),
        "porte": _porte(j.get("porte")) or _porte(j.get("codigo_porte")),
        "situacao": _texto(j.get("descricao_situacao_cadastral")),
        "abertura": _texto(j.get("data_inicio_atividade")),
        "telefone": _telefone(j.get("ddd_telefone_1")),
        "email_financeiro": _email(j.get("email")),
        "cep": _cep(j.get("cep")),
        "logradouro": _titulo(logradouro),
        "numero": _texto(j.get("numero")),
        "complemento": _texto(j.get("complemento")),
        "bairro": _titulo(j.get("bairro")),
        "cidade": _titulo(j.get("municipio")),
        "uf": _uf(j.get("uf")),
        "fonte": "BrasilAPI (Receita Federal)",
        "socios": [{"nome": _texto(q.get("nome_socio")) or "Sócio sem nome",
                    "qualificacao": _texto(q.get("qualificacao_socio")),
                    "documento": _texto(q.get("cnpj_cpf_do_socio")),
                    "data_entrada": _data_iso(q.get("data_entrada_sociedade")),
                    "faixa_etaria": _texto(q.get("faixa_etaria"))} for q in j.get("qsa") or []],
        "cnae_principal": _cnae(j.get("cnae_fiscal"), j.get("cnae_fiscal_descricao")),
        "cnaes_secundarios": [x for x in (_cnae(c.get("codigo"), c.get("descricao"))
                                          for c in j.get("cnaes_secundarios") or [] if c.get("codigo")) if x],
        "natureza_juridica": _texto(j.get("natureza_juridica")),
        "capital_social": _capital(j.get("capital_social")),
    }


def _cnpj_cnpja(digitos: str) -> dict:
    j = _get_json(f"https://open.cnpja.com/office/{digitos}")
    emp = j.get("company") or {}
    end = j.get("address") or {}
    fones = j.get("phones") or []
    emails = j.get("emails") or []
    atividade = j.get("mainActivity") or {}
    return {
        "nome": _texto(emp.get("name")),
        "nome_fantasia": _texto(j.get("alias")),
        "segmento": _texto(atividade.get("text")),
        "porte": _porte((emp.get("size") or {}).get("acronym")),
        "situacao": (_texto((j.get("status") or {}).get("text")) or "").upper() or None,
        "abertura": _texto(j.get("founded")),
        "telefone": _telefone(f"{fones[0].get('area', '')}{fones[0].get('number', '')}") if fones else None,
        "email_financeiro": _email(emails[0].get("address")) if emails else None,
        "cep": _cep(end.get("zip")),
        "logradouro": _titulo(end.get("street")),
        "numero": _texto(end.get("number")),
        "complemento": _texto(end.get("details")),
        "bairro": _titulo(end.get("district")),
        "cidade": _titulo(end.get("city")),
        "uf": _uf(end.get("state")),
        "fonte": "CNPJá (Receita Federal)",
        "socios": [{"nome": _texto((m.get("person") or {}).get("name")) or "Sócio sem nome",
                    "qualificacao": _texto((m.get("role") or {}).get("text")),
                    "documento": _texto((m.get("person") or {}).get("taxId")),
                    "data_entrada": _data_iso(m.get("since")),
                    "faixa_etaria": _texto((m.get("person") or {}).get("age"))} for m in emp.get("members") or []],
        "cnae_principal": _cnae(atividade.get("id"), atividade.get("text")),
        "cnaes_secundarios": [x for x in (_cnae(a.get("id"), a.get("text")) for a in j.get("sideActivities") or [])
                              if x],
        "natureza_juridica": _texto((emp.get("nature") or {}).get("text")),
        "capital_social": _capital(emp.get("equity")),
    }


def consultar_cnpj(cnpj: str, db: Session | None = None) -> dict:
    """Dados públicos do CNPJ. Ver o topo do módulo para o formato e os erros."""
    validar_cnpj(cnpj)
    digitos = so_digitos(cnpj)
    chave = f"cnpj:{digitos}"
    dados = _do_cache(chave)
    if dados is None:
        dados = _executar([lambda: _cnpj_brasilapi(digitos), lambda: _cnpj_cnpja(digitos)],
                          nao_encontrado="CNPJ não encontrado na Receita Federal. Confira os números.",
                          indisponivel="A consulta de CNPJ está fora do ar agora. Tente de novo em alguns minutos "
                                       "ou preencha os dados à mão.")
        dados["documento"] = formatar_cnpj(digitos)
        _guardar(chave, dados)
    if db is not None:
        dados["empresa_existente"] = empresa_com_documento(db, digitos)
    return dados


def empresa_com_documento(db: Session, documento: str) -> dict | None:
    """{"id", "nome"} da empresa já cadastrada com o mesmo CNPJ/CPF (comparando só os dígitos)."""
    from sqlalchemy import select

    from app.modules.nucleo.models import Empresa

    digitos = so_digitos(documento)
    if not digitos:
        return None
    for eid, nome, doc in db.execute(select(Empresa.id, Empresa.nome, Empresa.documento)
                                     .where(Empresa.documento.is_not(None)).order_by(Empresa.id)):
        if so_digitos(doc) == digitos:
            return {"id": eid, "nome": nome}
    return None


# ================================================================================================= CEP
def _cep_viacep(digitos: str) -> dict:
    j = _get_json(f"https://viacep.com.br/ws/{digitos}/json/")
    if j.get("erro") in (True, "true"):
        raise _NaoAchou
    return {"logradouro": _texto(j.get("logradouro")), "bairro": _texto(j.get("bairro")),
            "cidade": _texto(j.get("localidade")), "uf": _uf(j.get("uf")), "fonte": "ViaCEP"}


def _cep_brasilapi(digitos: str) -> dict:
    j = _get_json(f"https://brasilapi.com.br/api/cep/v2/{digitos}")
    return {"logradouro": _texto(j.get("street")), "bairro": _texto(j.get("neighborhood")),
            "cidade": _texto(j.get("city")), "uf": _uf(j.get("state")), "fonte": "BrasilAPI (Correios)"}


def consultar_cep(cep: str) -> dict:
    """Endereço do CEP: {"cep", "logradouro", "bairro", "cidade", "uf", "fonte"}."""
    formatado = validar_cep(cep)
    digitos = so_digitos(formatado)
    chave = f"cep:{digitos}"
    dados = _do_cache(chave)
    if dados is None:
        dados = _executar([lambda: _cep_viacep(digitos), lambda: _cep_brasilapi(digitos)],
                          nao_encontrado="CEP não encontrado. Confira os números ou preencha o endereço à mão.",
                          indisponivel="A consulta de CEP está fora do ar agora. Preencha o endereço à mão.")
        dados["cep"] = formatado
        _guardar(chave, dados)
    return dados
