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
# "lista" = seleção única, "multipla" = seleção múltipla, "link" = hiperlink; "sim_nao" só para campos antigos
TipoCampo = Literal["texto", "numero", "moeda", "data", "sim_nao", "lista", "multipla", "link"]
ObjetoCampo = Literal["empresa", "pessoa", "oportunidade", "produto"]
TipoDesconto = Literal["percentual", "valor"]
Frequencia = Literal["diaria", "semanal", "mensal", "semestral", "anual"]
TipoLista = Literal["segmento", "porte", "motivo_perda"]


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
class TelefoneItem(BaseModel):
    """Um telefone da pessoa. Tipo: celular | whatsapp | fixo | comercial (padrão celular). Normalizado no domínio
    (app.domain.contatos); exatamente um principal (nenhum marcado → o primeiro)."""

    model_config = ConfigDict(extra="ignore")
    numero: str | None = Field(default=None, max_length=40)
    tipo: str | None = Field(default=None, max_length=15)
    principal: bool = False


class EmailItem(BaseModel):
    """Um e-mail da pessoa. Tipo: comercial | pessoal | financeiro (padrão comercial). Sem repetição."""

    model_config = ConfigDict(extra="ignore")
    email: str | None = Field(default=None, max_length=200)
    tipo: str | None = Field(default=None, max_length=15)
    principal: bool = False


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
    # LGPD: valores de app.domain.cadastro.BASES_LEGAIS / PERMISSOES_COMUNICACAO (fora da lista → 400)
    base_legal: str | None = Field(default=None, max_length=30)
    permissoes_comunicacao: list[str] | None = None
    # vários contatos: com a lista, `email`/`telefone` são ignorados e passam a espelhar o principal; sem a lista,
    # `email`/`telefone` trocam o principal (telas antigas continuam funcionando)
    telefones: list[TelefoneItem] | None = None
    emails: list[EmailItem] | None = None


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
    base_legal: str | None = None
    permissoes_comunicacao: list[str] = []
    telefones: list[dict[str, Any]] = []  # [{numero, tipo, principal}] — o principal primeiro
    emails: list[dict[str, Any]] = []  # [{email, tipo, principal}] — o principal primeiro
    ativo: bool


# ------------------------------------------------------------------------------------------------- produto
class _ProdutoCampos(Entrada):
    codigo: str | None = Field(default=None, max_length=50)
    unidade: str | None = Field(default=None, max_length=30)
    preco_referencia: Decimal | None = Field(default=None, ge=0, max_digits=15, decimal_places=2)
    recorrente: bool | None = None
    descricao: str | None = None
    # desconto padrão (os dois ou nenhum): percentual 0–100; valor ≥ 0 e ≤ preço de referência
    desconto_tipo: TipoDesconto | None = None
    desconto_valor: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    # recorrência (só com recorrente=true; recorrente=false limpa): a cada `intervalo` dias/semanas/meses/anos
    frequencia: Frequencia | None = None
    intervalo: int | None = None
    dias_semana: list[str] | None = None  # seg ter qua qui sex sab dom (obrigatório na semanal)
    campos_custom: dict[str, Any] | None = None


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
    desconto_tipo: str | None = None
    desconto_valor: Decimal | None = None
    frequencia: str | None = None
    intervalo: int | None = None
    dias_semana: list[str] = []
    recorrencia_texto: str | None = None  # "Toda semana: seg, qua", "A cada 2 meses", "Semestral"…
    campos_custom: dict[str, Any] = {}


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
    # exibir na etapa (só oportunidade): funil + etapa a partir da qual o campo aparece (null = sempre)
    exibir_funil_id: int | None = None
    exibir_etapa_id: int | None = None
    visivel: bool = True  # preferência: aparece no cadastro (oculto continua guardando o valor)
    ordem: int = 0


class CampoAtualizar(Entrada):
    """Tipo e objeto não mudam depois de criado (os valores já gravados dependem deles): crie outro campo."""

    nome: str | None = Field(default=None, max_length=120)
    opcoes: list[str] | None = None
    obrigatorio: bool | None = None
    exigido_na_etapa_id: int | None = None
    exibir_funil_id: int | None = None
    exibir_etapa_id: int | None = None
    visivel: bool | None = None
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
    funil_id: int | None = None  # funil da etapa que exige o campo
    funil_nome: str | None = None
    exibir_funil_id: int | None = None
    exibir_funil_nome: str | None = None
    exibir_etapa_id: int | None = None
    exibir_etapa_nome: str | None = None
    exibir_etapa_ordem: int | None = None  # aparece quando a etapa da oportunidade tem ordem ≥ esta
    visivel: bool = True
    criado_em: datetime | None = None
    tipo_rotulo: str | None = None  # "Seleção única", "Seleção múltipla", "Hiperlink"…
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
    funil_id: int
    funil_nome: str
    ordem: int = 0


class CampoSugeridoSaida(BaseModel):
    """Modelo pronto de campo (app.domain.campos_sugeridos). `chave` = slug do campo que será criado."""

    objeto: str
    chave: str
    nome: str
    tipo: str
    tipo_rotulo: str
    descricao: str
    opcoes: list[str] = []


class CampoPadraoSaida(BaseModel):
    """Campo fixo do sistema (app.domain.campos_padrao). `fixo` = sempre obrigatório e visível (sem lápis)."""

    objeto: str
    campo: str
    nome: str
    tipo: str
    tipo_rotulo: str = "Campo padrão"
    fixo: bool
    obrigatorio: bool
    visivel: bool
    ordem: int


class CampoPadraoAtualizar(Entrada):
    obrigatorio: bool | None = None
    visivel: bool | None = None
    ordem: int | None = None


# ------------------------------------------------------------------------------------------------- listas (governança)
class OpcaoListaSaida(Saida):
    id: int
    tipo: str
    nome: str
    ordem: int
    ativo: bool
    criado_em: datetime | None = None


class OpcaoListaCriar(Entrada):
    nome: str = Field(max_length=120)
    ordem: int | None = None  # sem ordem: vai para o fim


class OpcaoListaAtualizar(Entrada):
    nome: str | None = Field(default=None, max_length=120)
    ordem: int | None = None
    ativo: bool | None = None


class ReordenarIn(Entrada):
    ids: list[int]  # POST /listas/{tipo}/reordenar: todos os itens (ativos e inativos), na nova ordem


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
