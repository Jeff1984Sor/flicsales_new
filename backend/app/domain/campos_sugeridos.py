"""Sugestão de campos (contrato Núcleo parte 2, §4): modelos prontos de campo personalizado por objeto.

"+ Adicionar campo" cria o campo personalizado já configurado (nome, tipo, opções). Sugestão cujo slug já existe no
objeto (ativo ou arquivado) não aparece. Funções puras: quem chama passa os slugs existentes.
"""

from dataclasses import dataclass, field

from app.domain import RegraViolada

OBJETOS = ("oportunidade", "empresa", "pessoa", "produto")


@dataclass(frozen=True)
class Sugestao:
    chave: str  # = slug do campo que será criado (= slug_de(nome): campo criado à mão com o mesmo nome esconde a sugestão)
    nome: str
    tipo: str  # texto | numero | moeda | data | lista | multipla | link
    descricao: str
    opcoes: tuple[str, ...] = field(default_factory=tuple)


CATALOGO: dict[str, tuple[Sugestao, ...]] = {
    "pessoa": (
        Sugestao("data_de_nascimento", "Data de nascimento", "data", "Para lembrar aniversários e segmentar."),
        Sugestao("linkedin", "LinkedIn", "link", "Perfil profissional do contato."),
        Sugestao("cpf", "CPF", "texto", "Documento do contato (quando a base legal permitir)."),
        Sugestao("departamento", "Departamento", "texto", "Área do contato na empresa."),
    ),
    "empresa": (
        Sugestao("inscricao_estadual", "Inscrição estadual", "texto", "Para emissão de nota fiscal."),
        Sugestao("no_de_funcionarios", "Nº de funcionários", "numero", "Tamanho da operação do cliente."),
        Sugestao("faturamento_anual", "Faturamento anual", "moeda", "Faturamento estimado no ano."),
        Sugestao("linkedin", "LinkedIn", "link", "Página da empresa no LinkedIn."),
    ),
    "oportunidade": (
        Sugestao("concorrente", "Concorrente", "texto", "Quem disputa a venda com você."),
        Sugestao("fonte_do_lead", "Fonte do lead", "lista", "De onde veio a oportunidade.",
                 ("Indicação", "Site", "Evento", "Prospecção ativa", "Redes sociais")),
        Sugestao("data_prevista_de_decisao", "Data prevista de decisão", "data", "Quando o cliente decide."),
    ),
    "produto": (
        Sugestao("sku_externo", "SKU externo", "texto", "Código do item em outro sistema (ERP, loja)."),
        Sugestao("ncm", "NCM", "texto", "Nomenclatura Comum do Mercosul (produtos com nota fiscal)."),
        Sugestao("garantia", "Garantia", "texto", "Prazo e condições de garantia."),
    ),
}


def disponiveis(objeto: str, slugs_existentes: set[str]) -> list[Sugestao]:
    """Sugestões do objeto que ainda não viraram campo."""
    if objeto not in CATALOGO:
        raise RegraViolada("Objeto inválido. Use oportunidade, empresa, pessoa ou produto.")
    return [s for s in CATALOGO[objeto] if s.chave not in slugs_existentes]


def obter(objeto: str, chave: str, slugs_existentes: set[str]) -> Sugestao:
    """A sugestão para criar. Já criada → RegraViolada."""
    if objeto not in CATALOGO:
        raise RegraViolada("Objeto inválido. Use oportunidade, empresa, pessoa ou produto.")
    s = next((s for s in CATALOGO[objeto] if s.chave == chave), None)
    if s is None:
        raise RegraViolada("Sugestão de campo não encontrada. Atualize a tela e escolha outra.")
    if s.chave in slugs_existentes:
        raise RegraViolada(f"O campo “{s.nome}” já existe neste objeto (veja também os arquivados).")
    return s
