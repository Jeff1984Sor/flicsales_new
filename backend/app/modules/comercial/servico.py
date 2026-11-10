"""Serviços do Comercial: carregar com escopo, empresa nascendo na oportunidade, histórico, serialização e cálculos.

Outros módulos podem chamar `registrar_evento` e `oportunidades_abertas_resumo` (assinaturas estáveis).
"""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import hoje as hoje_de_negocio
from app.core.deps import Contexto
from app.core.models import Usuario
from app.domain import RegraViolada
from app.domain.atividade import atrasada
from app.domain.cadastro import chave_de_nome, validar_nome
from app.domain.dinheiro import ZERO
from app.domain.funil import alem_do_limite, dias_na_etapa
from app.modules.comercial import regras
from app.modules.comercial.models import (
    Atividade,
    Comunicacao,
    Etapa,
    Funil,
    Oportunidade,
    OportunidadeEvento,
    Proposta,
)
from app.modules.comercial.schemas import AtividadeOut, OportunidadeOut
from app.modules.nucleo.models import CampoCustom, Empresa, Pessoa, Produto

NAO_ENCONTRADA = "Oportunidade não encontrada."


def hoje() -> date:
    return hoje_de_negocio()


# ------------------------------------------------------------------------------------------------ carregar com escopo
def obter(ctx: Contexto, modelo, id_: int, mensagem: str, *, responsavel: str | None = "responsavel_id"):
    """Carrega ou 404. Com escopo "só meus registros", registro de outro responsável também é 404 (não revela)."""
    obj = ctx.db.get(modelo, id_)
    if obj is None:
        raise HTTPException(404, mensagem)
    if responsavel and not ctx.pode_acessar(getattr(obj, responsavel)):
        raise HTTPException(404, mensagem)
    return obj


def obter_oportunidade(ctx: Contexto, id_: int) -> Oportunidade:
    return obter(ctx, Oportunidade, id_, NAO_ENCONTRADA)


def comunicacao_visivel(ctx: Contexto, com: Comunicacao) -> bool:
    """Regra ÚNICA de acesso a uma comunicação (tela Comercial e IA): com "só meus registros", a conversa herda o
    responsável da oportunidade vinculada — sem oportunidade, ou de oportunidade de outro, não é visível."""
    if not ctx.somente_meus_registros():
        return True
    op = ctx.db.get(Oportunidade, com.oportunidade_id) if com.oportunidade_id else None
    return op is not None and op.responsavel_id == ctx.usuario.id


def responsavel_efetivo(ctx: Contexto, responsavel_id: int | None) -> int:
    """Quem tem escopo "só meus registros" só cria registros para si (senão deixaria de enxergá-los)."""
    if ctx.somente_meus_registros():
        return ctx.usuario.id
    if responsavel_id is None:
        return ctx.usuario.id
    u = ctx.db.get(Usuario, responsavel_id)
    if u is None or not u.ativo:
        raise RegraViolada("Responsável não encontrado ou inativo.")
    return responsavel_id


def conferir_empresa(db: Session, empresa_id: int | None) -> None:
    if empresa_id is not None and db.get(Empresa, empresa_id) is None:
        raise RegraViolada("Empresa não encontrada.")


def conferir_oportunidade_vinculo(ctx: Contexto, oportunidade_id: int | None) -> Oportunidade | None:
    if oportunidade_id is None:
        return None
    op = ctx.db.get(Oportunidade, oportunidade_id)
    if op is None or not ctx.pode_acessar(op.responsavel_id):
        raise RegraViolada("Oportunidade não encontrada.")
    return op


def resolver_empresa(ctx: Contexto, *, empresa_id: int | None, empresa_nome: str | None,
                     responsavel_id: int) -> Empresa | None:
    """Empresa pelo id, ou pelo NOME (nasce dentro da oportunidade como prospect se ainda não existe).
    Mesmo nome normalizado = mesma empresa (cadastro único)."""
    if empresa_id is not None:
        e = ctx.db.get(Empresa, empresa_id)
        if e is None:
            raise RegraViolada("Empresa não encontrada.")
        return e
    if empresa_nome is None or not empresa_nome.strip():
        return None
    nome = validar_nome(empresa_nome, o_que="o nome da empresa")
    e = ctx.db.scalar(select(Empresa).where(Empresa.nome_chave == chave_de_nome(nome)))
    if e is not None:
        return e
    e = Empresa(nome=nome, responsavel_id=responsavel_id, papel_prospect=True, campos_custom={},
                origem="Oportunidade")
    ctx.db.add(e)
    ctx.db.flush()
    ctx.auditar("empresa.criar", "empresa", e.id, descricao=f"Empresa criada na oportunidade: {nome}",
                depois={"nome": nome, "papeis": ["prospect"]})
    return e


def registrar_evento(db: Session, oportunidade_id: int, tipo: str, texto: str, usuario_id: int | None) -> None:
    """Histórico compartilhado (o motor de automações lê esta tabela). `tipo` ∈ regras.TIPOS_EVENTO."""
    db.add(OportunidadeEvento(oportunidade_id=oportunidade_id, tipo=regras.validar_tipo_evento(tipo),
                              texto=texto[:4000], usuario_id=usuario_id))


def etapas_do_funil(db: Session, funil_id: int) -> list[Etapa]:
    return list(db.scalars(select(Etapa).where(Etapa.funil_id == funil_id).order_by(Etapa.ordem, Etapa.id)))


def primeira_etapa(db: Session, funil_id: int) -> Etapa:
    etapas = etapas_do_funil(db, funil_id)
    if not etapas:
        raise RegraViolada("O funil não tem etapas. Configure as etapas antes de criar oportunidades.")
    return etapas[0]


def conferir_campos_exigidos(db: Session, op: Oportunidade, etapa: Etapa) -> None:
    """Campo personalizado exigido na etapa precisa estar preenchido antes de entrar nela."""
    exigidos = db.scalars(select(CampoCustom).where(
        CampoCustom.objeto == "oportunidade", CampoCustom.exigido_na_etapa_id == etapa.id,
        CampoCustom.arquivado.is_(False)))
    for c in exigidos:
        if (op.campos_custom or {}).get(c.slug) in (None, ""):
            raise RegraViolada(f"Preencha {c.nome} antes de mover para {etapa.nome}.")


# ------------------------------------------------------------------------------------------------ nomes em lote
def _nomes(db: Session, modelo, ids: Iterable[int | None], campo: str = "nome") -> dict[int, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    col = getattr(modelo, campo)
    return dict(db.execute(select(modelo.id, col).where(modelo.id.in_(ids))).all())


def serializar_oportunidades(db: Session, ops: list[Oportunidade], ref: date | None = None) -> list[OportunidadeOut]:
    ref = ref or hoje()
    empresas = _nomes(db, Empresa, (o.empresa_id for o in ops))
    pessoas = _nomes(db, Pessoa, (o.contato_id for o in ops))
    usuarios = _nomes(db, Usuario, (o.responsavel_id for o in ops))
    funis = _nomes(db, Funil, (o.funil_id for o in ops))
    etapa_ids = {o.etapa_id for o in ops if o.etapa_id}
    etapas = {e.id: e for e in db.scalars(select(Etapa).where(Etapa.id.in_(etapa_ids)))} if etapa_ids else {}
    out = []
    for o in ops:
        e = etapas.get(o.etapa_id)
        aberta = o.resultado == "aberta"
        out.append(OportunidadeOut.model_validate(o).model_copy(update={
            "funil_nome": funis.get(o.funil_id),
            "etapa_nome": e.nome if e else None,
            "etapa_probabilidade": e.probabilidade if e else None,
            "empresa_nome": empresas.get(o.empresa_id),
            "contato_nome": pessoas.get(o.contato_id),
            "responsavel_nome": usuarios.get(o.responsavel_id),
            "dias_na_etapa": dias_na_etapa(o.entrou_etapa_em, ref) if aberta else 0,
            "alem_do_limite": aberta and e is not None and alem_do_limite(o.entrou_etapa_em, e.limite_dias, ref),
            "interesse": (o.campos_custom or {}).get("interesse"),
            "campos_custom": o.campos_custom or {},
        }))
    return out


def serializar_atividades(db: Session, ats: list[Atividade], ref: date | None = None) -> list[AtividadeOut]:
    ref = ref or hoje()
    empresas = _nomes(db, Empresa, (a.empresa_id for a in ats))
    usuarios = _nomes(db, Usuario, (a.responsavel_id for a in ats))
    ops = _nomes(db, Oportunidade, (a.oportunidade_id for a in ats), "titulo")
    return [AtividadeOut.model_validate(a).model_copy(update={
        "empresa_nome": empresas.get(a.empresa_id),
        "responsavel_nome": usuarios.get(a.responsavel_id),
        "oportunidade_titulo": ops.get(a.oportunidade_id),
        "atrasada": atrasada(prazo=a.prazo, status=a.status, hoje=ref),
    }) for a in ats]


def nomes_empresas(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Empresa, ids)


def nomes_usuarios(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Usuario, ids)


def nomes_oportunidades(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Oportunidade, ids, "titulo")


def nomes_produtos(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Produto, ids)


def nomes_funis(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Funil, ids)


def nomes_etapas(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    return _nomes(db, Etapa, ids)


# ------------------------------------------------------------------------------------------------ contexto da negociação
def contexto_negociacao(db: Session, op: Oportunidade) -> dict[str, Any]:
    """Contexto determinístico para o drawer: última comunicação vinculada (análise, se houver) + próxima ação.
    Sem probabilidade preditiva."""
    limite = "Leitura dos registros vinculados; hipótese de fechamento, sem probabilidade preditiva."
    c = db.scalar(select(Comunicacao).where(Comunicacao.oportunidade_id == op.id)
                  .order_by(Comunicacao.data.desc().nullslast(), Comunicacao.id.desc()).limit(1))
    if c is None:
        texto = (f"Próxima ação registrada: {op.proxima_acao}." if op.proxima_acao
                 else "Sem comunicações vinculadas e sem próxima ação registrada.")
        return {"texto": texto, "fonte": None, "limite": limite + " Importe notas ou mensagens para enriquecer."}
    a = c.analise or {}
    partes = []
    if a.get("objecoes"):
        partes.append(f"Objeção: {a['objecoes'][0]}")
    if a.get("compromissos"):
        partes.append(f"Compromisso: {a['compromissos'][0]}")
    if not partes:
        trecho = c.conteudo.strip().replace("\n", " ")
        partes.append(trecho[:280] + ("…" if len(trecho) > 280 else ""))
    if op.proxima_acao:
        partes.append(f"Próxima ação: {op.proxima_acao}")
    canal = {"reuniao": "reunião", "email": "e-mail", "whatsapp": "WhatsApp", "notas": "notas"}.get(c.canal, c.canal)
    data_txt = c.data.strftime("%d/%m/%Y") if c.data else "sem data"
    return {"texto": " · ".join(partes), "fonte": f"{canal} · {c.titulo or 'Comunicação'} · {data_txt}",
            "limite": limite}


def contagens_oportunidade(db: Session, op_id: int) -> dict[str, int]:
    return {
        "atividades_pendentes": db.scalar(select(func.count()).select_from(Atividade).where(
            Atividade.oportunidade_id == op_id, Atividade.status == "pendente")) or 0,
        "comunicacoes": db.scalar(select(func.count()).select_from(Comunicacao).where(
            Comunicacao.oportunidade_id == op_id)) or 0,
        "propostas": db.scalar(select(func.count()).select_from(Proposta).where(
            Proposta.oportunidade_id == op_id)) or 0,
    }


# ------------------------------------------------------------------------------------------------ cálculos
def soma(valores: Iterable[Decimal | None]) -> Decimal:
    return sum((v or ZERO for v in valores), ZERO)


def no_periodo(d: date | datetime | None, inicio: date, fim: date) -> bool:
    if d is None:
        return False
    if isinstance(d, datetime):
        d = d.date()
    return inicio <= d <= fim


def oportunidades_abertas_resumo(db: Session, funil_id: int | None = None) -> list[Oportunidade]:
    q = select(Oportunidade).where(Oportunidade.resultado == "aberta")
    if funil_id:
        q = q.where(Oportunidade.funil_id == funil_id)
    return list(db.scalars(q))
