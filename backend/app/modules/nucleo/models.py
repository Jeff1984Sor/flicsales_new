"""Núcleo: cadastros compartilhados pelos três módulos (empresa, pessoa, produto) e cadastros de apoio
(categoria, centro de custo, conta financeira, campo personalizado).

DECISÃO (Fundação, 10/11/2026) — FORNECEDOR: não existe tabela `fornecedor`. Fornecedor é uma `empresa` com
`papel_fornecedor = True` + duas colunas extras na própria empresa (`categoria_padrao_id`, `condicao_habitual`).
A tela Financeiro › Fornecedores é uma visão filtrada da empresa (mesmo cadastro, renomear atualiza tudo).

DECISÃO — PAPÉIS: em vez de JSON, quatro booleanos (`papel_prospect/cliente/fornecedor/parceiro`) indexáveis e
filtráveis igual no SQLite e no Postgres; a propriedade `papeis` devolve a lista.

DECISÃO — NOME ÚNICO: `nome` é UNIQUE e `nome_chave` (minúsculo, sem acento, espaços colapsados) também, preenchida
sozinha por evento (app.domain.cadastro.chave_de_nome). Nome duplicado é recusado ("Já existe empresa com este nome").
"""

from datetime import date
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
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamped
from app.domain.cadastro import PAPEIS_EMPRESA, chave_de_nome
from app.modules.base import Dinheiro


class Empresa(Base, Timestamped):
    __tablename__ = "empresa"
    __table_args__ = (
        Index("ix_empresa_papel_cliente", "papel_cliente"),
        Index("ix_empresa_papel_fornecedor", "papel_fornecedor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True)
    nome_chave: Mapped[str] = mapped_column(String(200), unique=True)  # ver chave_de_nome (preenchida por evento)
    documento: Mapped[str | None] = mapped_column(String(18), index=True)  # CNPJ/CPF (só dígitos ou formatado)
    nome_fantasia: Mapped[str | None] = mapped_column(String(200))
    segmento: Mapped[str | None] = mapped_column(String(100))
    porte: Mapped[str | None] = mapped_column(String(30))
    site: Mapped[str | None] = mapped_column(String(300))
    email_financeiro: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(30))
    endereco: Mapped[str | None] = mapped_column(Text)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    papel_prospect: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    papel_cliente: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    papel_fornecedor: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    papel_parceiro: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    origem: Mapped[str | None] = mapped_column(String(100))
    observacoes: Mapped[str | None] = mapped_column(Text)
    campos_custom: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # extras de fornecedor (só fazem sentido com papel_fornecedor)
    categoria_padrao_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    condicao_habitual: Mapped[str | None] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    @property
    def papeis(self) -> list[str]:
        return [p for p in PAPEIS_EMPRESA if getattr(self, f"papel_{p}")]

    @papeis.setter
    def papeis(self, valores: list[str]) -> None:
        for p in PAPEIS_EMPRESA:
            setattr(self, f"papel_{p}", p in (valores or []))


@event.listens_for(Empresa, "before_insert")
@event.listens_for(Empresa, "before_update")
def _chave_da_empresa(_mapper, _conn, alvo: Empresa) -> None:
    alvo.nome_chave = chave_de_nome(alvo.nome)


class Pessoa(Base, Timestamped):
    __tablename__ = "pessoa"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), index=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresa.id"), index=True)
    cargo: Mapped[str | None] = mapped_column(String(120))  # papel na compra
    email: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(30))
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"), index=True)
    canal_preferido: Mapped[str | None] = mapped_column(String(15))  # email | ligacao | whatsapp
    observacoes: Mapped[str | None] = mapped_column(Text)
    campos_custom: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class Produto(Base, Timestamped):
    __tablename__ = "produto"
    __table_args__ = (CheckConstraint("tipo IN ('servico', 'produto')", name="tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True)
    tipo: Mapped[str] = mapped_column(String(10))  # servico | produto
    codigo: Mapped[str | None] = mapped_column(String(50), unique=True)
    unidade: Mapped[str | None] = mapped_column(String(30))
    preco_referencia: Mapped[Decimal | None] = mapped_column(Dinheiro)
    recorrente: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class Categoria(Base, Timestamped):
    """Plano de contas gerencial (receita/despesa), com subcategorias por `superior_id`."""

    __tablename__ = "categoria"
    __table_args__ = (
        CheckConstraint("natureza IN ('receita', 'despesa')", name="natureza"),
        UniqueConstraint("natureza", "superior_id", "nome", name="uq_categoria_natureza_superior_nome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    natureza: Mapped[str] = mapped_column(String(10))  # receita | despesa
    superior_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"), index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class CentroCusto(Base, Timestamped):
    __tablename__ = "centro_custo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    responsavel_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class ContaFinanceira(Base, Timestamped):
    """Conta gerencial (banco, caixa). Saldo inicial pode ser negativo. Com movimento, não edita saldo inicial nem
    data-base (app.domain.caixa.validar_edicao_conta)."""

    __tablename__ = "conta_financeira"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    instituicao: Mapped[str | None] = mapped_column(String(120))
    saldo_inicial: Mapped[Decimal] = mapped_column(Dinheiro, default=Decimal("0.00"))
    data_base: Mapped[date] = mapped_column(Date)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class CampoCustom(Base, Timestamped):
    """Campo personalizado por objeto. O valor fica em `<objeto>.campos_custom[slug]`."""

    __tablename__ = "campo_custom"
    __table_args__ = (
        CheckConstraint("tipo IN ('texto', 'numero', 'moeda', 'data', 'sim_nao', 'lista')", name="tipo"),
        CheckConstraint("objeto IN ('empresa', 'pessoa', 'oportunidade')", name="objeto"),
        UniqueConstraint("objeto", "slug", name="uq_campo_custom_objeto_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[str] = mapped_column(String(10))
    objeto: Mapped[str] = mapped_column(String(15))
    opcoes: Mapped[list[str]] = mapped_column(JSON, default=list)  # para tipo "lista"
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    exigido_na_etapa_id: Mapped[int | None] = mapped_column(ForeignKey("etapa.id"))
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    arquivado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
