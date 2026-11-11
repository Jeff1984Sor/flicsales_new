"""Comercial: funis e etapas, oportunidades (com histórico compartilhado), atividades, comunicações, propostas, metas,
playbooks, modelos de comunicação e indicadores configuráveis.

Regras (app/domain): funil.py (etapas, forecast, dias na etapa, ganho/perda), proposta.py, atividade.py,
indicadores.py, fechamento.py (ganho → recebíveis em rascunho).
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamped, UtcDateTime, agora
from app.modules.base import Dinheiro


class Funil(Base, Timestamped):
    __tablename__ = "funil"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class Etapa(Base, Timestamped):
    """Etapa do funil. "Ganha" e "Perdida" NÃO são etapas: são o `resultado` da oportunidade."""

    __tablename__ = "etapa"
    __table_args__ = (
        UniqueConstraint("funil_id", "nome", name="uq_etapa_funil_nome"),
        CheckConstraint("probabilidade >= 0 AND probabilidade <= 100", name="probabilidade"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    funil_id: Mapped[int] = mapped_column(ForeignKey("funil.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    probabilidade: Mapped[int] = mapped_column(Integer, default=0)  # 0–100, parâmetro (não previsão de IA)
    limite_dias: Mapped[int | None] = mapped_column(Integer)
    criterios: Mapped[str | None] = mapped_column(Text)


class Oportunidade(Base, Timestamped):
    __tablename__ = "oportunidade"
    __table_args__ = (
        CheckConstraint("resultado IN ('aberta', 'ganha', 'perdida')", name="resultado"),
        Index("ix_oportunidade_funil_resultado", "funil_id", "resultado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    funil_id: Mapped[int] = mapped_column(ForeignKey("funil.id"))
    etapa_id: Mapped[int | None] = mapped_column(ForeignKey("etapa.id"), index=True)
    resultado: Mapped[str] = mapped_column(String(10), default="aberta", server_default="aberta")
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    contato_id: Mapped[int | None] = mapped_column(ForeignKey("pessoa.id"))
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    valor_unico: Mapped[Decimal] = mapped_column(Dinheiro, default=Decimal("0.00"))
    valor_recorrente_mensal: Mapped[Decimal] = mapped_column(Dinheiro, default=Decimal("0.00"))
    previsao_fechamento: Mapped[date | None] = mapped_column(Date)
    proxima_acao: Mapped[str | None] = mapped_column(String(300))
    proxima_acao_prazo: Mapped[date | None] = mapped_column(Date)
    origem: Mapped[str | None] = mapped_column(String(100))
    necessidade: Mapped[str | None] = mapped_column(Text)
    decisor: Mapped[str | None] = mapped_column(String(200))
    orcamento_concorrencia: Mapped[str | None] = mapped_column(Text)
    criterio_sucesso: Mapped[str | None] = mapped_column(Text)
    motivo_perda: Mapped[str | None] = mapped_column(Text)
    concorrente: Mapped[str | None] = mapped_column(String(200))
    data_retomada: Mapped[date | None] = mapped_column(Date)
    ganha_em: Mapped[date | None] = mapped_column(Date)
    perdida_em: Mapped[date | None] = mapped_column(Date)
    entrou_etapa_em: Mapped[date | None] = mapped_column(Date)  # base de "dias na etapa" vs limite
    campos_custom: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # ex.: {"interesse": "Alto"}


class OportunidadeEvento(Base):
    """Histórico compartilhado da oportunidade (etapa, reunião vinculada, proposta, nota, ganho, perda…)."""

    __tablename__ = "oportunidade_evento"

    id: Mapped[int] = mapped_column(primary_key=True)
    oportunidade_id: Mapped[int] = mapped_column(ForeignKey("oportunidade.id"), index=True)
    quando: Mapped[datetime] = mapped_column(UtcDateTime(), default=agora)
    tipo: Mapped[str] = mapped_column(String(30))
    texto: Mapped[str] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class Atividade(Base, Timestamped):
    """Criar atividade ≠ enviar mensagem: envio só com conector autorizado (Integrações)."""

    __tablename__ = "atividade"
    __table_args__ = (
        CheckConstraint("tipo IN ('tarefa', 'email', 'ligacao', 'whatsapp', 'reuniao')", name="tipo"),
        CheckConstraint("status IN ('pendente', 'concluida')", name="status"),
        Index("ix_atividade_responsavel_prazo", "responsavel_id", "prazo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assunto: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(10))
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    oportunidade_id: Mapped[int | None] = mapped_column(ForeignKey("oportunidade.id"), index=True)
    prazo: Mapped[date] = mapped_column(Date)
    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fim: Mapped[time | None] = mapped_column(Time)
    fuso: Mapped[str] = mapped_column(String(40), default="America/Sao_Paulo")
    participantes: Mapped[str | None] = mapped_column(Text)
    canal: Mapped[str | None] = mapped_column(String(300))  # link, telefone ou endereço
    objetivo: Mapped[str | None] = mapped_column(Text)
    resultado: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pendente", server_default="pendente")
    concluida_em: Mapped[datetime | None] = mapped_column(UtcDateTime())
    origem: Mapped[str] = mapped_column(String(10), default="manual", server_default="manual")  # manual|automacao|ia


class Comunicacao(Base, Timestamped):
    """Conversa vinculada (texto colado/importado). O conteúdo é DADO, nunca instrução para a IA."""

    __tablename__ = "comunicacao"
    __table_args__ = (CheckConstraint("canal IN ('reuniao', 'email', 'whatsapp', 'notas')", name="canal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    canal: Mapped[str] = mapped_column(String(10))
    titulo: Mapped[str | None] = mapped_column(String(200))
    conteudo: Mapped[str] = mapped_column(Text)
    data: Mapped[date | None] = mapped_column(Date)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    oportunidade_id: Mapped[int | None] = mapped_column(ForeignKey("oportunidade.id"), index=True)
    analise: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # necessidades, objeções, compromissos, citações
    analisada_em: Mapped[datetime | None] = mapped_column(UtcDateTime())


class Proposta(Base, Timestamped):
    """total = quantidade × preço unitário × (1 − desconto). Desconto > 0 exige justificativa (domain/proposta.py).
    "Aceita" não fecha a oportunidade sozinha."""

    __tablename__ = "proposta"
    __table_args__ = (
        UniqueConstraint("oportunidade_id", "versao", name="uq_proposta_oportunidade_versao"),
        CheckConstraint("quantidade > 0", name="quantidade"),
        CheckConstraint("desconto_pct >= 0 AND desconto_pct <= 100", name="desconto"),
        CheckConstraint("status IN ('rascunho', 'em_aprovacao', 'aprovada_internamente', 'enviada', 'aceita', 'recusada')",
                        name="status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    oportunidade_id: Mapped[int] = mapped_column(ForeignKey("oportunidade.id"), index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    escopo: Mapped[str] = mapped_column(Text)
    produto_id: Mapped[int | None] = mapped_column(ForeignKey("produto.id"))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(15, 3))
    preco_unitario: Mapped[Decimal] = mapped_column(Dinheiro)
    desconto_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    mensalidade_adicional: Mapped[Decimal] = mapped_column(Dinheiro, default=Decimal("0.00"))
    validade: Mapped[date] = mapped_column(Date)
    condicao: Mapped[str] = mapped_column(String(40))  # à vista | 2x | 3x | recorrente mensal
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    status: Mapped[str] = mapped_column(String(25), default="rascunho", server_default="rascunho")
    justificativa_desconto: Mapped[str | None] = mapped_column(Text)
    total: Mapped[Decimal] = mapped_column(Dinheiro)
    # 0008: modelo usado para gerar o documento/PDF (null = o modelo padrão)
    modelo_proposta_id: Mapped[int | None] = mapped_column(ForeignKey("modelo_proposta.id"))


class ModeloProposta(Base, Timestamped):
    """Modelo do documento da proposta (0008): textos com variáveis ({{empresa.nome}}, {{contato.nome}},
    {{oportunidade.titulo}}, {{proposta.total}}, {{proposta.validade}}…), validade e condição padrão. Um é o padrão."""

    __tablename__ = "modelo_proposta"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    padrao: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    introducao: Mapped[str | None] = mapped_column(Text)
    termos: Mapped[str | None] = mapped_column(Text)
    rodape: Mapped[str | None] = mapped_column(Text)
    validade_dias: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    condicao_padrao: Mapped[str | None] = mapped_column(String(40))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class Meta(Base, Timestamped):
    __tablename__ = "meta"
    __table_args__ = (
        CheckConstraint("fim >= inicio", name="periodo"),
        CheckConstraint("responsavel_tipo IN ('pessoa', 'equipe')", name="responsavel_tipo"),
        CheckConstraint("indicador IN ('receita_unica_ganha', 'mrr_novo', 'vendas_ganhas', 'atividades_concluidas')",
                        name="indicador"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    responsavel_tipo: Mapped[str] = mapped_column(String(10), default="pessoa")  # pessoa | equipe
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))  # quando pessoa
    equipe: Mapped[str | None] = mapped_column(String(120))  # quando equipe
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    indicador: Mapped[str] = mapped_column(String(30))
    alvo: Mapped[Decimal] = mapped_column(Dinheiro)  # moeda ou quantidade, conforme o indicador
    funil_id: Mapped[int | None] = mapped_column(ForeignKey("funil.id"))


class Playbook(Base, Timestamped):
    __tablename__ = "playbook"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    funil_id: Mapped[int | None] = mapped_column(ForeignKey("funil.id"))
    etapa_id: Mapped[int | None] = mapped_column(ForeignKey("etapa.id"))
    objetivo: Mapped[str] = mapped_column(Text)
    perguntas_discovery: Mapped[str | None] = mapped_column(Text)
    criterios_avanco: Mapped[str] = mapped_column(Text)
    objecoes: Mapped[str | None] = mapped_column(Text)
    proxima_acao_padrao: Mapped[str | None] = mapped_column(Text)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class ModeloComunicacao(Base, Timestamped):
    """Modelo com variáveis ({{empresa.nome}}, {{contato.nome}}, {{oportunidade.titulo}}, {{titulo.valor}}…)."""

    __tablename__ = "modelo_comunicacao"
    __table_args__ = (
        CheckConstraint("canal IN ('email', 'whatsapp', 'ligacao', 'reuniao')", name="canal"),
        CheckConstraint("status IN ('rascunho', 'revisado')", name="status"),
        CheckConstraint("classificacao IN ('comercial', 'financeiro', 'geral')", name="classificacao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    canal: Mapped[str] = mapped_column(String(10))
    # migração 0006 (app.domain.modelos_comunicacao): quem usa o modelo. Comercial lista comercial+geral; Financeiro
    # (cobranças) lista financeiro+geral; automações listam todos.
    classificacao: Mapped[str] = mapped_column(String(12), default="comercial", server_default="comercial")
    finalidade: Mapped[str] = mapped_column(String(20))  # prospeccao | follow_up | proposta | cobranca | renovacao
    assunto: Mapped[str | None] = mapped_column(String(200))
    conteudo: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="rascunho", server_default="rascunho")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class IndicadorConfig(Base, Timestamped):
    """Indicador configurável dos dashboards: objeto, métrica e filtro por campo personalizado."""

    __tablename__ = "indicador_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    objeto: Mapped[str] = mapped_column(String(15), default="oportunidade")
    metrica: Mapped[str] = mapped_column(String(20))  # soma_valor_unico | quantidade
    filtro_campo_id: Mapped[int | None] = mapped_column(ForeignKey("campo_custom.id"))
    filtro_valor: Mapped[str | None] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
