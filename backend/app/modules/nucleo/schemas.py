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


# ------------------------------------------------------------------------------------------------- empresa
class _EmpresaCampos(Entrada):
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


class EmpresaSaida(Saida):
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
class _PessoaCampos(Entrada):
    empresa_id: int | None = None
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


class PessoaSaida(Saida):
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
class _FornecedorCampos(Entrada):
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


class FornecedorSaida(BaseModel):
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
