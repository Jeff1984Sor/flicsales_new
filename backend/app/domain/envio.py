"""Envio de e-mail por um usuário (contrato de envio 11/2026). Funções puras: validar a mensagem, bloquear opt-out e
montar os textos que ficam registrados (comunicação, histórico da cobrança).

O serviço que fala com o banco e com o SMTP é `app.core.envio.enviar_por_usuario`; todo envio feito POR um usuário
(e qualquer envio automático futuro) passa por ele e, portanto, por `destinatarios_bloqueados`.
"""

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
