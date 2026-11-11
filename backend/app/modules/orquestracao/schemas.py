"""Schemas da API /api/orquestracao."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ------------------------------------------------------------------------------------------------ IA


class RegistroIn(BaseModel):
    tipo: str = Field(min_length=1, max_length=30)
    id: int


class PerguntaIn(BaseModel):
    escopo: Literal["registro", "modulo", "tudo"] = "modulo"
    modulo: Literal["comercial", "financeiro", "nucleo"] | None = None
    tela: str | None = Field(default=None, max_length=120)
    registro: RegistroIn | None = None
    pergunta: str = Field(min_length=1, max_length=2000)
    conversa_id: int | None = None


class EvidenciaOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    fonte: str
    trecho: str


class AcaoOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    tipo: str
    rotulo: str
    payload: dict[str, Any] = {}


class RespostaOut(BaseModel):
    """Formato ÚNICO (IA e regras)."""
    titulo: str
    analise: str
    proxima_acao: str = ""
    evidencias: list[EvidenciaOut] = []
    limites: list[str] = []
    acoes_sugeridas: list[AcaoOut] = []
    origem: Literal["ia", "regras"]
    ferramentas: list[str] = []
    ia_ligada: bool = False
    conversa_id: int | None = None
    mensagem_id: int | None = None


class AcaoIn(BaseModel):
    tipo: str = Field(min_length=1, max_length=40)
    payload: dict[str, Any] = {}


class CriarAtividadePayload(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    assunto: str = Field(min_length=1, max_length=200)
    tipo: Literal["tarefa", "email", "ligacao", "whatsapp", "reuniao"] = "tarefa"
    prazo: date | None = None
    oportunidade_id: int | None = None
    empresa_id: int | None = None
    objetivo: str | None = Field(default=None, max_length=4000)
    hora_inicio: str | None = None
    hora_fim: str | None = None


class AcaoExecutadaOut(BaseModel):
    tipo: str
    registro: dict[str, Any]
    mensagem: str


class AnaliseOut(BaseModel):
    comunicacao_id: int
    analise: dict[str, Any]
    analisada_em: datetime | None
    origem: Literal["ia", "regras"]


class EnriquecerIn(BaseModel):
    """Pedido de enriquecimento de um cadastro. `dados` e `texto_apoio` são DADO (nunca instrução)."""

    objeto: Literal["empresa", "fornecedor", "pessoa", "produto", "categoria", "centro_custo", "conta"]
    registro_id: int | None = None
    dados: dict[str, Any] = Field(default_factory=dict, max_length=120)
    instrucao: str = Field(default="", max_length=2000)
    texto_apoio: str | None = Field(default=None, max_length=20000)


class SugestaoOut(BaseModel):
    campo: str
    rotulo: str
    valor_atual: Any = None
    valor_sugerido: Any
    justificativa: str
    fonte: str


class EnriquecerOut(BaseModel):
    sugestoes: list[SugestaoOut]
    evidencias: list[str]
    limites: list[str]
    origem: Literal["ia", "regras"]


class ConversaOut(BaseModel):
    id: int
    escopo: str
    modulo: str | None
    tela: str | None
    titulo: str | None
    criado_em: datetime


# ------------------------------------------------------------------------------------------------ automações
Area = Literal["comercial", "financeiro"]


class AutomacaoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    area: Area
    nome: str = Field(min_length=1, max_length=150)
    gatilho: str = Field(min_length=1, max_length=40)
    funil_id: int | None = None
    etapa_destino_id: int | None = None
    campo: str | None = Field(default=None, max_length=60)
    operador: str | None = Field(default=None, max_length=12)
    valor_esperado: str | None = Field(default=None, max_length=200)
    prazo_dias: int | None = Field(default=None, ge=0, le=365)
    acao: str = Field(min_length=1, max_length=25)
    tipo_atividade: str | None = Field(default=None, max_length=10)
    responsavel_regra: str | None = Field(default=None, max_length=60)
    destinatario: str | None = Field(default=None, max_length=200)
    conteudo: str = Field(min_length=1, max_length=4000)
    revisar_condicoes: bool = True


class AutomacaoPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    gatilho: str | None = Field(default=None, max_length=40)
    funil_id: int | None = None
    etapa_destino_id: int | None = None
    campo: str | None = Field(default=None, max_length=60)
    operador: str | None = Field(default=None, max_length=12)
    valor_esperado: str | None = Field(default=None, max_length=200)
    prazo_dias: int | None = Field(default=None, ge=0, le=365)
    acao: str | None = Field(default=None, max_length=25)
    tipo_atividade: str | None = Field(default=None, max_length=10)
    responsavel_regra: str | None = Field(default=None, max_length=60)
    destinatario: str | None = Field(default=None, max_length=200)
    conteudo: str | None = Field(default=None, max_length=4000)
    revisar_condicoes: bool | None = None


class AutomacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    area: str
    nome: str
    gatilho: str
    gatilho_rotulo: str = ""
    funil_id: int | None
    etapa_destino_id: int | None
    campo: str | None
    operador: str | None
    valor_esperado: str | None
    prazo_dias: int | None
    acao: str
    acao_rotulo: str = ""
    tipo_atividade: str | None
    responsavel_regra: str | None
    destinatario: str | None
    conteudo: str
    revisar_condicoes: bool
    estado: str
    ativada_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime


class ExecucaoOut(BaseModel):
    id: int
    automacao_id: int
    automacao_nome: str
    area: str
    quando: datetime
    registro: str | None
    resultado: str | None
    simulacao: bool
    erro: str | None
    tentativas: int
    detalhe: str | None
    registro_criado: str | None


class TesteOut(BaseModel):
    elegiveis: int
    ja_executadas: int
    amostra: list[str]
    acao: str
    resumo: str
    observacao: str


class AvisoOut(BaseModel):
    id: int
    automacao_nome: str
    texto: str | None
    quando: datetime


# ------------------------------------------------------------------------------------------------ integrações
TipoIntegracao = Literal["google_calendar", "outlook", "email", "whatsapp"]


class IntegracaoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    conta: str | None = Field(default=None, max_length=200)
    escopos: list[str] | None = None
    responsavel_id: int | None = None
    segredo: str | None = Field(default=None, max_length=4000)  # somente escrita; vazio = manter


class IntegracaoOut(BaseModel):
    tipo: str
    nome: str
    grupo: str
    descricao: str
    estado: str
    situacao: str  # desconectado | conectado | erro | aguardando_conector
    situacao_rotulo: str
    conta: str | None
    escopos: list[str]
    escopos_disponiveis: list[str]
    responsavel_id: int | None
    segredo_definido: bool
    segredo_final: str | None
    segredo_rotulo: str | None
    requisitos: list[str]
    fluxos_dependentes: list[str]
    conectado_em: datetime | None
    testado_em: datetime | None
    ultimo_erro: str | None


class MensagemOut(BaseModel):
    mensagem: str


# ------------------------------------------------------------------------------------------------ WhatsApp (Evolution)
class EvolutionIn(BaseModel):
    """PUT /integracoes/whatsapp/evolution. apikey ausente/vazia = mantém a salva (somente escrita)."""

    model_config = ConfigDict(str_strip_whitespace=True)
    url: str = Field(min_length=1, max_length=300)
    apikey: str | None = Field(default=None, max_length=500)
    instancia: str | None = Field(default=None, max_length=100)


class EvolutionOut(BaseModel):
    configurado: bool
    provedor: str | None
    url: str | None
    instancia: str | None
    chave_final: str | None  # "••••••abcd"
    estado: str  # desconectado | conectado | erro
    numero: str | None = None
    testado_em: datetime | None
    ultimo_erro: str | None


class EvolutionBuscarIn(BaseModel):
    """POST …/evolution/instancias: URL/apikey do formulário (vazias = as salvas)."""

    model_config = ConfigDict(str_strip_whitespace=True)
    url: str | None = Field(default=None, max_length=300)
    apikey: str | None = Field(default=None, max_length=500)


class InstanciaEvolutionOut(BaseModel):
    nome: str
    estado: str  # conectado | conectando | desconectado
    numero: str | None


class TesteWhatsAppOut(BaseModel):
    ok: bool
    estado: str
    mensagem: str


class QrCodeOut(BaseModel):
    base64: str | None  # "data:image/png;base64,…" como a Evolution devolve
    codigo_pareamento: str | None
    estado: str  # conectando | conectado
    mensagem: str
