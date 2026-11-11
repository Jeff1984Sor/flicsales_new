"""Vários telefones e vários e-mails da pessoa (contrato Núcleo parte 2, §2). Funções puras.

Formato gravado:
  `pessoa.telefones` = [{"numero": "(11) 98888-7777", "tipo": "celular|whatsapp|fixo|comercial", "principal": bool}]
  `pessoa.emails`    = [{"email": "paula@aurora.com.br", "tipo": "comercial|pessoal|financeiro", "principal": bool}]

Regras: exatamente UM principal quando a lista não é vazia (nenhum marcado → o primeiro vira principal; mais de um →
RegraViolada). E-mail validado (minúsculo) e sem repetição; telefone normalizado ("(11) 98888-7777") e sem repetição.
Linha sem número/e-mail (linha em branco do formulário) é ignorada.

`pessoa.email` / `pessoa.telefone` continuam existindo e ESPELHAM o principal (`principal_de`). Cliente antigo que só
manda `email`/`telefone` troca o principal (`aplicar_principal`), sem apagar os outros.
"""

import re
from typing import Any

from app.domain import RegraViolada

TIPOS_TELEFONE = ("celular", "whatsapp", "fixo", "comercial")
TIPOS_EMAIL = ("comercial", "pessoal", "financeiro")
ROTULO_TIPO_TELEFONE = {"celular": "Celular", "whatsapp": "WhatsApp", "fixo": "Fixo", "comercial": "Comercial"}
ROTULO_TIPO_EMAIL = {"comercial": "Comercial", "pessoal": "Pessoal", "financeiro": "Financeiro"}
_RX_EMAIL = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")


def normalizar_telefone(numero: Any) -> str:
    """"11988887777" / "+55 (11) 98888-7777" → "(11) 98888-7777"; fixo com 10 dígitos → "(11) 3333-4444".
    Outros tamanhos (ramal, internacional) ficam como vieram, só sem espaços sobrando. Sem dígito → RegraViolada."""
    texto = re.sub(r"\s+", " ", str(numero or "")).strip()
    d = re.sub(r"\D", "", texto)
    if not d:
        raise RegraViolada(f"Telefone inválido: “{texto}”. Informe só números, com DDD.")
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    if len(d) < 8 or len(d) > 15:
        raise RegraViolada(f"Telefone inválido: “{texto}”. Informe o número com DDD.")
    return texto[:30]


def normalizar_email(email: Any) -> str:
    s = str(email or "").strip().lower()
    if not _RX_EMAIL.match(s) or len(s) > 200:
        raise RegraViolada(f"E-mail inválido: “{str(email or '').strip()}”.")
    return s


def _item(v: Any, chave: str) -> dict:
    if isinstance(v, str):  # aceita só o texto ("paula@x.com"): tipo padrão, não principal
        return {chave: v}
    if not isinstance(v, dict):
        raise RegraViolada("Lista de contatos em formato inválido.")
    return v


def _um_principal(itens: list[dict], o_que: str) -> list[dict]:
    marcados = [i for i in itens if i["principal"]]
    if len(marcados) > 1:
        raise RegraViolada(f"Marque só um {o_que} como principal.")
    if itens and not marcados:
        itens[0]["principal"] = True
    # o principal vai para o topo (é o que aparece nas listas e na busca)
    return sorted(itens, key=lambda i: not i["principal"])


def validar_telefones(lista: list[Any] | None) -> list[dict]:
    itens: list[dict] = []
    vistos: set[str] = set()
    for bruto in lista or []:
        v = _item(bruto, "numero")
        if not str(v.get("numero") or "").strip():
            continue
        numero = normalizar_telefone(v.get("numero"))
        tipo = (v.get("tipo") or "celular").strip().lower() if isinstance(v.get("tipo") or "celular", str) else ""
        if tipo not in TIPOS_TELEFONE:
            raise RegraViolada(f"Tipo de telefone inválido: {v.get('tipo')}. Use celular, WhatsApp, fixo ou comercial.")
        chave = re.sub(r"\D", "", numero)
        if chave in vistos:
            raise RegraViolada(f"Telefone repetido: {numero}.")
        vistos.add(chave)
        itens.append({"numero": numero, "tipo": tipo, "principal": bool(v.get("principal"))})
    return _um_principal(itens, "telefone")


def validar_emails(lista: list[Any] | None) -> list[dict]:
    itens: list[dict] = []
    vistos: set[str] = set()
    for bruto in lista or []:
        v = _item(bruto, "email")
        if not str(v.get("email") or "").strip():
            continue
        email = normalizar_email(v.get("email"))
        tipo = (v.get("tipo") or "comercial").strip().lower() if isinstance(v.get("tipo") or "comercial", str) else ""
        if tipo not in TIPOS_EMAIL:
            raise RegraViolada(f"Tipo de e-mail inválido: {v.get('tipo')}. Use comercial, pessoal ou financeiro.")
        if email in vistos:
            raise RegraViolada(f"E-mail repetido: {email}.")
        vistos.add(email)
        itens.append({"email": email, "tipo": tipo, "principal": bool(v.get("principal"))})
    return _um_principal(itens, "e-mail")


def principal_de(lista: list[dict] | None, chave: str) -> str | None:
    """Valor do item principal (ou do primeiro, em dado antigo sem marca); None se a lista é vazia."""
    itens = [i for i in (lista or []) if isinstance(i, dict) and i.get(chave)]
    if not itens:
        return None
    return next((i[chave] for i in itens if i.get("principal")), itens[0][chave])


def aplicar_principal(lista: list[dict] | None, valor: str | None, chave: str, *, tipo_padrao: str) -> list[dict]:
    """Cliente antigo mandou só `email`/`telefone`: o valor vira o principal (sem apagar os outros).

    - valor vazio → o principal sai da lista e o próximo vira principal;
    - valor que já está na lista → passa a ser o principal;
    - valor novo → substitui o valor do principal atual (ou entra como principal numa lista vazia).
    Não valida (quem chama já validou o valor, ou é dado antigo): nunca levanta erro."""
    itens = [dict(i) for i in (lista or []) if isinstance(i, dict) and i.get(chave)]
    idx = next((n for n, i in enumerate(itens) if i.get("principal")), 0 if itens else None)
    valor = (valor or "").strip() or None

    def mesma(a: str, b: str) -> bool:
        if chave == "numero":
            return re.sub(r"\D", "", a) == re.sub(r"\D", "", b) and bool(re.sub(r"\D", "", a))
        return a.strip().lower() == b.strip().lower()

    if valor is None:
        if idx is not None:
            itens.pop(idx)
    else:
        ja = next((n for n, i in enumerate(itens) if mesma(i[chave], valor)), None)
        if ja is not None:
            idx = ja
        elif idx is not None:
            itens[idx] = {**itens[idx], chave: valor}
        else:
            itens.append({chave: valor, "tipo": tipo_padrao, "principal": True})
            idx = len(itens) - 1
    for n, i in enumerate(itens):
        i["principal"] = valor is not None and n == idx
        i.setdefault("tipo", tipo_padrao)
    if itens and not any(i["principal"] for i in itens):
        itens[0]["principal"] = True
    return sorted(itens, key=lambda i: not i["principal"])


def juntar_adicionais(lista: list[dict] | None, adicionais: list[str], chave: str, *, tipo_padrao: str,
                      normalizar) -> list[dict]:
    """Planilha: mantém o principal e troca os demais pelos `adicionais` (texto já separado). Repetidos são ignorados."""
    principal = [dict(i) for i in (lista or []) if isinstance(i, dict) and i.get("principal") and i.get(chave)]
    itens = principal[:1]
    for bruto in adicionais:
        if not str(bruto or "").strip():
            continue
        v = normalizar(bruto)
        if chave == "numero":
            repetido = any(re.sub(r"\D", "", i[chave]) == re.sub(r"\D", "", v) for i in itens)
        else:
            repetido = any(i[chave].lower() == v.lower() for i in itens)
        if not repetido:
            itens.append({chave: v, "tipo": tipo_padrao, "principal": False})
    if itens and not any(i["principal"] for i in itens):
        itens[0]["principal"] = True
    return itens
