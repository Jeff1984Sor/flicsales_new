"""Financeiro: títulos (a receber/a pagar), baixas (com estorno, nunca apagadas), transferências, recorrências e
cobranças.

Venda ≠ recebimento ≠ caixa: o ganho de uma oportunidade gera títulos em RASCUNHO (idempotente pela UNIQUE
(origem_oportunidade_id, parcela)); recorrência gera um título por competência (UNIQUE (origem_recorrencia_id,
competencia)). Regras: app/domain/titulos.py, caixa.py, recorrencia.py, fechamento.py.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamped, UtcDateTime
from app.modules.base import Dinheiro


class Titulo(Base, Timestamped):
    """`status` guardado: rascunho | aberto | parcial | liquidado | cancelado. "Vencido" é DERIVADO (aberto/parcial com
    vencimento < hoje; app.domain.titulos.status_exibido). `saldo` = valor_original − baixas não estornadas."""

    __tablename__ = "titulo"
    __table_args__ = (
        UniqueConstraint("origem_oportunidade_id", "parcela", name="uq_titulo_oportunidade_parcela"),
        UniqueConstraint("origem_recorrencia_id", "competencia", name="uq_titulo_recorrencia_competencia"),
        CheckConstraint("direcao IN ('receber', 'pagar')", name="direcao"),
        CheckConstraint("status IN ('rascunho', 'aberto', 'parcial', 'liquidado', 'cancelado')", name="status"),
        CheckConstraint("valor_original > 0", name="valor_original"),
        CheckConstraint("saldo >= 0 AND saldo <= valor_original", name="saldo"),
        CheckConstraint("aprovacao IS NULL OR aprovacao IN ('pendente', 'aprovado')", name="aprovacao"),
        Index("ix_titulo_direcao_status_vencimento", "direcao", "status", "vencimento"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    direcao: Mapped[str] = mapped_column(String(7))  # receber | pagar
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)  # cliente ou fornecedor
    descricao: Mapped[str] = mapped_column(String(300))
    documento: Mapped[str | None] = mapped_column(String(60))
    emissao: Mapped[date | None] = mapped_column(Date)
    competencia: Mapped[str | None] = mapped_column(String(7))  # AAAA-MM
    vencimento: Mapped[date] = mapped_column(Date, index=True)
    valor_original: Mapped[Decimal] = mapped_column(Dinheiro)
    saldo: Mapped[Decimal] = mapped_column(Dinheiro)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    centro_custo_id: Mapped[int | None] = mapped_column(ForeignKey("centro_custo.id"))
    conta_prevista_id: Mapped[int | None] = mapped_column(ForeignKey("conta_financeira.id"))
    forma: Mapped[str | None] = mapped_column(String(15))  # pix | boleto | transferencia | cartao | dinheiro | outra
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    observacoes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="rascunho", server_default="rascunho")
    aprovacao: Mapped[str | None] = mapped_column(String(10))  # só a pagar: pendente | aprovado
    aprovado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    aprovado_em: Mapped[datetime | None] = mapped_column(UtcDateTime())
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text)
    cancelado_em: Mapped[datetime | None] = mapped_column(UtcDateTime())
    confirmado_em: Mapped[datetime | None] = mapped_column(UtcDateTime())  # rascunho → aberto
    origem_oportunidade_id: Mapped[int | None] = mapped_column(ForeignKey("oportunidade.id"), index=True)
    origem_recorrencia_id: Mapped[int | None] = mapped_column(ForeignKey("recorrencia.id"), index=True)
    parcela: Mapped[int | None] = mapped_column(Integer)  # n (de parcelas_total)
    parcelas_total: Mapped[int | None] = mapped_column(Integer)


class Baixa(Base, Timestamped):
    """Recebimento/pagamento gerencial. NUNCA é apagada: corrigir é estornar (com motivo; o movimento fica)."""

    __tablename__ = "baixa"
    __table_args__ = (CheckConstraint("valor > 0", name="valor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo_id: Mapped[int] = mapped_column(ForeignKey("titulo.id"), index=True)
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    data: Mapped[date] = mapped_column(Date, index=True)
    conta_id: Mapped[int] = mapped_column(ForeignKey("conta_financeira.id"), index=True)
    forma: Mapped[str] = mapped_column(String(15))
    referencia_comprovante: Mapped[str | None] = mapped_column(String(200))
    observacao: Mapped[str | None] = mapped_column(Text)
    registrada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    estornada: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    estorno_motivo: Mapped[str | None] = mapped_column(Text)
    estornada_em: Mapped[datetime | None] = mapped_column(UtcDateTime())
    estornada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class Transferencia(Base, Timestamped):
    """Entre contas: não é receita nem despesa."""

    __tablename__ = "transferencia"
    __table_args__ = (
        CheckConstraint("valor > 0", name="valor"),
        CheckConstraint("conta_origem_id <> conta_destino_id", name="contas_diferentes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conta_origem_id: Mapped[int] = mapped_column(ForeignKey("conta_financeira.id"), index=True)
    conta_destino_id: Mapped[int] = mapped_column(ForeignKey("conta_financeira.id"), index=True)
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    data: Mapped[date] = mapped_column(Date)
    descricao: Mapped[str | None] = mapped_column(String(300))


class Recorrencia(Base, Timestamped):
    __tablename__ = "recorrencia"
    __table_args__ = (
        CheckConstraint("direcao IN ('receber', 'pagar')", name="direcao"),
        CheckConstraint("frequencia IN ('mensal', 'trimestral', 'anual')", name="frequencia"),
        CheckConstraint("situacao IN ('ativa', 'pausada', 'cancelada')", name="situacao"),
        CheckConstraint("dia_vencimento BETWEEN 1 AND 28", name="dia_vencimento"),
        CheckConstraint("valor_ciclo > 0", name="valor_ciclo"),
        CheckConstraint("fim >= inicio", name="vigencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    descricao: Mapped[str] = mapped_column(String(300))
    direcao: Mapped[str] = mapped_column(String(7))
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    valor_ciclo: Mapped[Decimal] = mapped_column(Dinheiro)
    frequencia: Mapped[str] = mapped_column(String(10))
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    dia_vencimento: Mapped[int] = mapped_column(Integer)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    centro_custo_id: Mapped[int | None] = mapped_column(ForeignKey("centro_custo.id"))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    situacao: Mapped[str] = mapped_column(String(10), default="ativa", server_default="ativa")


class Cobranca(Base, Timestamped):
    __tablename__ = "cobranca"
    __table_args__ = (
        CheckConstraint("situacao IN ('em_acompanhamento', 'promessa_pagamento', 'em_contestacao', 'resolvida')",
                        name="situacao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assunto: Mapped[str] = mapped_column(String(200))
    titulo_id: Mapped[int] = mapped_column(ForeignKey("titulo.id"), index=True)
    responsavel_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    canal: Mapped[str] = mapped_column(String(15))
    situacao: Mapped[str] = mapped_column(String(20), default="em_acompanhamento", server_default="em_acompanhamento")
    data_prometida: Mapped[date | None] = mapped_column(Date)
    valor_prometido: Mapped[Decimal | None] = mapped_column(Dinheiro)
    proximo_contato: Mapped[date | None] = mapped_column(Date)
    historico: Mapped[str] = mapped_column(Text)
