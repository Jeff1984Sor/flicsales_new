"""Serviço único de envio de e-mail POR um usuário (comunicação, proposta, cobrança). Contrato de envio 11/2026.

Todo e-mail que um usuário manda pelo sistema passa por `enviar_por_usuario`: valida a mensagem, recusa destinatário
com opt-out (app.domain.envio), escolhe o servidor (SMTP próprio do usuário → organização → outbox em dev) e acrescenta a
assinatura. Envio automático (automação, worker) deve usar `destinatarios_liberados`, que PULA quem pediu opt-out e
registra no log. Erros saem como `RegraViolada` (HTTP 400) em PT-BR, sem senha nem resposta crua do servidor.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import String, cast, select
from sqlalchemy.orm import Session

from app.core import email as mail
from app.core.config import settings
from app.core.models import ConfigEmail, Usuario
from app.domain import RegraViolada
from app.domain import envio as dom
from app.domain.cadastro import OPT_OUT

log = logging.getLogger(__name__)

SEM_SMTP = "Configure o e-mail de envio em Configurações › E-mail ou em Minha conta."


@dataclass(frozen=True)
class Via:
    """Como um e-mail do usuário sairia agora. `via` None = não há como enviar."""

    pode_enviar: bool
    via: str | None  # "usuario" | "organizacao" | "outbox" | None
    remetente: str | None  # "Nome <email>" do From


def via_de_envio(db: Session, usuario: Usuario) -> Via:
    smtp = mail.smtp_para(db, usuario)
    if smtp is not None:
        return Via(True, smtp.origem, smtp.remetente)
    if settings.ambiente == "dev":
        cfg = db.get(ConfigEmail, 1)
        remetente = f"{cfg.remetente_nome} <{cfg.remetente_email}>" if cfg else settings.smtp_from
        return Via(True, "outbox", remetente)
    return Via(False, None, None)


def contatos_com_opt_out(db: Session) -> list[dom.Contato]:
    """Pessoas que pediram opt-out, com todos os e-mails delas (principal + adicionais)."""
    from app.modules.nucleo.models import Pessoa  # import tardio: core não depende dos módulos na carga

    pessoas = db.scalars(select(Pessoa).where(cast(Pessoa.permissoes_comunicacao, String).like(f"%{OPT_OUT}%")))
    contatos = []
    for p in pessoas:
        emails = {p.email or ""} | {str(e.get("email") or "") for e in (p.emails or []) if isinstance(e, dict)}
        contatos.append(dom.Contato(p.nome, tuple(sorted(e for e in emails if e)),
                                    tuple(p.permissoes_comunicacao or [])))
    return contatos


def destinatarios_liberados(db: Session, destinatarios: list[str], *, origem: str = "automação") -> list[str]:
    """Para envio AUTOMÁTICO: devolve só quem pode receber; quem pediu opt-out é pulado e registrado no log."""
    liberados, pulados = dom.filtrar_opt_out(destinatarios, contatos_com_opt_out(db))
    for _email, nome in pulados:
        log.info("Envio automático (%s) pulou %s: opt-out.", origem, nome)
    return liberados


def enviar_por_usuario(db: Session, usuario: Usuario, *, para: list[str], cc: list[str] | None = None, assunto: str,
                       corpo: str, anexos: list[tuple[str, bytes, str]] | None = None) -> dom.Mensagem:
    """Envia em nome de `usuario`. Devolve a mensagem normalizada (destinatários minúsculos, sem repetição)."""
    m = dom.validar_mensagem(para=para, cc=cc, assunto=assunto, corpo=corpo)
    dom.conferir_opt_out(m.para + m.cc, contatos_com_opt_out(db))
    if not via_de_envio(db, usuario).pode_enviar:
        raise RegraViolada(SEM_SMTP)
    erros: list[str] = []
    ok = mail.enviar(m.para, m.assunto, m.corpo, db=db, cc=m.cc or None, anexos=anexos, remetente=usuario,
                     erros=erros)
    if not ok:
        raise RegraViolada(f"Não foi possível enviar o e-mail: {erros[0] if erros else 'tente novamente.'}")
    return m
