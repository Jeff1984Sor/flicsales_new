"""Envio de e-mail por um usuário (contrato de envio 11/2026). Funções puras: validar a mensagem, bloquear opt-out e
montar os textos que ficam registrados (comunicação, histórico da cobrança).

O serviço que fala com o banco e com o SMTP é `app.core.envio.enviar_por_usuario`; todo envio feito POR um usuário
(e qualquer envio automático futuro) passa por ele e, portanto, por `destinatarios_bloqueados`.

WhatsApp (11/2026): `normalizar_whatsapp` (dígitos com DDI 55), `validar_mensagem_whatsapp`, opt-out por telefone
(`telefones_bloqueados`/`conferir_opt_out_telefones`/`filtrar_opt_out_telefones`) e os textos registrados. O serviço é
`app.core.envio.enviar_whatsapp_por_usuario`.
"""

import re
from dataclasses import dataclass
from datetime import date

from app.domain import RegraViolada
from app.domain.cadastro import OPT_OUT
from app.domain.contatos import normalizar_email
from app.domain.proposta import exige_aprovacao_desconto

MAX_DESTINATARIOS = 20
MAX_ASSUNTO = 200


def pode_receber_email(permissoes: list[str] | None) -> bool:
    """A pessoa aceita receber e-mail? Não, se pediu opt-out (vale para envio manual e automático)."""
    return OPT_OUT not in (permissoes or [])


@dataclass(frozen=True)
class Contato:
    """Pessoa cadastrada, com todos os e-mails dela (principal e adicionais) e as permissões de comunicação."""

    nome: str
    emails: tuple[str, ...]
    permissoes: tuple[str, ...] = ()
    telefones: tuple[str, ...] = ()  # como cadastrados; comparados já normalizados (normalizar_whatsapp)


@dataclass(frozen=True)
class Mensagem:
    para: list[str]
    cc: list[str]
    assunto: str
    corpo: str


def _lista(valores: list[str] | None) -> list[str]:
    saida: list[str] = []
    for v in valores or []:
        if not str(v or "").strip():
            continue
        e = normalizar_email(v)
        if e not in saida:
            saida.append(e)
    return saida


def validar_mensagem(*, para: list[str] | None, cc: list[str] | None, assunto: str | None,
                     corpo: str | None) -> Mensagem:
    """Para ≥ 1, e-mails válidos (minúsculos, sem repetir; quem está em "Para" sai do "Cc"), máx. 20 no total;
    assunto e corpo obrigatórios."""
    p = _lista(para)
    if not p:
        raise RegraViolada("Informe ao menos um destinatário em “Para”.")
    c = [e for e in _lista(cc) if e not in p]
    if len(p) + len(c) > MAX_DESTINATARIOS:
        raise RegraViolada(f"Envie para no máximo {MAX_DESTINATARIOS} destinatários por vez.")
    a = " ".join(str(assunto or "").split())
    if not a:
        raise RegraViolada("Informe o assunto do e-mail.")
    if len(a) > MAX_ASSUNTO:
        raise RegraViolada(f"Assunto longo demais: use até {MAX_ASSUNTO} caracteres.")
    texto = str(corpo or "").strip()
    if not texto:
        raise RegraViolada("Escreva a mensagem do e-mail.")
    return Mensagem(para=p, cc=c, assunto=a, corpo=texto)


def destinatarios_bloqueados(destinatarios: list[str], contatos: list[Contato]) -> list[tuple[str, str]]:
    """(e-mail, nome da pessoa) dos destinatários que pertencem a alguém com opt-out. E-mail sem cadastro passa."""
    alvo = {d.strip().lower() for d in destinatarios}
    bloqueados: list[tuple[str, str]] = []
    for c in contatos:
        if pode_receber_email(list(c.permissoes)):
            continue
        for e in c.emails:
            e = (e or "").strip().lower()
            if e in alvo and all(e != b[0] for b in bloqueados):
                bloqueados.append((e, c.nome))
    return bloqueados


def conferir_opt_out(destinatarios: list[str], contatos: list[Contato]) -> None:
    """Recusa o envio inteiro se algum destinatário pediu opt-out (a tela tira o nome e envia de novo)."""
    bloqueados = destinatarios_bloqueados(destinatarios, contatos)
    if not bloqueados:
        return
    nomes = list(dict.fromkeys(n for _, n in bloqueados))
    if len(nomes) == 1:
        raise RegraViolada(f"{nomes[0]} pediu para não receber comunicações (opt-out). Retire o e-mail e envie de novo.")
    raise RegraViolada(f"{', '.join(nomes[:-1])} e {nomes[-1]} pediram para não receber comunicações (opt-out). "
                       "Retire os e-mails e envie de novo.")


def filtrar_opt_out(destinatarios: list[str], contatos: list[Contato]) -> tuple[list[str], list[tuple[str, str]]]:
    """Para envio AUTOMÁTICO: em vez de recusar, pula quem pediu opt-out. Devolve (liberados, pulados)."""
    bloqueados = destinatarios_bloqueados(destinatarios, contatos)
    fora = {e for e, _ in bloqueados}
    return [d for d in destinatarios if d.strip().lower() not in fora], bloqueados


def conteudo_comunicacao(m: Mensagem) -> str:
    """Texto guardado na Comunicação (canal e-mail) de um e-mail enviado."""
    cabecalho = f"Para: {', '.join(m.para)}"
    if m.cc:
        cabecalho += f"\nCc: {', '.join(m.cc)}"
    return f"{cabecalho}\n\n{m.corpo}"


def linha_historico_cobranca(dia: date, m: Mensagem, usuario_nome: str) -> str:
    """"dd/mm/aaaa — E-mail enviado para … por <usuário>: <assunto>"."""
    return f"{dia:%d/%m/%Y} — E-mail enviado para {', '.join(m.para + m.cc)} por {usuario_nome}: {m.assunto}"


def acrescentar_historico(historico: str | None, linha: str) -> str:
    atual = (historico or "").rstrip()
    return f"{atual}\n{linha}" if atual else linha


def status_proposta_apos_envio(status: str, desconto_pct) -> str:
    """Enviar a proposta por e-mail marca "enviada" só se a regra de status permitir: rascunho sem desconto ou
    aprovada internamente. Com desconto ainda não aprovado (ou em aprovação, aceita, recusada…) o status fica."""
    if status == "aprovada_internamente":
        return "enviada"
    if status == "rascunho" and not exige_aprovacao_desconto(desconto_pct):
        return "enviada"
    return status


# ============================================================================================== WhatsApp (11/2026)
MAX_TELEFONES = 10
MAX_TEXTO_WHATSAPP = 4000


@dataclass(frozen=True)
class MensagemWhatsApp:
    para: list[str]  # só dígitos, com DDI (5511999990000)
    texto: str


def normalizar_whatsapp(numero: object) -> str:
    """Telefone → só dígitos com DDI 55, como a API do WhatsApp espera.

    "(11) 99999-0000", "11999990000", "+55 11 99999-0000", "011 3333-4444" → "5511999990000" / "551133334444".
    Celular (11 dígitos) precisa começar com 9 depois do DDD. Número estrangeiro só com "+" explícito (8–15 dígitos).
    Inválido → RegraViolada dizendo o que corrigir."""
    texto = " ".join(str(numero or "").split())
    d = re.sub(r"\D", "", texto)
    invalido = RegraViolada(f"Telefone inválido para WhatsApp: “{texto}”. Informe DDD e número, ex.: (11) 99999-0000.")
    if not d:
        raise invalido
    if texto.startswith("+") and not d.startswith("55"):
        if 8 <= len(d) <= 15:
            return d
        raise invalido
    if not texto.startswith("+"):
        d = d.lstrip("0")  # prefixo de longa distância (0xx)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) not in (10, 11) or d[0] == "0" or d[1] == "0":
        raise invalido
    if len(d) == 11 and d[2] != "9":
        raise invalido
    return "55" + d


def _normalizado_ou_none(numero: object) -> str | None:
    try:
        return normalizar_whatsapp(numero)
    except RegraViolada:
        return None


def validar_mensagem_whatsapp(*, para: list[str] | None, texto: str | None) -> MensagemWhatsApp:
    """Para ≥ 1 telefone válido (normalizado, sem repetir), máx. 10 por vez; texto obrigatório (até 4000)."""
    numeros: list[str] = []
    for v in para or []:
        if not str(v or "").strip():
            continue
        n = normalizar_whatsapp(v)
        if n not in numeros:
            numeros.append(n)
    if not numeros:
        raise RegraViolada("Informe ao menos um telefone em “Para”.")
    if len(numeros) > MAX_TELEFONES:
        raise RegraViolada(f"Envie para no máximo {MAX_TELEFONES} telefones por vez.")
    t = str(texto or "").strip()
    if not t:
        raise RegraViolada("Escreva a mensagem do WhatsApp.")
    if len(t) > MAX_TEXTO_WHATSAPP:
        raise RegraViolada(f"Mensagem longa demais: use até {MAX_TEXTO_WHATSAPP} caracteres.")
    return MensagemWhatsApp(para=numeros, texto=t)


def assinar_whatsapp(texto: str, nome_usuario: str | None) -> str:
    """Assinatura curta no fim: "— <nome do usuário>" (não repete se já estiver lá)."""
    nome = " ".join(str(nome_usuario or "").split())
    if not nome:
        return texto
    assinatura = f"— {nome}"
    return texto if texto.rstrip().endswith(assinatura) else f"{texto.rstrip()}\n\n{assinatura}"


def telefones_bloqueados(telefones: list[str], contatos: list[Contato]) -> list[tuple[str, str]]:
    """(telefone normalizado, nome) dos telefones que pertencem a alguém com opt-out. Telefone sem cadastro passa."""
    alvo = {n for n in (_normalizado_ou_none(t) for t in telefones) if n}
    bloqueados: list[tuple[str, str]] = []
    for c in contatos:
        if pode_receber_email(list(c.permissoes)):
            continue
        for t in c.telefones:
            n = _normalizado_ou_none(t)
            if n and n in alvo and all(n != b[0] for b in bloqueados):
                bloqueados.append((n, c.nome))
    return bloqueados


def conferir_opt_out_telefones(telefones: list[str], contatos: list[Contato]) -> None:
    """Recusa o envio inteiro se algum telefone é de quem pediu opt-out."""
    bloqueados = telefones_bloqueados(telefones, contatos)
    if not bloqueados:
        return
    nomes = list(dict.fromkeys(n for _, n in bloqueados))
    if len(nomes) == 1:
        raise RegraViolada(f"{nomes[0]} pediu para não receber comunicações (opt-out). "
                           "Retire o telefone e envie de novo.")
    raise RegraViolada(f"{', '.join(nomes[:-1])} e {nomes[-1]} pediram para não receber comunicações (opt-out). "
                       "Retire os telefones e envie de novo.")


def filtrar_opt_out_telefones(telefones: list[str],
                              contatos: list[Contato]) -> tuple[list[str], list[tuple[str, str]]]:
    """Para envio AUTOMÁTICO: devolve (liberados normalizados, pulados). Telefone inválido também é deixado de fora."""
    bloqueados = telefones_bloqueados(telefones, contatos)
    fora = {n for n, _ in bloqueados}
    liberados: list[str] = []
    for t in telefones:
        n = _normalizado_ou_none(t)
        if n and n not in fora and n not in liberados:
            liberados.append(n)
    return liberados, bloqueados


def formatar_whatsapp(numero: str) -> str:
    """"5511999990000" → "+55 (11) 99999-0000" (para registros e histórico)."""
    d = re.sub(r"\D", "", numero or "")
    if d.startswith("55") and len(d) in (12, 13):
        local = d[2:]
        meio = 5 if len(local) == 11 else 4
        return f"+55 ({local[:2]}) {local[2:2 + meio]}-{local[2 + meio:]}"
    return f"+{d}" if d else ""


def conteudo_comunicacao_whatsapp(m: MensagemWhatsApp) -> str:
    """Texto guardado na Comunicação (canal WhatsApp) de uma mensagem enviada."""
    return f"Para: {', '.join(formatar_whatsapp(n) for n in m.para)}\n\n{m.texto}"


def linha_historico_cobranca_whatsapp(dia: date, m: MensagemWhatsApp, usuario_nome: str) -> str:
    """"dd/mm/aaaa — WhatsApp enviado para … por <usuário>"."""
    return f"{dia:%d/%m/%Y} — WhatsApp enviado para {', '.join(formatar_whatsapp(n) for n in m.para)} por {usuario_nome}"
