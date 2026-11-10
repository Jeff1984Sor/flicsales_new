"""Serviços do Financeiro que OUTROS módulos chamam. Assinaturas estáveis — mudar exige combinar com o coordenador.

`preparar_recebiveis_do_ganho` é a ponte Comercial → Financeiro: a venda ganha vira recebíveis em RASCUNHO.
Não registra pagamento nem movimenta caixa. Idempotente: chamar de novo não duplica parcela.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.fechamento import parcelas_do_fechamento
from app.modules.financeiro.models import Titulo


def recebiveis_da_oportunidade(db: Session, oportunidade_id: int) -> list[Titulo]:
    return list(db.scalars(
        select(Titulo).where(Titulo.origem_oportunidade_id == oportunidade_id).order_by(Titulo.parcela)))


def preparar_recebiveis_do_ganho(db: Session, *, oportunidade_id: int, titulo: str, empresa_id: int | None,
                                 valor: Decimal, condicao: str | int, primeiro_vencimento: date | None,
                                 responsavel_id: int) -> list[Titulo]:
    """Cria (flush, sem commit) as parcelas em rascunho que ainda não existem e devolve TODAS as da oportunidade.
    Levanta `RegraViolada` (→ HTTP 400) se faltar empresa, valor ou vencimento."""
    existentes = {t.parcela for t in recebiveis_da_oportunidade(db, oportunidade_id) if t.parcela is not None}
    novas = parcelas_do_fechamento(
        oportunidade_id=oportunidade_id, titulo=titulo, empresa_id=empresa_id, valor=valor, condicao=condicao,
        primeiro_vencimento=primeiro_vencimento, existentes=existentes)
    for p in novas:
        db.add(Titulo(
            direcao="receber", empresa_id=p.empresa_id, descricao=p.descricao, vencimento=p.vencimento,
            valor_original=p.valor, saldo=p.valor, responsavel_id=responsavel_id, status="rascunho",
            origem_oportunidade_id=p.oportunidade_id, parcela=p.parcela, parcelas_total=p.parcelas_total))
    db.flush()
    return recebiveis_da_oportunidade(db, oportunidade_id)


def titulos_em_contestacao(db: Session) -> set[int]:
    """Ids dos títulos com cobrança "Em contestação" (a automação de cobrança deve suspender o envio)."""
    from app.modules.financeiro.operacoes import titulos_em_contestacao as _contestados

    return _contestados(db)


def cobranca_suspensa(db: Session, titulo_id: int) -> bool:
    """A automação de cobrança deve pular este título? (recebido, cancelado, rascunho ou em contestação)."""
    from app.domain.cobranca import cobranca_suspensa as _suspensa
    from app.modules.financeiro.models import Cobranca

    t = db.get(Titulo, titulo_id)
    if t is None:
        return True
    situacoes = list(db.scalars(select(Cobranca.situacao).where(Cobranca.titulo_id == titulo_id)))
    return _suspensa(titulo_status=t.status, situacoes=situacoes)


# ---------------------------------------------------------------- quem vê o quê (usado também pela IA)
VER_PAGAR = ("financeiro.aprovacoes.ver", "financeiro.baixas.ver")


def pode_ver_pagar(ctx) -> bool:
    """Contas a pagar são da operação financeira: `financeiro.titulos.ver` sozinho (perfil Comercial, "leitura dos
    recebíveis") vê só títulos a RECEBER. Ver a pagar exige também Aprovações ou Baixas."""
    return any(ctx.pode(p) for p in VER_PAGAR)


def filtrar_direcao_visivel(ctx, consulta):
    """Restringe uma consulta de títulos às direções que o perfil pode ver."""
    return consulta if pode_ver_pagar(ctx) else consulta.where(Titulo.direcao == "receber")


def pode_ver_caixa(ctx) -> bool:
    """Saldo de caixa e contas financeiras: `financeiro.caixa.ver`."""
    return ctx.pode("financeiro.caixa.ver")
