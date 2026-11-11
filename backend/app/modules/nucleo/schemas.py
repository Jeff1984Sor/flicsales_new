"""Schemas da API do Núcleo (`/api/nucleo`). Padrão: `<X>Criar`, `<X>Atualizar` (tudo opcional, a rota grava só o
enviado — `model_dump(exclude_unset=True)`) e `<X>Saida`. Texto vazio ("") vira None antes da validação."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Papel = Literal["prospect", "cliente", "fornecedor", "parceiro"]
Canal = Literal["email", "ligacao", "whatsapp"]
TipoProduto = Literal["servico", "produto"]
Natureza = Literal["receita", "despesa"]
TipoCampo = Literal["texto", "numero", "moeda", "data", "sim_nao", "lista"]
ObjetoCampo = Literal["empresa", "pessoa", "oportunidade"]


class Entrada(BaseModel):
    """Base dos corpos de entrada: "" → None (campo vazio do formulário não grava texto vazio)."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _vazio_vira_none(cls, dados: Any) -> Any:
        if isinstance(dados, dict):
            # campo obrigatório mantém o texto (a regra devolve "Informe o nome…" em vez de um erro de tipo)
            obrigatorios = {k for k, f in cls.model_fields.items() if f.is_required()}
            return {k: (None if isinstance(v, str) and not v.strip() and k not in obrigatorios else v)
                    for k, v in dados.items()}
        return dados


class Saida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------------------------------------- endereço
class _EnderecoCampos(Entrada):
    """Endereço estruturado (CEP "00000-000" ou só dígitos; UF em sigla). Normalizado em app.domain.cadastro."""

    cep: str | None = Field(default=None, max_length=9)
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    cidade: str | None = Field(default=None, max_length=100)
    uf: str | None = Field(default=None, max_length=2)


class _ReceitaSaida(BaseModel):
    """Dados da Receita Federal (migração 0004). Somente leitura: gravados por POST /empresas/{id}/cnpj/aplicar."""

    cnae_principal: str | None = None
    cnaes_secundarios: list[str] = []
    natureza_juridica: str | None = None
    capital_social: Decimal | None = None
    situacao_cadastral: str | None = None
    data_abertura: date | None = None
    receita_consultada_em: datetime | None = None


class _EnderecoSaida(BaseModel):
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    uf: str | None = None


# ------------------------------------------------------------------------------------------------- empresa
class _EmpresaCampos(_EnderecoCampos):
    documento: str | None = Field(default=None, max_length=18)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    segmento: str | None = Field(default=None, max_length=100)
    porte: str | None = Field(default=None, max_length=30)
    site: str | None = Field(default=None, max_length=300)
    email_financeiro: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    endereco: str | None = None
    responsavel_id: int | None = None
    papeis: list[Papel] | None = None
    origem: str | None = Field(default=None, max_length=100)
    observacoes: str | None = None
    campos_custom: dict[str, Any] | None = None
    categoria_padrao_id: int | None = None
    condicao_habitual: str | None = Field(default=None, max_length=200)


class EmpresaCriar(_EmpresaCampos):
    nome: str = Field(max_length=200)


class EmpresaAtualizar(_EmpresaCampos):
    nome: str | None = Field(default=None, max_length=200)
    ativo: bool | None = None


class EmpresaSaida(_EnderecoSaida, _ReceitaSaida, Saida):
    id: int
    nome: str
    documento: str | None
    nome_fantasia: str | None
    segmento: str | None
    porte: str | None
    site: str | None
    email_financeiro: str | None
    telefone: str | None
    endereco: str | None
    responsavel_id: int | None
    responsavel_nome: str | None = None
    papeis: list[str]
    origem: str | None
    observacoes: str | None
    campos_custom: dict[str, Any]
    categoria_padrao_id: int | None
    categoria_padrao_nome: str | None = None
    condicao_habitual: str | None
    ativo: bool
    criado_em: datetime
    # None = o perfil não vê (oportunidades: comercial.oportunidades.ver; títulos/saldo: financeiro.titulos.ver)
    oportunidades: int | None = 0
    titulos_receber: int | None = 0
    saldo_receber: Decimal | None = Decimal("0.00")


class ContatoResumo(Saida):
    id: int
    nome: str
    cargo: str | None
    email: str | None
    telefone: str | None


class EmpresaDetalhe(EmpresaSaida):
    contatos: list[ContatoResumo] = []


class MesclarIn(Entrada):
    duplicada_id: int


class MesclaSaida(BaseModel):
    empresa: EmpresaSaida
    movidos: dict[str, int]
    mensagem: str


class EmpresaCurta(BaseModel):
    id: int
    nome: str
    documento: str | None
    ativo: bool
    oportunidades: int
    titulos: int


class Duplicidade(BaseModel):
    a: EmpresaCurta
    b: EmpresaCurta
    motivo: str
    semelhanca: float


# ------------------------------------------------------------------------------------------------- pessoa
class _PessoaCampos(_EnderecoCampos):
    empresa_id: int | None = None
    # ligada (padrão): o endereço é o da empresa e acompanha as mudanças dela. Editar o endereço sem mandar a marca
    # desliga a marca.
    usa_endereco_da_empresa: bool | None = None
    cargo: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    responsavel_id: int | None = None
    canal_preferido: Canal | None = None
    observacoes: str | None = None
    campos_custom: dict[str, Any] | None = None


class PessoaCriar(_PessoaCampos):
    nome: str = Field(max_length=200)


class PessoaAtualizar(_PessoaCampos):
    nome: str | None = Field(default=None, max_length=200)
    ativo: bool | None = None


class PessoaSaida(_EnderecoSaida, Saida):
    id: int
    nome: str
    empresa_id: int | None
    empresa_nome: str | None = None
    cargo: str | None
    email: str | None
    telefone: str | None
    responsavel_id: int | None
    responsavel_nome: str | None = None
    canal_preferido: str | None
    observacoes: str | None
    campos_custom: dict[str, Any]
    usa_endereco_da_empresa: bool = True
    ativo: bool


# ------------------------------------------------------------------------------------------------- produto
class _ProdutoCampos(Entrada):
    codigo: str | None = Field(default=None, max_length=50)
    unidade: str | None = Field(default=None, max_length=30)
    preco_referencia: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    recorrente: bool | None = None
    descricao: str | None = None


class ProdutoCriar(_ProdutoCampos):
    nome: str = Field(max_length=200)
    tipo: TipoProduto


class ProdutoAtualizar(_ProdutoCampos):
    nome: str | None = Field(default=None, max_length=200)
    tipo: TipoProduto | None = None
    ativo: bool | None = None


class ProdutoSaida(Saida):
    id: int
    nome: str
    tipo: str
    codigo: str | None
    unidade: str | None
    preco_referencia: Decimal | None
    recorrente: bool
    descricao: str | None
    ativo: bool


# ------------------------------------------------------------------------------------------------- fornecedor
class _FornecedorCampos(_EnderecoCampos):
    documento: str | None = Field(default=None, max_length=18)
    contato: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    categoria_padrao_id: int | None = None
    condicao_habitual: str | None = Field(default=None, max_length=200)
    observacoes: str | None = None


class FornecedorCriar(_FornecedorCampos):
    """Com `empresa_id`, marca uma empresa existente como fornecedor (sem duplicar cadastro); sem ele, cria pelo nome."""

    nome: str | None = Field(default=None, max_length=200)
    empresa_id: int | None = None


class FornecedorAtualizar(_FornecedorCampos):
    nome: str | None = Field(default=None, max_length=200)
    ativo: bool | None = None


class FornecedorSaida(_EnderecoSaida, _ReceitaSaida):
    id: int
    nome: str
    documento: str | None
    contato: str | None
    email: str | None
    telefone: str | None
    categoria_padrao_id: int | None
    categoria_padrao_nome: str | None
    condicao_habitual: str | None
    observacoes: str | None
    papeis: list[str]
    ativo: bool
    titulos_pagar: int = 0


# ------------------------------------------------------------------------------------------------- categoria
class CategoriaCriar(Entrada):
    nome: str = Field(max_length=120)
    natureza: Natureza
    superior_id: int | None = None


class CategoriaAtualizar(Entrada):
    nome: str | None = Field(default=None, max_length=120)
    natureza: Natureza | None = None
    superior_id: int | None = None
    ativo: bool | None = None


class CategoriaSaida(Saida):
    id: int
    nome: str
    natureza: str
    superior_id: int | None
    superior_nome: str | None = None
    ativo: bool


# ------------------------------------------------------------------------------------------------- centro de custo
class CentroCriar(Entrada):
    nome: str = Field(max_length=120)
    codigo: str = Field(max_length=20)
    responsavel_id: int | None = None


class CentroAtualizar(Entrada):
    nome: str | None = Field(default=None, max_length=120)
    codigo: str | None = Field(default=None, max_length=20)
    responsavel_id: int | None = None
    ativo: bool | None = None


class CentroSaida(Saida):
    id: int
    nome: str
    codigo: str
    responsavel_id: int | None
    responsavel_nome: str | None = None
    ativo: bool


# ------------------------------------------------------------------------------------------------- conta financeira
class ContaCriar(Entrada):
    nome: str = Field(max_length=120)
    instituicao: str | None = Field(default=None, max_length=120)
    saldo_inicial: Decimal = Field(max_digits=15, decimal_places=2)  # pode ser negativo
    data_base: date


class ContaAtualizar(Entrada):
    nome: str | None = Field(default=None, max_length=120)
    instituicao: str | None = Field(default=None, max_length=120)
    saldo_inicial: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    data_base: date | None = None
    ativo: bool | None = None


class ContaSaida(Saida):
    id: int
    nome: str
    instituicao: str | None
    saldo_inicial: Decimal
    data_base: date
    ativo: bool
    tem_movimento: bool = False


# ------------------------------------------------------------------------------------------------- campo custom
class CampoCriar(Entrada):
    nome: str = Field(max_length=120)
    tipo: TipoCampo
    objeto: ObjetoCampo
    opcoes: list[str] | None = None
    obrigatorio: bool = False
    exigido_na_etapa_id: int | None = None
    ordem: int = 0


class CampoAtualizar(Entrada):
    """Tipo e objeto não mudam depois de criado (os valores já gravados dependem deles): crie outro campo."""

    nome: str | None = Field(default=None, max_length=120)
    opcoes: list[str] | None = None
    obrigatorio: bool | None = None
    exigido_na_etapa_id: int | None = None
    ordem: int | None = None


class CampoSaida(Saida):
    id: int
    nome: str
    slug: str
    tipo: str
    objeto: str
    opcoes: list[str]
    obrigatorio: bool
    exigido_na_etapa_id: int | None
    etapa_nome: str | None = None
    ordem: int
    arquivado: bool
    registros_preenchidos: int = 0
    dependencias_ativas: int = 0


class Dependencia(BaseModel):
    tipo: Literal["dashboard", "automacao", "etapa", "registros"]
    id: int | None
    nome: str
    detalhe: str
    ativa: bool


class DependenciasSaida(BaseModel):
    campo: CampoSaida
    dependencias: list[Dependencia]
    pode_arquivar: bool
    mensagem: str


class ArquivarIn(Entrada):
    confirmar: bool = False


class EtapaOpcao(BaseModel):
    id: int
    nome: str
    funil_nome: str


# ------------------------------------------------------------------------------------------------- consultas públicas
class EmpresaExistente(BaseModel):
    id: int
    nome: str


class ConsultaCnpjSaida(_EnderecoSaida):
    documento: str
    nome: str | None = None
    nome_fantasia: str | None = None
    segmento: str | None = None
    porte: Literal["ME", "EPP", "Demais"] | None = None
    situacao: str | None = None
    abertura: str | None = None
    telefone: str | None = None
    email_financeiro: str | None = None
    fonte: str
    socios: list["SocioConsulta"] = []
    cnae_principal: str | None = None
    cnaes_secundarios: list[str] = []
    natureza_juridica: str | None = None
    capital_social: Decimal | None = None
    empresa_existente: EmpresaExistente | None = None


class SocioConsulta(BaseModel):
    nome: str
    qualificacao: str | None = None
    documento: str | None = None
    data_entrada: date | None = None
    faixa_etaria: str | None = None


class SocioSaida(SocioConsulta, Saida):
    id: int
    empresa_id: int


TipoAnexo = Literal["cartao_cnpj", "contrato", "documento", "outro"]


class AnexoSaida(BaseModel):
    id: int
    empresa_id: int
    nome: str
    tipo: str
    mime: str | None
    tamanho: int
    enviado_por_nome: str | None = None
    criado_em: datetime
    ativo: bool
    url: str  # caminho da API (sem /api): GET → download, exige login e nucleo.cadastros.ver


ConsultaCnpjSaida.model_rebuild()


class ConsultaCepSaida(BaseModel):
    cep: str
    logradouro: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    uf: str | None = None
    fonte: str


# ------------------------------------------------------------------------------------------------- planilhas
class ErroPlanilha(BaseModel):
    linha: int
    coluna: str | None = None
    mensagem: str


class PreviaPlanilha(BaseModel):
    linha: int
    acao: Literal["criar", "atualizar", "ignorar"]
    nome: str


class ImportacaoSaida(BaseModel):
    total: int
    criar: int
    atualizar: int
    ignorar: int
    erros: list[ErroPlanilha]
    previa: list[PreviaPlanilha]


# ------------------------------------------------------------------------------------------------- busca global
class ItemBusca(BaseModel):
    id: int
    titulo: str
    subtitulo: str | None
    href: str


class GrupoBusca(BaseModel):
    tipo: Literal["empresas", "pessoas", "oportunidades", "titulos"]
    rotulo: str
    itens: list[ItemBusca]


class BuscaSaida(BaseModel):
    termo: str
    grupos: list[GrupoBusca]
