"""Orquestração: automações (motor compartilhado, configuração por área) com execuções idempotentes, integrações
(segredo cifrado, somente escrita) e conversas com a IA unificada (pergunta + resposta estruturada).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamped, UtcDateTime, agora


class Automacao(Base, Timestamped):
    __tablename__ = "automacao"
    __table_args__ = (
        CheckConstraint("area IN ('comercial', 'financeiro')", name="area"),
        CheckConstraint("estado IN ('rascunho', 'ativa', 'pausada')", name="estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    area: Mapped[str] = mapped_column(String(12))
    nome: Mapped[str] = mapped_column(String(150))
    gatilho: Mapped[str] = mapped_column(String(40))  # ver docs/ESPECIFICACAO.md (gatilhos comerciais/financeiros)
    funil_id: Mapped[int | None] = mapped_column(ForeignKey("funil.id"))
    etapa_destino_id: Mapped[int | None] = mapped_column(ForeignKey("etapa.id"))
    campo: Mapped[str | None] = mapped_column(String(60))
    operador: Mapped[str | None] = mapped_column(String(12))  # igual | diferente | maior | menor | preenchido
    valor_esperado: Mapped[str | None] = mapped_column(String(200))
    prazo_dias: Mapped[int | None] = mapped_column(Integer)
    acao: Mapped[str] = mapped_column(String(25))  # criar_atividade | enviar_email | enviar_whatsapp | atualizar_campo | notificar
    tipo_atividade: Mapped[str | None] = mapped_column(String(10))
    responsavel_regra: Mapped[str | None] = mapped_column(String(60))  # ex.: "responsavel_do_registro"
    destinatario: Mapped[str | None] = mapped_column(String(200))
    conteudo: Mapped[str] = mapped_column(Text)
    revisar_condicoes: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    estado: Mapped[str] = mapped_column(String(10), default="rascunho", server_default="rascunho")


class AutomacaoExecucao(Base):
    """Uma execução (ou simulação). `chave_idempotencia` ÚNICA: a mesma automação no mesmo registro/evento não roda
    duas vezes (ex.: f"{automacao_id}:{gatilho}:oportunidade:{id}:{data}")."""

    __tablename__ = "automacao_execucao"

    id: Mapped[int] = mapped_column(primary_key=True)
    automacao_id: Mapped[int] = mapped_column(ForeignKey("automacao.id"), index=True)
    quando: Mapped[datetime] = mapped_column(UtcDateTime(), default=agora, index=True)
    chave_idempotencia: Mapped[str] = mapped_column(String(200), unique=True)
    registro: Mapped[str | None] = mapped_column(String(80))  # "oportunidade:12", "titulo:7"
    resultado: Mapped[str | None] = mapped_column(String(20))  # executada | ignorada | falhou | simulada
    simulacao: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    erro: Mapped[str | None] = mapped_column(Text)
    tentativas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Integracao(Base, Timestamped):
    """Conector (Google Calendar, Outlook, e-mail, WhatsApp). Segredo cifrado (MASTER_KEY), nunca devolvido."""

    __tablename__ = "integracao"
    __table_args__ = (
        CheckConstraint("tipo IN ('google_calendar', 'outlook', 'email', 'whatsapp')", name="tipo"),
        CheckConstraint("estado IN ('desconectado', 'conectado', 'erro')", name="estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), unique=True)
    estado: Mapped[str] = mapped_column(String(15), default="desconectado", server_default="desconectado")
    escopos: Mapped[list[str]] = mapped_column(JSON, default=list)
    conta: Mapped[str | None] = mapped_column(String(200))
    segredo_cifrado: Mapped[bytes | None] = mapped_column(LargeBinary)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    conectado_em: Mapped[datetime | None] = mapped_column(UtcDateTime())
    ultimo_erro: Mapped[str | None] = mapped_column(Text)


class IaConversa(Base, Timestamped):
    __tablename__ = "ia_conversa"
    __table_args__ = (CheckConstraint("escopo IN ('registro', 'modulo', 'tudo')", name="escopo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    escopo: Mapped[str] = mapped_column(String(10))  # Este registro | Este módulo | Toda a FlicSales
    modulo: Mapped[str | None] = mapped_column(String(20))
    tela: Mapped[str | None] = mapped_column(String(60))
    registro_tipo: Mapped[str | None] = mapped_column(String(30))
    registro_id: Mapped[int | None] = mapped_column(Integer)
    titulo: Mapped[str | None] = mapped_column(String(200))


class IaMensagem(Base):
    """Pergunta e resposta estruturada {titulo, analise, proxima_acao, evidencias, limites, acoes_sugeridas}."""

    __tablename__ = "ia_mensagem"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversa_id: Mapped[int] = mapped_column(ForeignKey("ia_conversa.id"), index=True)
    quando: Mapped[datetime] = mapped_column(UtcDateTime(), default=agora)
    pergunta: Mapped[str] = mapped_column(Text)
    resposta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ferramentas: Mapped[list[str]] = mapped_column(JSON, default=list)  # fontes consultadas
    origem: Mapped[str] = mapped_column(String(10), default="regras")  # ia | regras (IA desligada)
    provedor: Mapped[str | None] = mapped_column(String(10))
    modelo: Mapped[str | None] = mapped_column(String(100))
    erro: Mapped[str | None] = mapped_column(Text)
