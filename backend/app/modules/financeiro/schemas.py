"""Schemas da API do Financeiro (`/api/financeiro`). Dinheiro sai como string decimal ("1234.50")."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_validator

from app.core.schemas import Schema

Direcao = Literal["receber", "pagar"]
Forma = Literal["pix", "boleto", "transferencia", "cartao", "dinheiro", "outra"]
Frequencia = Literal["mensal", "trimestral", "anual"]
SituacaoRecorrencia = Literal["ativa", "pausada", "cancelada"]
SituacaoCobranca = Literal["em_acompanhamento", "promessa_pagamento", "em_contestacao", "resolvida"]
Canal = Literal["email", "ligacao", "whatsapp"]
COMPETENCIA_RE = r"^\d{4}-(0[1-9]|1[0-2])$"


def _texto_limpo(v: Any) -> Any:
    """Antes da validação: espaços nas pontas saem; texto vazio vira None (obrigatório vazio → 422)."""
    if not isinstance(v, str):
        return v
    v = v.strip()
    return v or None


# ---------------------------------------------------------------- títulos
class TituloIn(Schema):
    direcao: Direcao
    empresa_id: int
    descricao: str = Field(min_length=1, max_length=300)
    documento: str | None = Field(None, max_length=60)
    emissao: date | None = None
    competencia: str | None = Field(None, pattern=COMPETENCIA_RE)
    vencimento: date
    valor_original: Decimal
    categoria_id: int | None = None
    centro_custo_id: int | None = None
    conta_prevista_id: int | None = None
    forma: Forma | None = None
    responsavel_id: int
    observacoes: str | None = None
    aprovacao: Literal["pendente", "aprovado"] | None = None  # só a pagar; "aprovado" exige alçada
    rascunho: bool = False  # lançamento manual nasce aberto; rascunho é opcional

    _limpar = field_validator("descricao", "documento", "observacoes", mode="before")(_texto_limpo)


class TituloAtualizar(Schema):
    empresa_id: int | None = None
    descricao: str | None = Field(None, min_length=1, max_length=300)
    documento: str | None = Field(None, max_length=60)
    emissao: date | None = None
    competencia: str | None = Field(None, pattern=COMPETENCIA_RE)
    vencimento: date | None = None
    valor_original: Decimal | None = None
    categoria_id: int | None = None
    centro_custo_id: int | None = None
    conta_prevista_id: int | None = None
    forma: Forma | None = None
    responsavel_id: int | None = None
    observacoes: str | None = None
    aprovacao: Literal["pendente", "aprovado"] | None = None

    _limpar = field_validator("descricao", "documento", "observacoes", mode="before")(_texto_limpo)


class MotivoIn(Schema):
    motivo: str = Field(min_length=1, max_length=2000)


class TituloOut(Schema):
    id: int
    direcao: str
    empresa_id: int
    empresa_nome: str
    descricao: str
    documento: str | None
    emissao: date | None
    competencia: str | None
    vencimento: date
    valor_original: Decimal
    saldo: Decimal
    categoria_id: int | None
    categoria_nome: str | None
    centro_custo_id: int | None
    centro_custo_nome: str | None
    conta_prevista_id: int | None
    conta_prevista_nome: str | None
    forma: str | None
    responsavel_id: int
    responsavel_nome: str | None
    observacoes: str | None
    status: str
    estado: str  # o que a tela mostra ("vencido" é derivado)
    dias_atraso: int
    aprovacao: str | None
    aprovado_por_nome: str | None
    aprovado_em: datetime | None
    motivo_cancelamento: str | None
    cancelado_em: datetime | None
    confirmado_em: datetime | None
    origem_oportunidade_id: int | None
    origem_recorrencia_id: int | None
    parcela: int | None
    parcelas_total: int | None
    tem_baixa_ativa: bool
    em_contestacao: bool
    criado_em: datetime | None


class OrigemOut(Schema):
    tipo: Literal["oportunidade", "recorrencia", "manual"]
    id: int | None
    rotulo: str


class BaixaOut(Schema):
    id: int
    titulo_id: int
    direcao: str
    empresa_nome: str
    titulo_descricao: str
    valor: Decimal
    data: date
    conta_id: int
    conta_nome: str
    forma: str
    referencia_comprovante: str | None
    observacao: str | None
    registrada_por_nome: str | None
    estornada: bool
    estorno_motivo: str | None
    estornada_em: datetime | None
    estornada_por_nome: str | None
    criado_em: datetime | None


class CobrancaOut(Schema):
    id: int
    assunto: str
    titulo_id: int
    titulo_descricao: str
    empresa_nome: str
    titulo_saldo: Decimal
    titulo_estado: str
    responsavel_id: int
    responsavel_nome: str | None
    canal: str
    situacao: str
    data_prometida: date | None
    valor_prometido: Decimal | None
    proximo_contato: date | None
    historico: str
    criado_em: datetime | None


class TituloDetalhe(TituloOut):
    origem: OrigemOut
    baixas: list[BaixaOut]
    cobrancas: list[CobrancaOut]


class Opcao(Schema):
    id: int
    nome: str


class OpcaoEmpresa(Opcao):
    cliente: bool
    fornecedor: bool


class OpcaoConta(Opcao):
    data_base: date


class OpcaoCategoria(Opcao):
    natureza: str


class OpcoesFinanceiro(Schema):
    empresas: list[OpcaoEmpresa]
    categorias: list[OpcaoCategoria]
    centros_custo: list[Opcao]
    contas: list[OpcaoConta]


# ---------------------------------------------------------------- baixas
class BaixaIn(Schema):
    valor: Decimal
    data: date
    conta_id: int
    forma: Forma
    referencia_comprovante: str | None = Field(None, max_length=200)
    observacao: str | None = None

    _limpar = field_validator("referencia_comprovante", "observacao", mode="before")(_texto_limpo)


# ---------------------------------------------------------------- transferências
class TransferenciaIn(Schema):
    conta_origem_id: int
    conta_destino_id: int
    valor: Decimal
    data: date
    descricao: str | None = Field(None, max_length=300)

    _limpar = field_validator("descricao", mode="before")(_texto_limpo)


class TransferenciaOut(Schema):
    id: int
    conta_origem_id: int
    conta_origem_nome: str
    conta_destino_id: int
    conta_destino_nome: str
    valor: Decimal
    data: date
    descricao: str | None
    criado_em: datetime | None


# ---------------------------------------------------------------- recorrências
class RecorrenciaIn(Schema):
    descricao: str = Field(min_length=1, max_length=300)
    direcao: Direcao
    empresa_id: int
    valor_ciclo: Decimal
    frequencia: Frequencia
    inicio: date
    fim: date
    dia_vencimento: int
    categoria_id: int | None = None
    centro_custo_id: int | None = None
    responsavel_id: int | None = None
    situacao: SituacaoRecorrencia = "ativa"

    _limpar = field_validator("descricao", mode="before")(_texto_limpo)


class RecorrenciaAtualizar(Schema):
    descricao: str | None = Field(None, min_length=1, max_length=300)
    direcao: Direcao | None = None
    empresa_id: int | None = None
    valor_ciclo: Decimal | None = None
    frequencia: Frequencia | None = None
    inicio: date | None = None
    fim: date | None = None
    dia_vencimento: int | None = None
    categoria_id: int | None = None
    centro_custo_id: int | None = None
    responsavel_id: int | None = None
    situacao: SituacaoRecorrencia | None = None

    _limpar = field_validator("descricao", mode="before")(_texto_limpo)


class RecorrenciaOut(Schema):
    id: int
    descricao: str
    direcao: str
    empresa_id: int
    empresa_nome: str
    valor_ciclo: Decimal
    frequencia: str
    inicio: date
    fim: date
    dia_vencimento: int
    categoria_id: int | None
    categoria_nome: str | None
    centro_custo_id: int | None
    centro_custo_nome: str | None
    responsavel_id: int | None
    situacao: str
    competencias_geradas: list[str]
    proxima_competencia: str | None
    criado_em: datetime | None


class GerarCompetenciaIn(Schema):
    competencia: str = Field(pattern=COMPETENCIA_RE)


# ---------------------------------------------------------------- cobranças
class CobrancaIn(Schema):
    assunto: str = Field(min_length=1, max_length=200)
    titulo_id: int
    responsavel_id: int
    canal: Canal
    situacao: SituacaoCobranca = "em_acompanhamento"
    data_prometida: date | None = None
    valor_prometido: Decimal | None = None
    proximo_contato: date | None = None
    historico: str = Field(min_length=1)

    _limpar = field_validator("assunto", "historico", mode="before")(_texto_limpo)


class CobrancaAtualizar(Schema):
    assunto: str | None = Field(None, min_length=1, max_length=200)
    responsavel_id: int | None = None
    canal: Canal | None = None
    situacao: SituacaoCobranca | None = None
    data_prometida: date | None = None
    valor_prometido: Decimal | None = None
    proximo_contato: date | None = None
    historico: str | None = None

    _limpar = field_validator("assunto", "historico", mode="before")(_texto_limpo)


class ContestadosOut(Schema):
    titulo_ids: list[int]


# ---------------------------------------------------------------- caixa, dashboards, hoje
class ContaSaldo(Schema):
    id: int
    nome: str
    instituicao: str | None
    saldo_inicial: Decimal
    data_base: date
    saldo_atual: Decimal
    ativo: bool


class Indicador(Schema):
    valor: Decimal
    detalhe: str
    formula: str


class CaixaOut(Schema):
    saldo_gerencial: Indicador
    entradas_abertas: Indicador
    saidas_abertas: Indicador
    saldo_apos_titulos: Indicador
    contas: list[ContaSaldo]
    limites: list[str]


class FaixaAgingOut(Schema):
    faixa: str
    rotulo: str
    valor: Decimal
    quantidade: int


class DashboardsOut(Schema):
    caixa: CaixaOut
    aging_receber: list[FaixaAgingOut]
    aging_pagar: list[FaixaAgingOut]
    hoje: date
    limites: list[str]


class FilaCobranca(Schema):
    titulo_id: int
    empresa_nome: str
    descricao: str
    saldo: Decimal
    vencimento: date
    dias_atraso: int
    em_contestacao: bool


class HojeOut(Schema):
    hoje: date
    saldo_gerencial: Indicador | None  # None = perfil sem financeiro.caixa.ver (a tela esconde o KPI)
    recebiveis_vencidos: Indicador
    recebiveis_vencidos_qtd: int
    aprovacoes_pendentes: int | None  # None = perfil não vê contas a pagar
    recorrencias_ativas: int | None  # None = perfil sem financeiro.recorrencias.ver
    fila_cobranca: list[FilaCobranca]
    leitura: dict[str, Any]
    ia_ligada: bool
    limites: list[str]
