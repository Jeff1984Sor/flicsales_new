"""Proposta automatizada + documento (PDF): modelo de proposta, dados da proposta gerada e textos do documento.

Funções puras: recebem tudo por parâmetro (inclusive "hoje") e levantam `RegraViolada` com a mensagem da tela.
Valores vêm SEMPRE do cadastro (produto/oportunidade): nada de número inventado, nem pela IA.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain import RegraViolada
from app.domain.dinheiro import ZERO, arredondar, dinheiro, formatar_brl
from app.domain.proposta import calcular_total, proxima_versao

# Mesma lista aceita na proposta (app.modules.comercial.regras.CONDICOES_PROPOSTA).
CONDICOES = ("À vista", "2 parcelas", "3 parcelas", "Recorrente mensal")
CONDICAO_SEM_MODELO = "À vista"
VALIDADE_MIN, VALIDADE_MAX = 1, 365

VARIAVEIS = ("empresa.nome", "empresa.cnpj", "contato.nome", "oportunidade.titulo", "proposta.titulo",
             "proposta.total", "proposta.validade", "proposta.condicao", "responsavel.nome", "hoje")

MODELO_INICIAL = {
    "nome": "Proposta comercial padrão",
    "padrao": True,
    "introducao": ("Prezado(a) {{contato.nome}},\n\nApresentamos a proposta para {{oportunidade.titulo}}, preparada "
                   "para a {{empresa.nome}} a partir do que conversamos."),
    "termos": ("Valor total: {{proposta.total}}. Condição de pagamento: {{proposta.condicao}}.\n"
               "Proposta válida até {{proposta.validade}}. Valores sujeitos a confirmação após a validade."),
    "rodape": "Proposta emitida em {{hoje}} por {{responsavel.nome}}.",
    "validade_dias": 15,
    "condicao_padrao": "À vista",
}


def _data_br(d: date | None) -> str | None:
    return d.strftime("%d/%m/%Y") if d else None


# ------------------------------------------------------------------------------------------------ modelo de proposta
def validar_modelo_proposta(*, nome: str | None, validade_dias: int | None, condicao_padrao: str | None,
                            outros_nomes: list[str]) -> str:
    """Nome obrigatório e único (sem diferenciar maiúsculas), validade 1–365 dias, condição aceita na proposta.
    `outros_nomes` = nomes dos DEMAIS modelos. Devolve o nome limpo."""
    n = (nome or "").strip()
    if not n:
        raise RegraViolada("Informe o nome do modelo de proposta.")
    if n.casefold() in {o.strip().casefold() for o in outros_nomes}:
        raise RegraViolada(f"Já existe um modelo de proposta chamado {n}. Escolha outro nome.")
    if validade_dias is None or not (VALIDADE_MIN <= validade_dias <= VALIDADE_MAX):
        raise RegraViolada("A validade da proposta deve ficar entre 1 e 365 dias.")
    if condicao_padrao not in (None, "") and condicao_padrao not in CONDICOES:
        raise RegraViolada(f"Condição de pagamento inválida. Use: {', '.join(CONDICOES)}.")
    return n


def conferir_padrao_e_ativo(*, era_padrao: bool, padrao: bool, ativo: bool) -> None:
    """O padrão não pode ser inativado, e sempre há um padrão: para trocar, marque OUTRO modelo como padrão."""
    if padrao and not ativo:
        raise RegraViolada("O modelo padrão não pode ser inativado. Marque outro modelo como padrão antes.")
    if era_padrao and not padrao:
        raise RegraViolada("Sempre há um modelo padrão: marque outro modelo como padrão para trocar.")


# ------------------------------------------------------------------------------------------------ proposta automática
@dataclass(frozen=True)
class ProdutoBase:
    nome: str
    descricao: str | None
    preco_referencia: Decimal | None
    recorrente: bool = False


def escopo_padrao(*, oportunidade_titulo: str, necessidade: str | None, produto: ProdutoBase | None) -> str:
    """Escopo sem IA: nome + descrição do produto; sem produto, o título e a necessidade da oportunidade."""
    if produto is not None:
        partes = [produto.nome.strip()]
        if (produto.descricao or "").strip():
            partes.append(produto.descricao.strip())
        return "\n\n".join(partes)
    partes = [oportunidade_titulo.strip()]
    if (necessidade or "").strip():
        partes.append(f"Necessidade: {necessidade.strip()}")
    return "\n\n".join(partes)


def dados_proposta_automatica(*, oportunidade_titulo: str, necessidade: str | None, valor_unico: Decimal | None,
                              valor_recorrente_mensal: Decimal | None, produto: ProdutoBase | None,
                              validade_dias: int, condicao_padrao: str | None, versoes: list[int],
                              hoje: date) -> dict:
    """Campos da proposta em RASCUNHO gerada a partir da oportunidade.

    - preço unitário = preço de referência do produto; sem produto (ou sem preço) = valor único da oportunidade;
    - mensalidade adicional = valor recorrente mensal da oportunidade, exceto quando o produto é recorrente
      (o preço do produto já é a mensalidade: não soma duas vezes);
    - quantidade 1, desconto 0, validade = hoje + validade do modelo, condição do modelo ou "À vista".
    """
    if produto is not None and produto.preco_referencia is not None:
        preco = dinheiro(produto.preco_referencia)
    else:
        preco = dinheiro(valor_unico or ZERO)
    if preco < 0:
        raise RegraViolada("O preço unitário não pode ser negativo.")
    mensal = ZERO if (produto is not None and produto.recorrente) else dinheiro(valor_recorrente_mensal or ZERO)
    if not (VALIDADE_MIN <= validade_dias <= VALIDADE_MAX):
        raise RegraViolada("A validade da proposta deve ficar entre 1 e 365 dias.")
    return {
        "titulo": f"Proposta — {oportunidade_titulo.strip()}"[:200],
        "versao": proxima_versao(versoes),
        "escopo": escopo_padrao(oportunidade_titulo=oportunidade_titulo, necessidade=necessidade, produto=produto),
        "quantidade": Decimal("1"),
        "preco_unitario": preco,
        "desconto_pct": Decimal("0"),
        "mensalidade_adicional": mensal,
        "validade": hoje + timedelta(days=validade_dias),
        "condicao": condicao_padrao or CONDICAO_SEM_MODELO,
        "status": "rascunho",
        "total": calcular_total(1, preco, 0),
    }


def escopo_da_ia(resposta: dict | None) -> str | None:
    """Aceita da IA `{"paragrafos": [str, ...]}` (2–5) ou `{"escopo": str}`. Formato fora disso = None (segue sem IA)."""
    if not isinstance(resposta, dict):
        return None
    paragrafos = resposta.get("paragrafos")
    if isinstance(paragrafos, list):
        ps = [p.strip() for p in paragrafos if isinstance(p, str) and p.strip()]
    elif isinstance(resposta.get("escopo"), str):
        ps = [p.strip() for p in resposta["escopo"].split("\n\n") if p.strip()]
    else:
        return None
    if not ps:
        return None
    return "\n\n".join(ps[:5])[:8000]


# ------------------------------------------------------------------------------------------------ documento
def valores_variaveis(*, empresa_nome: str | None, empresa_cnpj: str | None, contato_nome: str | None,
                      oportunidade_titulo: str | None, proposta_titulo: str | None, total: Decimal | None,
                      validade: date | None, condicao: str | None, responsavel_nome: str | None,
                      hoje: date) -> dict[str, str | None]:
    """Valores das variáveis aceitas nos textos do modelo (VARIAVEIS), já formatados para o documento."""
    return {
        "empresa.nome": empresa_nome,
        "empresa.cnpj": empresa_cnpj,
        "contato.nome": contato_nome,
        "oportunidade.titulo": oportunidade_titulo,
        "proposta.titulo": proposta_titulo,
        "proposta.total": formatar_brl(total) if total is not None else None,
        "proposta.validade": _data_br(validade),
        "proposta.condicao": condicao,
        "responsavel.nome": responsavel_nome,
        "hoje": _data_br(hoje),
    }


def mostra_faixa_rascunho(status: str, desconto_pct) -> bool:
    """Faixa "RASCUNHO — não enviar": proposta em rascunho, ou em aprovação com desconto > 0."""
    desconto = Decimal(str(desconto_pct or 0))
    return status == "rascunho" or (status == "em_aprovacao" and desconto > 0)


def nome_arquivo_pdf(proposta_id: int, versao: int) -> str:
    return f"proposta-{proposta_id}-v{versao}.pdf"


def linha_item(*, quantidade, preco_unitario, desconto_pct) -> dict[str, Decimal]:
    """Linha da tabela do documento: total = qtd × unitário × (1 − desc)."""
    return {"quantidade": Decimal(str(quantidade)), "preco_unitario": arredondar(Decimal(str(preco_unitario))),
            "desconto_pct": Decimal(str(desconto_pct or 0)),
            "total": calcular_total(quantidade, preco_unitario, desconto_pct)}
