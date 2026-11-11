"""Envio de e-mail. SMTP vem da tela Configurações › E-mail (senha cifrada) ou, na falta, do .env.

Sem SMTP em dev, grava a mensagem em storage/outbox (.eml). Sem SMTP em hml/prod, registra erro e devolve False.
Nunca registra o corpo da mensagem no log (pode conter link de redefinição de senha).

Assinatura (app.domain.assinatura): `remetente=<Usuario>` = e-mail enviado POR um usuário (comunicação, cobrança,
proposta) → assinatura dele (texto + imagem inline CID), ou a padrão da Identidade (texto + imagem da Identidade)
se ele não tem; `assinar=True`
sem remetente = e-mail do sistema (senha, convite) → assinatura da Identidade. Sem os dois, nada é acrescentado.

Servidor (contrato de envio 11/2026): `remetente=<Usuario>` com SMTP próprio ativo (`ConfigEmailUsuario`) → sai por
ele, com `From` dele; senão sai pelo SMTP da organização (`ConfigEmail` id=1 ou .env) com `Reply-To` = e-mail do
usuário. E-mails do sistema sempre pelo SMTP da organização. `smtp_para(db, usuario)` diz qual servidor seria usado
(a tela "Enviar como …" e `app.core.envio` usam).
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core import segredos, storage
from app.core.config import settings
from app.core.db import agora
from app.core.models import ConfigEmail, ConfigEmailUsuario, Identidade, Usuario
from app.domain import assinatura as _assinatura

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Smtp:
    """Servidor escolhido para um envio. `origem`: "usuario" (SMTP próprio) | "organizacao" (tela ou .env)."""

    host: str
    porta: int
    usuario: str | None
    senha: str | None
    remetente: str  # cabeçalho From pronto ("Nome <email>")
    origem: str


def _endereco(nome: str, email: str) -> str:
    return f"{nome} <{email}>"


def _remetente_org(config: ConfigEmail | None) -> str:
    if config:
        return _endereco(config.remetente_nome, config.remetente_email)
    return settings.smtp_from


def smtp_da_organizacao(db: Session | None) -> Smtp | None:
    """SMTP da organização (tela; na falta, .env). None = não configurado."""
    config = db.get(ConfigEmail, 1) if db is not None else None
    host = (config and config.smtp_host) or settings.smtp_host
    if not host:
        return None
    porta = config.smtp_porta if config and config.smtp_host else settings.smtp_port
    usuario = (config and config.smtp_usuario) or settings.smtp_user
    senha = settings.smtp_password
    if config and config.smtp_senha_cifrada:
        senha = segredos.decifrar_texto(config.smtp_senha_cifrada)
    return Smtp(host, porta, usuario, senha, _remetente_org(config), "organizacao")


def smtp_de_config_usuario(c: ConfigEmailUsuario) -> Smtp:
    senha = segredos.decifrar_texto(c.smtp_senha_cifrada) if c.smtp_senha_cifrada else None
    return Smtp(c.smtp_host, c.smtp_porta, c.smtp_usuario, senha, _endereco(c.remetente_nome, c.remetente_email),
                "usuario")


def smtp_do_usuario(db: Session | None, usuario: Usuario | None) -> Smtp | None:
    """SMTP próprio do usuário, se cadastrado e ativo."""
    if db is None or usuario is None or usuario.id is None:
        return None
    c = db.get(ConfigEmailUsuario, usuario.id)
    if c is None or not c.ativo or not c.smtp_host:
        return None
    return smtp_de_config_usuario(c)


def smtp_para(db: Session | None, remetente: Usuario | None) -> Smtp | None:
    """Servidor que um envio usaria: o do usuário (se tiver) ou o da organização. None = nenhum configurado."""
    return smtp_do_usuario(db, remetente) or smtp_da_organizacao(db)


def _conectar(smtp: Smtp) -> smtplib.SMTP:
    """Abre a conexão (465 = SSL direto; outras portas = STARTTLS) e faz login se houver usuário e senha."""
    if smtp.porta == 465:
        conexao: smtplib.SMTP = smtplib.SMTP_SSL(smtp.host, smtp.porta, timeout=30)
    else:
        conexao = smtplib.SMTP(smtp.host, smtp.porta, timeout=30)
    try:
        if smtp.porta != 465:
            conexao.starttls()
        if smtp.usuario and smtp.senha:
            conexao.login(smtp.usuario, smtp.senha)
    except BaseException:
        try:
            conexao.close()
        except Exception:  # noqa: BLE001 - só fechando a conexão que falhou
            pass
        raise
    return conexao


def motivo_falha(e: BaseException) -> str:
    """Texto curto (sem senha nem resposta crua do servidor) para mostrar na tela."""
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "o servidor recusou o usuário ou a senha."
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "o servidor recusou o destinatário."
    if isinstance(e, smtplib.SMTPSenderRefused):
        return "o servidor recusou o remetente."
    if isinstance(e, smtplib.SMTPNotSupportedError):
        return "o servidor não aceita conexão segura (STARTTLS) nesta porta."
    if isinstance(e, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError)):
        return "não foi possível conectar ao servidor (confira servidor e porta)."
    return "o servidor recusou a mensagem."


def testar_login(smtp: Smtp) -> tuple[bool, str]:
    """Conecta e faz login, sem enviar nada. (ok, mensagem para a tela)."""
    try:
        with _conectar(smtp):
            pass
    except (smtplib.SMTPException, OSError) as e:
        log.info("Teste de SMTP falhou (%s): %s", smtp.host, type(e).__name__)
        return False, f"Não foi possível conectar: {motivo_falha(e)}"
    return True, "Conexão com o servidor de e-mail confirmada."


def enviar(
    para: list[str],
    assunto: str,
    corpo: str,
    *,
    db: Session | None = None,
    anexos: list[tuple[str, bytes, str]] | None = None,
    cc: list[str] | None = None,
    cco: list[str] | None = None,
    html: str | None = None,
    imagens: dict[str, tuple[bytes, str]] | None = None,
    remetente: Usuario | None = None,
    assinar: bool = False,
    erros: list[str] | None = None,
) -> bool:
    """Devolve True se a mensagem foi entregue ao SMTP (ou gravada no outbox em dev).

    `html`: versão HTML (multipart/alternative; `corpo` fica como texto puro). `imagens`: {cid: (bytes, mime)} embutidas
    no HTML (`<img src="cid:logo">`), em multipart/related. `erros`: se informada, recebe o motivo curto da falha."""
    if remetente is not None or assinar:
        corpo, html, imagens = assinar_mensagem(db, corpo, html, imagens, remetente=remetente)
    smtp = smtp_para(db, remetente)
    msg = EmailMessage()
    if smtp is not None:
        msg["From"] = smtp.remetente
    else:
        msg["From"] = _remetente_org(db.get(ConfigEmail, 1) if db is not None else None)
    if remetente is not None and remetente.email and (smtp is None or smtp.origem != "usuario"):
        msg["Reply-To"] = _endereco(remetente.nome, remetente.email)  # saiu pela organização: resposta vai a ele
    msg["To"] = ", ".join(para)
    if cc:
        msg["Cc"] = ", ".join(cc)
    todos = list(dict.fromkeys([*para, *(cc or []), *(cco or [])]))  # Cco só entra na lista de entrega
    msg["Subject"] = assunto
    msg.set_content(corpo)
    if html:
        msg.add_alternative(html, subtype="html")
        if imagens:
            parte_html = msg.get_payload()[-1]
            for cid, (dados, mime) in imagens.items():
                maintype, subtype = mime.split("/", 1)
                parte_html.add_related(dados, maintype=maintype, subtype=subtype, cid=f"<{cid}>")
    for nome, dados, mime in anexos or []:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(dados, maintype=maintype, subtype=subtype, filename=nome)

    if smtp is None:
        if settings.ambiente != "dev":
            log.error("SMTP não configurado: e-mail '%s' não enviado.", assunto)
            if erros is not None:
                erros.append("nenhum servidor de e-mail configurado.")
            return False
        outbox = storage.raiz() / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        arq = outbox / f"{agora():%Y%m%d-%H%M%S-%f}.eml"
        arq.write_bytes(bytes(msg))
        log.info("E-mail gravado em %s (SMTP não configurado)", arq.name)
        return True

    try:
        with _conectar(smtp) as s:
            s.send_message(msg, to_addrs=todos)
    except (smtplib.SMTPException, OSError) as e:
        log.error("Falha ao enviar e-mail '%s' (%s): %s", assunto, smtp.origem, type(e).__name__)
        if erros is not None:
            erros.append(motivo_falha(e))
        return False
    return True


_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def assinar_mensagem(db: Session | None, corpo: str, html: str | None,
                     imagens: dict[str, tuple[bytes, str]] | None, *, remetente: Usuario | None = None,
                     ) -> tuple[str, str | None, dict[str, tuple[bytes, str]] | None]:
    """Acrescenta a assinatura (do `remetente` ou, sem ele/sem assinatura própria, a da Identidade)."""
    identidade = db.get(Identidade, 1) if db is not None else None
    caminho_usuario = remetente.assinatura_imagem if remetente is not None else None
    caminho_identidade = identidade.assinatura_imagem if identidade else None
    escolha = _assinatura.escolher(
        texto_usuario=remetente.assinatura_email if remetente is not None else None,
        tem_imagem_usuario=storage.existe(caminho_usuario),
        texto_identidade=identidade.assinatura_email if identidade else None, do_sistema=remetente is None,
        tem_imagem_identidade=storage.existe(caminho_identidade))
    corpo, html = _assinatura.aplicar(corpo, html, escolha)
    caminho = caminho_usuario if escolha.origem == "usuario" else caminho_identidade
    if escolha.com_imagem and caminho:
        ext = "." + caminho.rsplit(".", 1)[-1].lower()
        imagens = {**(imagens or {}), _assinatura.CID_IMAGEM: (storage.ler(caminho), _MIME.get(ext, "image/png"))}
    return corpo, html, imagens
