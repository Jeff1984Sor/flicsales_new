"""Schemas da API do Comercial (/api/comercial). Dinheiro como Decimal (sai como string no JSON); datas-de-dia `date`."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.schemas import Schema

Texto = str | None


# ------------------------------------------------------------------------------------------------ funis e etapas
class EtapaOut(Schema):
    id: int
    funil_id: int
    nome: str
    ordem: int
    probabilidade: int
    limite_dias: int | None
    criterios: str | None


class FunilOut(Schema):
    id: int
    nome: str
    ativo: bool
    etapas: list[EtapaOut] = []


class FunilCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    etapas: list[str]


class FunilAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    ativo: bool | None = None


class EtapaConfig(BaseModel):
    id: int | None = None
    nome: str = Field(min_length=1, max_length=80)
    probabilidade: int
    limite_dias: int | None = None
    criterios: Texto = None


class EtapasConfig(BaseModel):
    etapas: list[EtapaConfig]


# ------------------------------------------------------------------------------------------------ oportunidades
class OportunidadeBase(BaseModel):
    contato_id: int | None = None
    valor_unico: Decimal | None = None
    valor_recorrente_mensal: Decimal | None = None
    previsao_fechamento: date | None = None
    proxima_acao: str | None = Field(default=None, max_length=300)
    proxima_acao_prazo: date | None = None
    origem: str | None = Field(default=None, max_length=100)
    necessidade: Texto = None
    decisor: str | None = Field(default=None, max_length=200)
    orcamento_concorrencia: Texto = None
    criterio_sucesso: Texto = None
    interesse: str | None = Field(default=None, max_length=40)
    campos_custom: dict[str, Any] | None = None


class OportunidadeCriar(OportunidadeBase):
    titulo: str = Field(min_length=1, max_length=200)
    funil_id: int
    empresa_id: int | None = None
    empresa_nome: str | None = Field(default=None, max_length=200)
    responsavel_id: int | None = None


class OportunidadeAtualizar(OportunidadeBase):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    funil_id: int | None = None
    etapa_id: int | None = None
    empresa_id: int | None = None
    empresa_nome: str | None = Field(default=None, max_length=200)
    responsavel_id: int | None = None


class OportunidadeOut(Schema):
    id: int
    titulo: str
    funil_id: int
    funil_nome: str | None = None
    etapa_id: int | None
    etapa_nome: str | None = None
    etapa_probabilidade: int | None = None
    resultado: str
    empresa_id: int | None
    empresa_nome: str | None = None
    contato_id: int | None
    contato_nome: str | None = None
    responsavel_id: int
    responsavel_nome: str | None = None
    valor_unico: Decimal
    valor_recorrente_mensal: Decimal
    previsao_fechamento: date | None
    proxima_acao: str | None
    proxima_acao_prazo: date | None
    origem: str | None
    necessidade: str | None
    decisor: str | None
    orcamento_concorrencia: str | None
    criterio_sucesso: str | None
    motivo_perda: str | None
    concorrente: str | None
    data_retomada: date | None
    ganha_em: date | None
    perdida_em: date | None
    entrou_etapa_em: date | None
    dias_na_etapa: int = 0
    alem_do_limite: bool = False
    interesse: str | None = None
    campos_custom: dict[str, Any] = {}
    criado_em: datetime


class EventoOut(Schema):
    id: int
    quando: datetime
    tipo: str
    texto: str
    usuario_id: int | None
    usuario_nome: str | None = None


class ContextoNegociacao(BaseModel):
    texto: str
    fonte: str | None = None
    limite: str


class RecebivelOut(Schema):
    id: int
    descricao: str
    valor_original: Decimal
    saldo: Decimal
    vencimento: date
    status: str
    parcela: int | None
    parcelas_total: int | None


class OportunidadeDetalhe(OportunidadeOut):
    contexto: ContextoNegociacao
    recebiveis: list[RecebivelOut] = []  # vazio para quem não tem financeiro.titulos.ver
    recebiveis_preparados: int = 0  # quantidade (sem valores) — visível a quem vê a oportunidade
    atividades_pendentes: int = 0
    comunicacoes: int = 0
    propostas: int = 0


class MoverIn(BaseModel):
    etapa_id: int


class GanharIn(BaseModel):
    empresa_id: int | None = None
    empresa_nome: str | None = Field(default=None, max_length=200)
    valor: Decimal
    condicao: str | int = "Parcela única"
    primeiro_vencimento: date | None = None


class GanhoOut(BaseModel):
    oportunidade: OportunidadeOut
    recebiveis: list[RecebivelOut]
    mensagem: str


class PerderIn(BaseModel):
    motivo: str | None = Field(default=None, max_length=2000)
    concorrente: str | None = Field(default=None, max_length=200)
    data_retomada: date | None = None


class NotaIn(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


class OpcaoSimples(BaseModel):
    id: int
    nome: str


class OpcaoPessoa(OpcaoSimples):
    empresa_id: int | None = None


class OpcaoProduto(OpcaoSimples):
    preco_referencia: Decimal | None = None
    recorrente: bool = False


class OpcaoOportunidade(OpcaoSimples):
    empresa_id: int | None = None
    resultado: str


class OpcaoCampo(BaseModel):
    id: int
    nome: str
    slug: str
    tipo: str
    objeto: str
    opcoes: list[str] = []


class OpcoesComerciais(BaseModel):
    empresas: list[OpcaoSimples]
    pessoas: list[OpcaoPessoa]
    produtos: list[OpcaoProduto]
    oportunidades: list[OpcaoOportunidade]
    funis: list[FunilOut]
    campos: list[OpcaoCampo]
    condicoes_ganho: list[str]
    interesse: list[str]


# ------------------------------------------------------------------------------------------------ atividades
TipoAtividade = Literal["tarefa", "email", "ligacao", "whatsapp", "reuniao"]


class AtividadeCriar(BaseModel):
    assunto: str = Field(min_length=1, max_length=200)
    tipo: TipoAtividade
    responsavel_id: int | None = None
    empresa_id: int | None = None
    oportunidade_id: int | None = None
    prazo: date
    hora_inicio: time | None = None
    hora_fim: time | None = None
    fuso: str | None = Field(default=None, max_length=40)
    participantes: Texto = None
    canal: str | None = Field(default=None, max_length=300)
    objetivo: Texto = None
    resultado: Texto = None
    origem: Literal["manual", "ia", "automacao"] = "manual"


class AtividadeAtualizar(BaseModel):
    assunto: str | None = Field(default=None, min_length=1, max_length=200)
    tipo: TipoAtividade | None = None
    responsavel_id: int | None = None
    empresa_id: int | None = None
    oportunidade_id: int | None = None
    prazo: date | None = None
    hora_inicio: time | None = None
    hora_fim: time | None = None
    fuso: str | None = Field(default=None, max_length=40)
    participantes: Texto = None
    canal: str | None = Field(default=None, max_length=300)
    objetivo: Texto = None
    resultado: Texto = None


class ConcluirIn(BaseModel):
    resultado: Texto = None


class AtividadeOut(Schema):
    id: int
    assunto: str
    tipo: str
    responsavel_id: int
    responsavel_nome: str | None = None
    empresa_id: int | None
    empresa_nome: str | None = None
    oportunidade_id: int | None
    oportunidade_titulo: str | None = None
    prazo: date
    hora_inicio: time | None
    hora_fim: time | None
    fuso: str
    participantes: str | None
    canal: str | None
    objetivo: str | None
    resultado: str | None
    status: str
    concluida_em: datetime | None
    origem: str
    atrasada: bool = False


# ------------------------------------------------------------------------------------------------ comunicações
class ComunicacaoCriar(BaseModel):
    canal: Literal["reuniao", "email", "whatsapp", "notas"]
    titulo: str | None = Field(default=None, max_length=200)
    conteudo: str = Field(min_length=1, max_length=50000)
    data: date | None = None
    empresa_id: int | None = None
    oportunidade_id: int | None = None


class AnaliseIn(BaseModel):
    analise: dict[str, Any]


class ComunicacaoOut(Schema):
    id: int
    canal: str
    titulo: str | None
    conteudo: str
    data: date | None
    empresa_id: int | None
    empresa_nome: str | None = None
    oportunidade_id: int | None
    oportunidade_titulo: str | None = None
    analise: dict[str, Any] | None
    analisada_em: datetime | None
    criado_em: datetime


class RascunhoOut(BaseModel):
    rascunho: str
    aviso: str


# ------------------------------------------------------------------------------------------------ propostas
StatusProposta = Literal["rascunho", "em_aprovacao", "aprovada_internamente", "enviada", "aceita", "recusada"]


class PropostaCriar(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    oportunidade_id: int
    empresa_id: int | None = None
    versao: int | None = Field(default=None, ge=1)
    escopo: str = Field(min_length=1)
    produto_id: int | None = None
    quantidade: Decimal
    preco_unitario: Decimal
    desconto_pct: Decimal | None = Decimal("0")
    mensalidade_adicional: Decimal | None = Decimal("0")
    validade: date
    condicao: str = Field(min_length=1, max_length=40)
    responsavel_id: int | None = None
    status: StatusProposta = "rascunho"
    justificativa_desconto: Texto = None


class PropostaAtualizar(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    escopo: str | None = Field(default=None, min_length=1)
    produto_id: int | None = None
    quantidade: Decimal | None = None
    preco_unitario: Decimal | None = None
    desconto_pct: Decimal | None = None
    mensalidade_adicional: Decimal | None = None
    validade: date | None = None
    condicao: str | None = Field(default=None, min_length=1, max_length=40)
    responsavel_id: int | None = None
    status: StatusProposta | None = None
    justificativa_desconto: Texto = None


class PropostaOut(Schema):
    id: int
    titulo: str
    oportunidade_id: int
    oportunidade_titulo: str | None = None
    empresa_id: int
    empresa_nome: str | None = None
    versao: int
    escopo: str
    produto_id: int | None
    produto_nome: str | None = None
    quantidade: Decimal
    preco_unitario: Decimal
    desconto_pct: Decimal
    mensalidade_adicional: Decimal
    validade: date
    condicao: str
    responsavel_id: int
    responsavel_nome: str | None = None
    status: str
    justificativa_desconto: str | None
    total: Decimal
    criado_em: datetime


# ------------------------------------------------------------------------------------------------ metas e forecast
IndicadorMeta = Literal["receita_unica_ganha", "mrr_novo", "vendas_ganhas", "atividades_concluidas"]


class MetaCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    responsavel_tipo: Literal["pessoa", "equipe"] = "pessoa"
    responsavel_id: int | None = None
    equipe: str | None = Field(default=None, max_length=120)
    inicio: date
    fim: date
    indicador: IndicadorMeta
    alvo: Decimal
    funil_id: int | None = None


class MetaAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    responsavel_tipo: Literal["pessoa", "equipe"] | None = None
    responsavel_id: int | None = None
    equipe: str | None = Field(default=None, max_length=120)
    inicio: date | None = None
    fim: date | None = None
    indicador: IndicadorMeta | None = None
    alvo: Decimal | None = None
    funil_id: int | None = None


class MetaOut(Schema):
    id: int
    nome: str
    responsavel_tipo: str
    responsavel_id: int | None
    responsavel_nome: str | None = None
    equipe: str | None
    inicio: date
    fim: date
    indicador: str
    alvo: Decimal
    funil_id: int | None
    funil_nome: str | None = None
    realizado: Decimal = Decimal("0")
    percentual: Decimal | None = None
    formula: str = ""


class ForecastOut(BaseModel):
    pipeline_aberto: Decimal
    ponderado: Decimal
    mrr_potencial: Decimal
    sem_previsao: int
    abertas: int
    por_etapa: list[dict[str, Any]]
    formulas: dict[str, str]
    limite: str


# ------------------------------------------------------------------------------------------------ desempenho
class IndicadorCalculado(BaseModel):
    valor: Decimal | None
    detalhe: str
    formula: str


class VendedorDesempenho(BaseModel):
    usuario_id: int
    nome: str
    ganhas: int
    perdidas: int
    encerradas: int
    conversao: Decimal | None
    receita: Decimal
    sem_proxima_acao: int


class DesempenhoOut(BaseModel):
    inicio: date
    fim: date
    encerradas: int
    conversao: IndicadorCalculado
    receita_ganha: IndicadorCalculado
    ticket_medio: IndicadorCalculado
    ciclo_mediano: IndicadorCalculado
    vendedores: list[VendedorDesempenho]
    limites: list[str]


class EvidenciasOut(BaseModel):
    usuario_id: int
    nome: str
    inicio: date
    fim: date
    ganhas: list[OportunidadeOut]
    perdidas: list[OportunidadeOut]
    sem_proxima_acao: list[OportunidadeOut]
    alem_do_limite: list[OportunidadeOut]
    atividades_atrasadas: list[AtividadeOut]
    gargalo: str
    acao_sugerida: str
    limites: list[str]


# ------------------------------------------------------------------------------------------------ dashboards e indicadores
class IndicadorConfigCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    objeto: Literal["oportunidade"] = "oportunidade"
    metrica: Literal["soma_valor_unico", "quantidade"]
    filtro_campo_id: int | None = None
    filtro_valor: str | None = Field(default=None, max_length=200)


class IndicadorConfigAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    metrica: Literal["soma_valor_unico", "quantidade"] | None = None
    filtro_campo_id: int | None = None
    filtro_valor: str | None = Field(default=None, max_length=200)
    ativo: bool | None = None


class PreviaIndicador(BaseModel):
    valor: Decimal
    quantidade: int
    descricao: str
    formula: str


class IndicadorConfigOut(Schema):
    id: int
    nome: str
    objeto: str
    metrica: str
    filtro_campo_id: int | None
    filtro_campo_nome: str | None = None
    filtro_valor: str | None
    ativo: bool
    resultado: PreviaIndicador | None = None


class DashboardOut(BaseModel):
    pipeline_alto_interesse: Decimal
    oportunidades: int
    recebiveis: int
    proximas_acoes: int
    funil_id: int | None
    pipeline_por_etapa: list[dict[str, Any]]
    indicadores: list[IndicadorConfigOut]


# ------------------------------------------------------------------------------------------------ playbooks e modelos
class PlaybookCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    funil_id: int | None = None
    etapa_id: int | None = None
    objetivo: str = Field(min_length=1)
    perguntas_discovery: Texto = None
    criterios_avanco: str = Field(min_length=1)
    objecoes: Texto = None
    proxima_acao_padrao: Texto = None
    responsavel_id: int | None = None


class PlaybookAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    funil_id: int | None = None
    etapa_id: int | None = None
    objetivo: str | None = Field(default=None, min_length=1)
    perguntas_discovery: Texto = None
    criterios_avanco: str | None = Field(default=None, min_length=1)
    objecoes: Texto = None
    proxima_acao_padrao: Texto = None
    responsavel_id: int | None = None
    ativo: bool | None = None


class PlaybookOut(Schema):
    id: int
    nome: str
    funil_id: int | None
    funil_nome: str | None = None
    etapa_id: int | None
    etapa_nome: str | None = None
    objetivo: str
    perguntas_discovery: str | None
    criterios_avanco: str
    objecoes: str | None
    proxima_acao_padrao: str | None
    responsavel_id: int | None
    responsavel_nome: str | None = None
    ativo: bool


class ModeloCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    canal: Literal["email", "whatsapp", "ligacao", "reuniao"]
    finalidade: Literal["prospeccao", "follow_up", "proposta", "cobranca", "renovacao"]
    assunto: str | None = Field(default=None, max_length=200)
    conteudo: str = Field(min_length=1)
    status: Literal["rascunho", "revisado"] = "rascunho"


class ModeloAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    canal: Literal["email", "whatsapp", "ligacao", "reuniao"] | None = None
    finalidade: Literal["prospeccao", "follow_up", "proposta", "cobranca", "renovacao"] | None = None
    assunto: str | None = Field(default=None, max_length=200)
    conteudo: str | None = Field(default=None, min_length=1)
    status: Literal["rascunho", "revisado"] | None = None
    ativo: bool | None = None


class ModeloOut(Schema):
    id: int
    nome: str
    canal: str
    finalidade: str
    assunto: str | None
    conteudo: str
    status: str
    ativo: bool
    variaveis: list[str] = []


class PreviaModeloIn(BaseModel):
    oportunidade_id: int | None = None


class PreviaModeloOut(BaseModel):
    assunto: str | None
    conteudo: str
    faltando: list[str]
    aviso: str


# ------------------------------------------------------------------------------------------------ hoje
class HojeOut(BaseModel):
    nome: str
    hoje: date
    pipeline_aberto: Decimal
    oportunidades_ativas: int
    em_negociacao: Decimal
    em_negociacao_qtd: int
    em_negociacao_etapa: str | None
    tarefas_do_dia: int
    recebiveis_vinculados: int
    atencao: list[AtividadeOut]
    agenda: list[AtividadeOut]
    agenda_conectada: bool
    saude_funil: list[dict[str, Any]]
    funil_nome: str | None
    leitura: dict[str, Any]
    ia_ligada: bool


class PreviaIndicadorIn(BaseModel):
    metrica: Literal["soma_valor_unico", "quantidade"]
    filtro_campo_id: int | None = None
    filtro_valor: str | None = Field(default=None, max_length=200)
