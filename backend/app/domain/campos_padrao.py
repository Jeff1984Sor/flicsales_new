"""Campos padrões (contrato Núcleo parte 2, §4): os campos fixos do sistema por objeto, com obrigatoriedade e
visibilidade configuráveis na tela Campos de dados. Funções puras.

O catálogo diz o que existe e o que PODE mudar (`fixo=True` = sempre obrigatório e visível, sem lápis: nome da
empresa, da pessoa, do produto; título e funil da oportunidade; tipo do produto). A configuração gravada
(`campo_padrao_config`) só guarda o que o Gestor mudou; o resto vale o padrão do catálogo.

Validação do obrigatório (`validar_obrigatorios`): ao CRIAR, todo campo obrigatório precisa vir preenchido; ao
ALTERAR, só se confere o que veio no corpo (apagar um obrigatório → 400). Assim um campo que vira obrigatório hoje não
trava a edição de registros antigos em outros campos.
"""

from dataclasses import dataclass
from typing import Any

from app.domain import RegraViolada

OBJETOS = ("oportunidade", "empresa", "pessoa", "produto")


@dataclass(frozen=True)
class CampoPadrao:
    campo: str  # nome do atributo na API (ex.: "segmento", "empresa_id")
    nome: str
    tipo: str  # rótulo do tipo de dado (Texto, Data, Lista, Moeda…)
    fixo: bool = False  # sempre obrigatório e visível; não pode ser configurado
    obrigatorio: bool = False  # padrão
    visivel: bool = True  # padrão
    # campos alternativos do corpo que também satisfazem o obrigatório (ex.: empresa_nome cria a empresa)
    alternativos: tuple[str, ...] = ()


_ENDERECO = (
    CampoPadrao("cep", "CEP", "Texto"),
    CampoPadrao("logradouro", "Logradouro", "Texto"),
    CampoPadrao("numero", "Número", "Texto"),
    CampoPadrao("complemento", "Complemento", "Texto"),
    CampoPadrao("bairro", "Bairro", "Texto"),
    CampoPadrao("cidade", "Cidade", "Texto"),
    CampoPadrao("uf", "UF", "Lista"),
)

CATALOGO: dict[str, tuple[CampoPadrao, ...]] = {
    "empresa": (
        CampoPadrao("nome", "Nome", "Texto", fixo=True, obrigatorio=True),
        CampoPadrao("documento", "CNPJ/CPF", "Documento"),
        CampoPadrao("nome_fantasia", "Nome fantasia", "Texto"),
        CampoPadrao("segmento", "Segmento", "Lista"),
        CampoPadrao("porte", "Porte", "Lista"),
        CampoPadrao("site", "Site", "Hiperlink"),
        CampoPadrao("telefone", "Telefone", "Telefone"),
        CampoPadrao("origem", "Origem", "Texto"),
        CampoPadrao("observacoes", "Observações", "Texto longo"),
        *_ENDERECO,
    ),
    "pessoa": (
        CampoPadrao("nome", "Nome", "Texto", fixo=True, obrigatorio=True),
        CampoPadrao("empresa_id", "Empresa", "Vínculo"),
        CampoPadrao("cargo", "Cargo", "Texto"),
        CampoPadrao("email", "E-mail", "E-mail", alternativos=("emails",)),
        CampoPadrao("telefone", "Telefone", "Telefone", alternativos=("telefones",)),
        CampoPadrao("canal_preferido", "Canal preferido", "Lista"),
        CampoPadrao("base_legal", "Base legal (LGPD)", "Lista"),
        CampoPadrao("observacoes", "Observações", "Texto longo"),
    ),
    "produto": (
        CampoPadrao("nome", "Nome", "Texto", fixo=True, obrigatorio=True),
        CampoPadrao("tipo", "Tipo", "Lista", fixo=True, obrigatorio=True),
        CampoPadrao("codigo", "Código", "Texto"),
        CampoPadrao("unidade", "Unidade", "Texto"),
        CampoPadrao("preco_referencia", "Preço de referência", "Moeda"),
        CampoPadrao("descricao", "Descrição", "Texto longo"),
    ),
    "oportunidade": (
        CampoPadrao("titulo", "Título", "Texto", fixo=True, obrigatorio=True),
        CampoPadrao("funil_id", "Funil", "Lista", fixo=True, obrigatorio=True),
        CampoPadrao("empresa_id", "Empresa", "Vínculo", alternativos=("empresa_nome",)),
        CampoPadrao("contato_id", "Contato", "Vínculo"),
        CampoPadrao("previsao_fechamento", "Previsão de fechamento", "Data"),
        CampoPadrao("proxima_acao", "Próxima ação", "Texto"),
        CampoPadrao("proxima_acao_prazo", "Prazo da próxima ação", "Data"),
        CampoPadrao("origem", "Origem", "Texto"),
        CampoPadrao("necessidade", "Necessidade", "Texto longo"),
        CampoPadrao("decisor", "Decisor", "Texto"),
        CampoPadrao("orcamento_concorrencia", "Orçamento e concorrência", "Texto longo"),
        CampoPadrao("criterio_sucesso", "Critério de sucesso", "Texto longo"),
    ),
}


@dataclass(frozen=True)
class Config:
    """Linha gravada em `campo_padrao_config`."""

    obrigatorio: bool
    visivel: bool
    ordem: int = 0


@dataclass(frozen=True)
class CampoEfetivo:
    campo: str
    nome: str
    tipo: str
    fixo: bool
    obrigatorio: bool
    visivel: bool
    ordem: int


def _objeto(objeto: str) -> tuple[CampoPadrao, ...]:
    if objeto not in CATALOGO:
        raise RegraViolada("Objeto inválido. Use oportunidade, empresa, pessoa ou produto.")
    return CATALOGO[objeto]


def catalogo(objeto: str, campo: str) -> CampoPadrao:
    c = next((c for c in _objeto(objeto) if c.campo == campo), None)
    if c is None:
        raise RegraViolada("Campo padrão não encontrado neste objeto.")
    return c


def efetivos(objeto: str, configs: dict[str, Config] | None = None) -> list[CampoEfetivo]:
    """Catálogo + o que foi configurado, na ordem configurada (empate: ordem do catálogo). Campo fixo ignora config."""
    out = []
    for n, c in enumerate(_objeto(objeto)):
        cfg = None if c.fixo else (configs or {}).get(c.campo)
        out.append(CampoEfetivo(c.campo, c.nome, c.tipo, c.fixo, c.obrigatorio if cfg is None else cfg.obrigatorio,
                                c.visivel if cfg is None else cfg.visivel, n if cfg is None or not cfg.ordem
                                else cfg.ordem))
    return sorted(out, key=lambda e: (not e.fixo, e.ordem))


def validar_alteracao(objeto: str, campo: str, *, obrigatorio: bool, visivel: bool) -> CampoPadrao:
    c = catalogo(objeto, campo)
    if c.fixo:
        raise RegraViolada(f"“{c.nome}” é sempre obrigatório e visível: não pode ser alterado.")
    if obrigatorio and not visivel:
        raise RegraViolada(f"“{c.nome}” obrigatório precisa ficar visível no cadastro (senão ninguém consegue "
                           "preenchê-lo). Torne-o visível ou deixe de exigir.")
    return c


def _vazio(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list | tuple | dict) and not v)


def validar_obrigatorios(objeto: str, campos: list[CampoEfetivo], valores: dict[str, Any], *, criando: bool) -> None:
    """`valores` = corpo já validado. Fixos ficam de fora (cada rota já exige os seus)."""
    por_campo = {c.campo: c for c in _objeto(objeto)}
    faltando = []
    for e in campos:
        if e.fixo or not e.obrigatorio:
            continue
        cat = por_campo[e.campo]
        chaves = (e.campo, *cat.alternativos)
        if criando:
            if all(_vazio(valores.get(k)) for k in chaves):
                faltando.append(e.nome)
        elif any(k in valores for k in chaves) and all(_vazio(valores.get(k)) for k in chaves if k in valores):
            faltando.append(e.nome)
    if faltando:
        raise RegraViolada(f"Preencha o campo obrigatório: {', '.join(faltando)}.")
