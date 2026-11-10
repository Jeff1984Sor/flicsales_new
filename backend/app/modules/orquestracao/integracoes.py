"""Integrações (Google Calendar, Microsoft Outlook, E-mail, WhatsApp): estado, requisitos, segredo cifrado somente
escrita, "Testar conexão", revogar e último erro.

Nesta fase NENHUMA chamada externa real é feita para Google/Outlook/WhatsApp: o teste valida o formato da conta e do
segredo e marca "aguardando conector oficial". O E-mail usa o SMTP configurado no core (Configurações › E-mail).
"""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import email as mail
from app.core import segredos
from app.core.config import settings
from app.core.db import agora
from app.core.models import ConfigEmail
from app.modules.orquestracao.models import Automacao, Integracao

REQUISITOS_COMUNS = [
    "Conta: qual conta da organização será usada (nunca conta pessoal sem autorização).",
    "Escopos de leitura e escrita: só o necessário para os fluxos ativados.",
    "Responsável: quem responde pela conexão e recebe os avisos de falha.",
    "Retenção: o que é guardado no FlicSales e por quanto tempo.",
    "Fluxos dependentes: automações que usam este canal param se a conexão for revogada.",
    "Testar, reconectar e revogar a qualquer momento.",
]

CATALOGO: dict[str, dict[str, Any]] = {
    "google_calendar": {
        "nome": "Google Calendar", "grupo": "AGENDA",
        "descricao": "Eventos e participantes; conteúdo de reunião exige outra fonte.",
        "escopos": ["Ler eventos (calendar.readonly)", "Criar convites (calendar.events)"],
        "segredo_rotulo": "Token de atualização (OAuth)", "conta": "email",
        "requisitos": ["Projeto OAuth do Google Workspace aprovado pela organização."],
    },
    "outlook": {
        "nome": "Microsoft Outlook", "grupo": "AGENDA",
        "descricao": "Eventos e participantes; conteúdo de reunião exige outra fonte.",
        "escopos": ["Ler agenda (Calendars.Read)", "Criar convites (Calendars.ReadWrite)"],
        "segredo_rotulo": "Token de atualização (OAuth)", "conta": "email",
        "requisitos": ["Aplicativo registrado no Microsoft Entra ID pela organização."],
    },
    "email": {
        "nome": "E-mail", "grupo": "COMUNICAÇÃO",
        "descricao": "Leitura e envio exigem escopos próprios.",
        "escopos": ["Envio (SMTP)", "Leitura (IMAP)"],
        "segredo_rotulo": "Senha IMAP (leitura; opcional)", "conta": "email",
        "requisitos": ["Envio usa o servidor SMTP de Configurações › E-mail.",
                       "Leitura de caixa (IMAP) depende de conector próprio — ainda não captura mensagens."],
    },
    "whatsapp": {
        "nome": "WhatsApp", "grupo": "COMUNICAÇÃO",
        "descricao": "Requer conector oficial autorizado.",
        "escopos": ["Enviar mensagens com modelo aprovado", "Receber respostas"],
        "segredo_rotulo": "Token da API oficial (WhatsApp Business)", "conta": "telefone",
        "requisitos": ["Número verificado no WhatsApp Business (API oficial) e modelos de mensagem aprovados."],
    },
}

SITUACOES = {"conectado": "Conectado", "erro": "Erro na última tentativa", "aguardando_conector": "Aguardando conector oficial",
             "desconectado": "Desconectado"}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def obter(db: Session, tipo: str) -> Integracao | None:
    return db.scalar(select(Integracao).where(Integracao.tipo == tipo))


def obter_ou_criar(db: Session, tipo: str) -> Integracao:
    i = obter(db, tipo)
    if i is None:
        i = Integracao(tipo=tipo, estado="desconectado", escopos=[])
        db.add(i)
        db.flush()
    return i


def canais_conectados(db: Session) -> set[str]:
    return set(db.scalars(select(Integracao.tipo).where(Integracao.estado == "conectado")))


def situacao(i: Integracao | None) -> str:
    if i is None:
        return "desconectado"
    if i.estado in ("conectado", "erro"):
        return i.estado
    return "aguardando_conector" if i.aguardando_conector else "desconectado"


def fluxos_dependentes(db: Session, tipo: str) -> list[str]:
    q = select(Automacao).where(Automacao.estado != "pausada")
    if tipo == "email":
        q = q.where(Automacao.acao == "enviar_email")
    elif tipo == "whatsapp":
        q = q.where(Automacao.acao == "enviar_whatsapp")
    else:  # agendas: reuniões criadas por automação dependem de agenda para virar convite
        q = q.where(Automacao.acao == "criar_atividade", Automacao.tipo_atividade == "reuniao")
    return [f"{a.nome} ({a.estado})" for a in db.scalars(q.order_by(Automacao.nome))]


def saida(db: Session, tipo: str, i: Integracao | None) -> dict[str, Any]:
    cat = CATALOGO[tipo]
    final = None
    if i is not None and i.segredo_cifrado:
        try:
            final = segredos.decifrar_texto(i.segredo_cifrado)[-4:]
        except segredos.SegredoInvalido:
            final = None
    s = situacao(i)
    return {"tipo": tipo, "nome": cat["nome"], "grupo": cat["grupo"], "descricao": cat["descricao"],
            "estado": i.estado if i else "desconectado", "situacao": s, "situacao_rotulo": SITUACOES[s],
            "conta": i.conta if i else None, "escopos": list(i.escopos or []) if i else [],
            "escopos_disponiveis": cat["escopos"], "responsavel_id": i.responsavel_id if i else None,
            "segredo_definido": bool(i and i.segredo_cifrado), "segredo_final": final,
            "segredo_rotulo": cat["segredo_rotulo"], "requisitos": [*cat["requisitos"], *REQUISITOS_COMUNS],
            "fluxos_dependentes": fluxos_dependentes(db, tipo), "conectado_em": i.conectado_em if i else None,
            "testado_em": i.testado_em if i else None, "ultimo_erro": i.ultimo_erro if i else None}


def _problema_formato(tipo: str, i: Integracao) -> str | None:
    cat = CATALOGO[tipo]
    conta = (i.conta or "").strip()
    if cat["conta"] == "email" and not _EMAIL.match(conta):
        return "Informe a conta (e-mail) da organização."
    if cat["conta"] == "telefone" and not 10 <= len(re.sub(r"\D", "", conta)) <= 15:
        return "Informe o número do WhatsApp Business com DDI e DDD (ex.: +55 11 99999-0000)."
    if not i.escopos:
        return "Escolha ao menos um escopo."
    if not i.segredo_cifrado:
        return f"Informe o {cat['segredo_rotulo'].lower()}."
    if len(segredos.decifrar_texto(i.segredo_cifrado).strip()) < 20:
        return "O segredo informado parece incompleto (mínimo de 20 caracteres)."
    return None


def testar(db: Session, i: Integracao, email_usuario: str) -> str:
    """Atualiza estado/último erro e devolve a mensagem para a tela."""
    i.testado_em = agora()
    if i.tipo == "email":
        cfg = db.get(ConfigEmail, 1)
        host = (cfg and cfg.smtp_host) or settings.smtp_host
        if not host:
            i.estado, i.ultimo_erro, i.aguardando_conector = "erro", (
                "Servidor SMTP não configurado. Configure em Configurações › E-mail."), False
            return i.ultimo_erro
        ok = mail.enviar([email_usuario], "Teste da integração de e-mail",
                         "Se você recebeu esta mensagem, o envio do FlicSales está funcionando.", db=db)
        if not ok:
            i.estado, i.ultimo_erro = "erro", "Não foi possível enviar. Confira servidor, porta, usuário e senha."
            return i.ultimo_erro
        i.estado, i.ultimo_erro, i.aguardando_conector = "conectado", None, False
        i.conectado_em = i.conectado_em or agora()
        if not i.conta and cfg and cfg.remetente_email:
            i.conta = cfg.remetente_email
        if not i.escopos:
            i.escopos = ["Envio (SMTP)"]
        return f"E-mail de teste enviado para {email_usuario}. Envio conectado."
    problema = _problema_formato(i.tipo, i)
    if problema:
        i.estado, i.ultimo_erro, i.aguardando_conector = "erro", problema, False
        return problema
    i.estado, i.ultimo_erro, i.aguardando_conector = "desconectado", None, True
    return ("Formato conferido. A conexão fica aguardando o conector oficial: nenhuma chamada externa foi feita "
            "e nada será enviado ou capturado até lá.")


def revogar(db: Session, i: Integracao) -> list[Automacao]:
    """Apaga o segredo e desconecta. Automações de envio do canal são PAUSADAS (devolvidas para auditoria)."""
    i.segredo_cifrado, i.estado, i.aguardando_conector, i.conectado_em = None, "desconectado", False, None
    pausadas = []
    acao = {"email": "enviar_email", "whatsapp": "enviar_whatsapp"}.get(i.tipo)
    if acao:
        for a in db.scalars(select(Automacao).where(Automacao.acao == acao, Automacao.estado == "ativa")):
            a.estado = "pausada"
            pausadas.append(a)
    return pausadas
