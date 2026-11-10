"""IA unificada: leitura do momento, perguntar, análise de comunicação e execução de ação sugerida (após revisão)."""

from datetime import date, time

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select

from app.core import audit
from app.core.db import hoje
from app.core.deps import Ctx
from app.domain import RegraViolada
from app.domain.atividade import validar_atividade
from app.modules.comercial.models import Atividade, Oportunidade
from app.modules.nucleo.models import Empresa
from app.modules.orquestracao.ia import gateway, servico
from app.modules.orquestracao.ia.formato import TIPOS_ACAO_PERMITIDOS
from app.modules.orquestracao.models import IaConversa, IaMensagem
from app.modules.orquestracao.schemas import (
    AcaoExecutadaOut,
    AcaoIn,
    AnaliseOut,
    ConversaOut,
    CriarAtividadePayload,
    PerguntaIn,
    RespostaOut,
)

router = APIRouter()


@router.get("/leitura", response_model=RespostaOut)
def leitura(ctx: Ctx, modulo: str = Query("comercial", pattern="^(comercial|financeiro|nucleo)$")):
    """Leitura do momento: IA se ligada; senão regras determinísticas (app.domain.leitura). Mesmo formato."""
    return servico.leitura_do_momento(ctx, modulo, hoje())


@router.get("/ia/estado")
def estado_ia(ctx: Ctx):
    provedor, modelo = gateway.descricao(ctx.db)
    ligada = gateway.ligada(ctx.db)
    return {"ligada": ligada, "provedor": provedor if ligada else None, "modelo": modelo if ligada else None,
            "configurar_em": "/configuracoes/ia"}


@router.post("/ia/perguntar", response_model=RespostaOut)
def perguntar(dados: PerguntaIn, ctx: Ctx):
    registro = (dados.registro.tipo, dados.registro.id) if dados.registro else None
    return servico.perguntar(ctx, pergunta=dados.pergunta, escopo=dados.escopo, modulo=dados.modulo, tela=dados.tela,
                             registro=registro, conversa_id=dados.conversa_id, hoje=hoje())


@router.get("/ia/conversas", response_model=list[ConversaOut])
def conversas(ctx: Ctx):
    q = select(IaConversa).where(IaConversa.usuario_id == ctx.usuario.id).order_by(IaConversa.id.desc()).limit(30)
    return [ConversaOut(id=c.id, escopo=c.escopo, modulo=c.modulo, tela=c.tela, titulo=c.titulo, criado_em=c.criado_em)
            for c in ctx.db.scalars(q)]


@router.get("/ia/conversas/{conversa_id}/mensagens")
def mensagens(conversa_id: int, ctx: Ctx):
    c = ctx.db.get(IaConversa, conversa_id)
    if c is None or c.usuario_id != ctx.usuario.id:
        raise HTTPException(404, "Conversa não encontrada.")
    return [{"id": m.id, "quando": m.quando, "pergunta": m.pergunta, "resposta": m.resposta, "origem": m.origem}
            for m in ctx.db.scalars(select(IaMensagem).where(IaMensagem.conversa_id == c.id).order_by(IaMensagem.id))]


@router.post("/ia/comunicacoes/{comunicacao_id}/analisar", response_model=AnaliseOut)
def analisar_comunicacao(comunicacao_id: int, ctx: Ctx):
    ctx.exigir("orquestracao.ia.ver")
    return servico.analisar_comunicacao(ctx, comunicacao_id)


def _hora(v: str | None) -> time | None:
    if not v:
        return None
    try:
        return time.fromisoformat(v)
    except ValueError:
        raise RegraViolada("Horário inválido (use HH:MM).") from None


@router.post("/acoes/executar", response_model=AcaoExecutadaOut)
def executar_acao(dados: AcaoIn, ctx: Ctx):
    """Executa uma ação SUGERIDA depois da revisão do usuário. Só tipos permitidos (`criar_atividade`)."""
    if dados.tipo not in TIPOS_ACAO_PERMITIDOS:
        raise HTTPException(400, "Ação não permitida pelo assistente. Faça esta mudança na tela do módulo.")
    ctx.exigir("comercial.atividades.editar")
    try:
        p = CriarAtividadePayload.model_validate(dados.payload)
    except ValidationError:
        raise HTTPException(400, "Revise a sugestão: informe assunto, tipo e prazo válidos.") from None
    empresa_id = p.empresa_id
    if p.oportunidade_id is not None:
        o = ctx.db.get(Oportunidade, p.oportunidade_id)
        if o is None or not ctx.pode_acessar(o.responsavel_id):
            raise HTTPException(404, "Oportunidade não encontrada.")
        empresa_id = empresa_id or o.empresa_id
    if empresa_id is not None and ctx.db.get(Empresa, empresa_id) is None:
        raise HTTPException(404, "Empresa não encontrada.")
    prazo: date = p.prazo or hoje()
    inicio, fim = _hora(p.hora_inicio), _hora(p.hora_fim)
    validar_atividade(assunto=p.assunto, tipo=p.tipo, prazo=prazo, hora_inicio=inicio, hora_fim=fim)
    a = Atividade(assunto=p.assunto, tipo=p.tipo, responsavel_id=ctx.usuario.id, empresa_id=empresa_id,
                  oportunidade_id=p.oportunidade_id, prazo=prazo, hora_inicio=inicio, hora_fim=fim,
                  objetivo=p.objetivo, origem="ia")
    ctx.db.add(a)
    ctx.db.flush()
    ctx.auditar("atividade.criar", "atividade", a.id, descricao="Sugestão do assistente criada após revisão do usuário",
                depois=audit.snapshot(a))
    ctx.db.commit()
    return AcaoExecutadaOut(tipo=dados.tipo, registro={"tipo": "atividade", "id": a.id, "assunto": a.assunto,
                                                       "prazo": a.prazo.isoformat()},
                            mensagem="Atividade criada após sua revisão.")
