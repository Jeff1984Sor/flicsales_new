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

from datetime import date, datetime
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
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamped, UtcDateTime
from app.domain import contatos
from app.domain.cadastro import PAPEIS_EMPRESA, chave_de_nome
from app.modules.base import Dinheiro


class EnderecoMixin:
    """Endereço estruturado (migração 0003). CEP "00000-000", UF em sigla. O antigo `empresa.endereco` (texto livre)
    continua existindo; as telas novas usam estes campos (app.domain.cadastro.CAMPOS_ENDERECO)."""

    cep: Mapped[str | None] = mapped_column(String(9))
    logradouro: Mapped[str | None] = mapped_column(String(200))
    numero: Mapped[str | None] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2))


class Empresa(EnderecoMixin, Base, Timestamped):
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
    # dados da Receita (migração 0004): gravados só por POST /empresas/{id}/cnpj/aplicar (sempre sobrescreve);
    # não são editáveis pelo formulário, pela planilha nem pela IA
    cnae_principal: Mapped[str | None] = mapped_column(String(300))
    cnaes_secundarios: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    natureza_juridica: Mapped[str | None] = mapped_column(String(200))
    capital_social: Mapped[Decimal | None] = mapped_column(Dinheiro)
    situacao_cadastral: Mapped[str | None] = mapped_column(String(40))
    data_abertura: Mapped[date | None] = mapped_column(Date)
    receita_consultada_em: Mapped[datetime | None] = mapped_column(UtcDateTime())

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


class Pessoa(EnderecoMixin, Base, Timestamped):
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
    # ligada: o endereço da pessoa acompanha o da empresa (app.domain.cadastro.resolver_endereco_pessoa/propagar_endereco)
    usa_endereco_da_empresa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # LGPD (migração 0005): app.domain.cadastro.BASES_LEGAIS / PERMISSOES_COMUNICACAO ("opt_out" é exclusivo)
    base_legal: Mapped[str | None] = mapped_column(String(30))
    permissoes_comunicacao: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    # vários contatos (migração 0006): app.domain.contatos. `email`/`telefone` acima ESPELHAM o principal.
    telefones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, server_default="[]")
    emails: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, server_default="[]")


def _mudou(alvo: Any, atributo: str, inserindo: bool) -> bool:
    if inserindo:
        return bool(getattr(alvo, atributo))
    return sa_inspect(alvo).attrs[atributo].history.has_changes()


@event.listens_for(Pessoa, "before_insert")
@event.listens_for(Pessoa, "before_update")
def _espelhar_principal(_mapper, _conn, alvo: Pessoa) -> None:
    """Mantém `email`/`telefone` = principal das listas, em qualquer caminho de gravação (rota, planilha, fornecedor,
    comercial). Mudou a lista → o espelho acompanha; mudou só o campo antigo → ele vira o principal da lista."""
    inserindo = alvo.id is None
    for lista, simples, chave, tipo in (("emails", "email", "email", "comercial"),
                                         ("telefones", "telefone", "numero", "celular")):
        if _mudou(alvo, lista, inserindo):
            setattr(alvo, simples, contatos.principal_de(getattr(alvo, lista), chave))
        elif _mudou(alvo, simples, inserindo) or (getattr(alvo, simples) and not getattr(alvo, lista)):
            setattr(alvo, lista, contatos.aplicar_principal(getattr(alvo, lista), getattr(alvo, simples), chave,
                                                            tipo_padrao=tipo))


class Produto(Base, Timestamped):
    __tablename__ = "produto"
    __table_args__ = (
        CheckConstraint("tipo IN ('servico', 'produto')", name="tipo"),
        CheckConstraint("desconto_tipo IN ('percentual', 'valor')", name="desconto_tipo"),
        CheckConstraint("frequencia IN ('diaria', 'semanal', 'mensal', 'semestral', 'anual')", name="frequencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True)
    tipo: Mapped[str] = mapped_column(String(10))  # servico | produto
    codigo: Mapped[str | None] = mapped_column(String(50), unique=True)
    unidade: Mapped[str | None] = mapped_column(String(30))
    preco_referencia: Mapped[Decimal | None] = mapped_column(Dinheiro)
    recorrente: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # migração 0006 (app.domain.produto): desconto padrão e recorrência
    desconto_tipo: Mapped[str | None] = mapped_column(String(10))  # percentual | valor
    desconto_valor: Mapped[Decimal | None] = mapped_column(Dinheiro)
    frequencia: Mapped[str | None] = mapped_column(String(10))  # diaria | semanal | mensal | semestral | anual
    intervalo: Mapped[int | None] = mapped_column(Integer)  # a cada N (semestral = 1)
    dias_semana: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")  # seg…dom (semanal)
    campos_custom: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")


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
        CheckConstraint("tipo IN ('texto', 'numero', 'moeda', 'data', 'sim_nao', 'lista', 'multipla', 'link')",
                        name="tipo"),
        CheckConstraint("objeto IN ('empresa', 'pessoa', 'oportunidade', 'produto')", name="objeto"),
        UniqueConstraint("objeto", "slug", name="uq_campo_custom_objeto_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[str] = mapped_column(String(10))
    objeto: Mapped[str] = mapped_column(String(15))
    opcoes: Mapped[list[str]] = mapped_column(JSON, default=list)  # para tipos "lista" e "multipla"
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    exigido_na_etapa_id: Mapped[int | None] = mapped_column(ForeignKey("etapa.id"))
    # exibir na etapa (migração 0006, app.domain.campos_exibicao): null = sempre
    exibir_funil_id: Mapped[int | None] = mapped_column(ForeignKey("funil.id"))
    exibir_etapa_id: Mapped[int | None] = mapped_column(ForeignKey("etapa.id"))
    visivel: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")  # preferência (migração 0006)
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    arquivado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class CampoPadraoConfig(Base, Timestamped):
    """Obrigatoriedade/visibilidade configurada de um campo padrão (catálogo em app.domain.campos_padrao). Sem linha
    = vale o padrão do catálogo."""

    __tablename__ = "campo_padrao_config"
    __table_args__ = (
        CheckConstraint("objeto IN ('empresa', 'pessoa', 'oportunidade', 'produto')", name="objeto"),
        UniqueConstraint("objeto", "campo", name="uq_campo_padrao_config_objeto_campo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    objeto: Mapped[str] = mapped_column(String(15))
    campo: Mapped[str] = mapped_column(String(60))
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    visivel: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class OpcaoLista(Base, Timestamped):
    """Opções da Governança de ajustes (segmento e porte da empresa, motivo de perda). Nada se exclui: inativa."""

    __tablename__ = "opcao_lista"
    __table_args__ = (
        CheckConstraint("tipo IN ('segmento', 'porte', 'motivo_perda')", name="tipo"),
        UniqueConstraint("tipo", "nome", name="uq_opcao_lista_tipo_nome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(15))
    nome: Mapped[str] = mapped_column(String(120))
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class EmpresaSocio(Base, Timestamped):
    """Quadro societário vindo da consulta pública do CNPJ (substituído inteiro a cada "aplicar CNPJ", com auditoria
    antes→depois). CPF do sócio vem mascarado da Receita: guardado como veio."""

    __tablename__ = "empresa_socio"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    qualificacao: Mapped[str | None] = mapped_column(String(120))
    documento: Mapped[str | None] = mapped_column(String(18))
    data_entrada: Mapped[date | None] = mapped_column(Date)
    faixa_etaria: Mapped[str | None] = mapped_column(String(40))


class EmpresaAnexo(Base, Timestamped):
    """Arquivo anexado à empresa (comprovante de consulta CNPJ, contrato…). Arquivo em `app/core/storage.py`
    (categoria "empresas_anexos"); nunca apagado: arquivar = `ativo` false."""

    __tablename__ = "empresa_anexo"
    __table_args__ = (CheckConstraint("tipo IN ('cartao_cnpj', 'contrato', 'documento', 'outro')", name="tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(30))
    mime: Mapped[str | None] = mapped_column(String(100))
    tamanho: Mapped[int] = mapped_column(Integer, default=0)
    caminho: Mapped[str] = mapped_column(String(300))
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
