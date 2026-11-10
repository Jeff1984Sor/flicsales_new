"""Trabalho do dia: Hoje, Atividades e Comunicações."""

from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, or_, select

from app.core import audit, ia
from app.core.db import agora
from app.core.deps import Ctx
from app.domain import RegraViolada
from app.domain.atividade import validar_atividade, validar_conclusao
from app.domain.leitura import AtividadeResumo, OportunidadeResumo, TituloResumo, ler_momento
from app.domain.titulos import EM_ABERTO
from app.modules.comercial import regras
from app.modules.comercial import servico as sv
from app.modules.comercial.models import Atividade, Comunicacao, Etapa, Funil, Oportunidade
from app.modules.comercial.schemas import (
    AnaliseIn,
    AtividadeAtualizar,
    AtividadeCriar,
    AtividadeOut,
    ComunicacaoCriar,
    ComunicacaoOut,
    ConcluirIn,
    HojeOut,
    RascunhoOut,
)
from app.modules.financeiro.models import Titulo
from app.modules.nucleo.models import Empresa, Pessoa

router = APIRouter(tags=["comercial · trabalho"])

TIPO_ROTULO = {"tarefa": "Tarefa", "email": "E-mail", "ligacao": "Ligação", "whatsapp": "WhatsApp", "reuniao": "Reunião"}


# ------------------------------------------------------------------------------------------------ atividades
@router.get("/atividades", response_model=list[AtividadeOut])
def listar_atividades(ctx: Ctx, tipo: str | None = None, status: str | None = None, q: str | None = None,
                      oportunidade_id: int | None = None, empresa_id: int | None = None,
                      responsavel_id: int | None = None, de: date | None = None, ate: date | None = None,
                      atrasadas: bool = False):
    consulta = ctx.filtrar_meus(select(Atividade), Atividade.responsavel_id)
    if tipo:
        consulta = consulta.where(Atividade.tipo == tipo)
    if status in ("pendente", "concluida"):
        consulta = consulta.where(Atividade.status == status)
    if oportunidade_id:
        consulta = consulta.where(Atividade.oportunidade_id == oportunidade_id)
    if empresa_id:
        consulta = consulta.where(Atividade.empresa_id == empresa_id)
    if responsavel_id:
        consulta = consulta.where(Atividade.responsavel_id == responsavel_id)
    if de:
        consulta = consulta.where(Atividade.prazo >= de)
    if ate:
        consulta = consulta.where(Atividade.prazo <= ate)
    if atrasadas:
        consulta = consulta.where(Atividade.status == "pendente", Atividade.prazo < sv.hoje())
    if q and q.strip():
        termo = f"%{q.strip().lower()}%"
        consulta = consulta.outerjoin(Empresa, Empresa.id == Atividade.empresa_id).where(or_(
            func.lower(Atividade.assunto).like(termo), func.lower(Empresa.nome).like(termo)))
    ats = list(ctx.db.scalars(consulta.order_by(Atividade.status.desc(), Atividade.prazo, Atividade.hora_inicio,
                                                Atividade.id).limit(500)))
    return sv.serializar_atividades(ctx.db, ats)


def _vinculos(ctx: Ctx, empresa_id: int | None, oportunidade_id: int | None) -> tuple[int | None, Oportunidade | None]:
    op = sv.conferir_oportunidade_vinculo(ctx, oportunidade_id)
    sv.conferir_empresa(ctx.db, empresa_id)
    if empresa_id is None and op is not None:
        empresa_id = op.empresa_id
    return empresa_id, op


def _quando(a: Atividade) -> str:
    hora = f" às {a.hora_inicio.strftime('%H:%M')}" if a.hora_inicio else ""
    return f"{a.prazo.strftime('%d/%m/%Y')}{hora}"


@router.get("/atividades/{atividade_id}", response_model=AtividadeOut)
def obter_atividade(atividade_id: int, ctx: Ctx):
    a = sv.obter(ctx, Atividade, atividade_id, "Atividade não encontrada.")
    return sv.serializar_atividades(ctx.db, [a])[0]


@router.post("/atividades", response_model=AtividadeOut, status_code=201)
def criar_atividade(dados: AtividadeCriar, ctx: Ctx):
    validar_atividade(assunto=dados.assunto, tipo=dados.tipo, prazo=dados.prazo, hora_inicio=dados.hora_inicio,
                      hora_fim=dados.hora_fim)
    empresa_id, op = _vinculos(ctx, dados.empresa_id, dados.oportunidade_id)
    a = Atividade(**dados.model_dump(exclude={"responsavel_id", "empresa_id", "fuso"}),
                  responsavel_id=sv.responsavel_efetivo(ctx, dados.responsavel_id), empresa_id=empresa_id,
                  fuso=dados.fuso or "America/Sao_Paulo", status="pendente")
    a.assunto = a.assunto.strip()
    ctx.db.add(a)
    ctx.db.flush()
    if op is not None and a.tipo == "reuniao":
        sv.registrar_evento(ctx.db, op.id, "reuniao", f"Reunião vinculada: {a.assunto} · {_quando(a)}", ctx.usuario.id)
    ctx.auditar("atividade.criar", "atividade", a.id, descricao=f"{TIPO_ROTULO[a.tipo]} / {a.assunto}",
                depois=audit.snapshot(a))
    ctx.db.commit()
    return sv.serializar_atividades(ctx.db, [a])[0]


@router.patch("/atividades/{atividade_id}", response_model=AtividadeOut)
def atualizar_atividade(atividade_id: int, dados: AtividadeAtualizar, ctx: Ctx):
    a = sv.obter(ctx, Atividade, atividade_id, "Atividade não encontrada.")
    antes = audit.snapshot(a)
    d = dados.model_dump(exclude_unset=True)
    validar_atividade(assunto=d.get("assunto", a.assunto), tipo=d.get("tipo") or a.tipo,
                      prazo=d.get("prazo", a.prazo), hora_inicio=d.get("hora_inicio", a.hora_inicio),
                      hora_fim=d.get("hora_fim", a.hora_fim))
    if "oportunidade_id" in d or "empresa_id" in d:
        empresa_id, _ = _vinculos(ctx, d.get("empresa_id", a.empresa_id), d.get("oportunidade_id", a.oportunidade_id))
        d["empresa_id"] = empresa_id
    if "responsavel_id" in d:
        if d["responsavel_id"] is None or ctx.somente_meus_registros():
            d.pop("responsavel_id")
        else:
            d["responsavel_id"] = sv.responsavel_efetivo(ctx, d["responsavel_id"])
    if "fuso" in d and not d["fuso"]:
        d.pop("fuso")
    for k, v in d.items():
        setattr(a, k, v.strip() if k == "assunto" and v else v)
    a_, d_ = audit.diff(antes, audit.snapshot(a))
    ctx.auditar("atividade.atualizar", "atividade", a.id, descricao=a.assunto, antes=a_, depois=d_)
    ctx.db.commit()
    return sv.serializar_atividades(ctx.db, [a])[0]


@router.post("/atividades/{atividade_id}/concluir", response_model=AtividadeOut)
def concluir_atividade(atividade_id: int, dados: ConcluirIn, ctx: Ctx):
    a = sv.obter(ctx, Atividade, atividade_id, "Atividade não encontrada.")
    antes = audit.snapshot(a)
    a.status = validar_conclusao(a.status)
    a.concluida_em = agora()
    if dados.resultado and dados.resultado.strip():
        a.resultado = dados.resultado.strip()
    if a.oportunidade_id:
        tipo, texto = (("reuniao", f"Reunião encerrada: {a.assunto}") if a.tipo == "reuniao"
                       else ("nota", f"{TIPO_ROTULO[a.tipo]} concluída: {a.assunto}"))
        if a.resultado:
            texto += f" · {a.resultado}"
        sv.registrar_evento(ctx.db, a.oportunidade_id, tipo, texto, ctx.usuario.id)
    a_, d_ = audit.diff(antes, audit.snapshot(a))
    ctx.auditar("atividade.concluir", "atividade", a.id, descricao=a.assunto, antes=a_, depois=d_)
    ctx.db.commit()
    return sv.serializar_atividades(ctx.db, [a])[0]


# ------------------------------------------------------------------------------------------------ comunicações
def _filtrar_comunicacoes(ctx: Ctx, consulta):
    """Escopo "só meus registros": só as conversas vinculadas às próprias oportunidades."""
    if not ctx.somente_meus_registros():
        return consulta
    return consulta.join(Oportunidade, Oportunidade.id == Comunicacao.oportunidade_id).where(
        Oportunidade.responsavel_id == ctx.usuario.id)


def _obter_comunicacao(ctx: Ctx, cid: int) -> Comunicacao:
    c = ctx.db.get(Comunicacao, cid)
    nao = HTTPException(404, "Comunicação não encontrada.")
    if c is None or not sv.comunicacao_visivel(ctx, c):
        raise nao
    return c


def _serializar_comunicacoes(ctx: Ctx, cs: list[Comunicacao]) -> list[ComunicacaoOut]:
    empresas = sv.nomes_empresas(ctx.db, (c.empresa_id for c in cs))
    ops = sv.nomes_oportunidades(ctx.db, (c.oportunidade_id for c in cs))
    return [ComunicacaoOut.model_validate(c).model_copy(update={
        "empresa_nome": empresas.get(c.empresa_id), "oportunidade_titulo": ops.get(c.oportunidade_id)}) for c in cs]


@router.get("/comunicacoes", response_model=list[ComunicacaoOut])
def listar_comunicacoes(ctx: Ctx, oportunidade_id: int | None = None, empresa_id: int | None = None,
                        canal: str | None = None, q: str | None = None):
    consulta = _filtrar_comunicacoes(ctx, select(Comunicacao))
    if oportunidade_id:
        consulta = consulta.where(Comunicacao.oportunidade_id == oportunidade_id)
    if empresa_id:
        consulta = consulta.where(Comunicacao.empresa_id == empresa_id)
    if canal:
        consulta = consulta.where(Comunicacao.canal == canal)
    if q and q.strip():
        termo = f"%{q.strip().lower()}%"
        consulta = consulta.where(or_(func.lower(Comunicacao.titulo).like(termo),
                                      func.lower(Comunicacao.conteudo).like(termo)))
    cs = list(ctx.db.scalars(consulta.order_by(Comunicacao.data.desc().nullslast(), Comunicacao.id.desc()).limit(300)))
    return _serializar_comunicacoes(ctx, cs)


@router.get("/comunicacoes/{comunicacao_id}", response_model=ComunicacaoOut)
def obter_comunicacao(comunicacao_id: int, ctx: Ctx):
    return _serializar_comunicacoes(ctx, [_obter_comunicacao(ctx, comunicacao_id)])[0]


@router.post("/comunicacoes", response_model=ComunicacaoOut, status_code=201)
def importar_comunicacao(dados: ComunicacaoCriar, ctx: Ctx):
    """Importa texto colado (notas, e-mail, WhatsApp). O conteúdo é DADO, nunca instrução para a IA."""
    conteudo = dados.conteudo.strip()
    if not conteudo:
        raise RegraViolada("Cole o conteúdo da conversa para importar.")
    if ctx.somente_meus_registros() and dados.oportunidade_id is None:
        raise RegraViolada("Vincule a comunicação a uma das suas oportunidades.")
    empresa_id, op = _vinculos(ctx, dados.empresa_id, dados.oportunidade_id)
    c = Comunicacao(canal=dados.canal, titulo=(dados.titulo or "").strip() or None, conteudo=conteudo,
                    data=dados.data or sv.hoje(), empresa_id=empresa_id, oportunidade_id=dados.oportunidade_id)
    ctx.db.add(c)
    ctx.db.flush()
    if op is not None:
        sv.registrar_evento(ctx.db, op.id, "nota", f"Comunicação vinculada ({dados.canal}): {c.titulo or 'sem título'}",
                            ctx.usuario.id)
    ctx.auditar("comunicacao.importar", "comunicacao", c.id, descricao=c.titulo or dados.canal,
                depois={"canal": c.canal, "titulo": c.titulo, "oportunidade_id": c.oportunidade_id})
    ctx.db.commit()
    return _serializar_comunicacoes(ctx, [c])[0]


@router.put("/comunicacoes/{comunicacao_id}/analise", response_model=ComunicacaoOut)
def guardar_analise(comunicacao_id: int, dados: AnaliseIn, ctx: Ctx):
    """Guarda a análise (necessidades, objeções, compromissos, citações, limites) vinda da Orquestração."""
    c = _obter_comunicacao(ctx, comunicacao_id)
    antes = c.analise
    c.analise = regras.validar_analise(dados.analise)
    c.analisada_em = agora()
    ctx.auditar("comunicacao.analise", "comunicacao", c.id, descricao=c.titulo, antes={"analise": antes},
                depois={"analise": c.analise})
    ctx.db.commit()
    return _serializar_comunicacoes(ctx, [c])[0]


@router.post("/comunicacoes/{comunicacao_id}/resposta", response_model=RascunhoOut)
def preparar_resposta(comunicacao_id: int, ctx: Ctx):
    """Rascunho de resposta a partir da análise. Nada é enviado nem gravado."""
    c = _obter_comunicacao(ctx, comunicacao_id)
    contato = None
    if c.oportunidade_id:
        op = ctx.db.get(Oportunidade, c.oportunidade_id)
        if op and op.contato_id:
            p = ctx.db.get(Pessoa, op.contato_id)
            contato = p.nome if p else None
    return RascunhoOut(rascunho=regras.rascunho_resposta(contato=contato, analise=c.analise),
                       aviso="Rascunho para revisão. Nenhum envio é feito: o envio exige um canal conectado e autorizado.")


# ------------------------------------------------------------------------------------------------ hoje
@router.get("/hoje", response_model=HojeOut)
def hoje_comercial(ctx: Ctx, funil_id: int | None = None):
    """Painéis do Hoje + Leitura do momento determinística (funciona sem IA)."""
    db, ref = ctx.db, sv.hoje()
    abertas = list(db.scalars(ctx.filtrar_meus(select(Oportunidade).where(Oportunidade.resultado == "aberta"),
                                               Oportunidade.responsavel_id)))
    etapas = {e.id: e for e in db.scalars(select(Etapa))}
    funil = db.get(Funil, funil_id) if funil_id else db.scalar(
        select(Funil).where(Funil.ativo.is_(True)).order_by(Funil.id).limit(1))

    # "Em negociação" = abertas na última etapa de cada funil
    ultima_por_funil: dict[int, int] = {}
    for e in sorted(etapas.values(), key=lambda e: (e.funil_id, e.ordem, e.id)):
        ultima_por_funil[e.funil_id] = e.id
    negociacao = [o for o in abertas if o.etapa_id and ultima_por_funil.get(o.funil_id) == o.etapa_id]
    nome_negociacao = etapas[ultima_por_funil[funil.id]].nome if funil and funil.id in ultima_por_funil else None

    pendentes = list(db.scalars(ctx.filtrar_meus(
        select(Atividade).where(Atividade.status == "pendente"), Atividade.responsavel_id)
        .order_by(Atividade.prazo, Atividade.hora_inicio, Atividade.id)))
    do_dia = [a for a in pendentes if a.prazo <= ref]
    agenda = [a for a in pendentes if a.prazo == ref]
    atencao = (do_dia + [a for a in pendentes if a.prazo > ref])[:6]

    minhas = select(Oportunidade.id)
    if ctx.somente_meus_registros():
        minhas = minhas.where(Oportunidade.responsavel_id == ctx.usuario.id)
    recebiveis = db.scalar(select(func.count()).select_from(Titulo).where(
        Titulo.origem_oportunidade_id.in_(minhas), Titulo.status != "cancelado")) or 0

    saude = []
    if funil:
        for e in sv.etapas_do_funil(db, funil.id):
            da_etapa = [o for o in abertas if o.etapa_id == e.id]
            saude.append({"etapa_id": e.id, "etapa": e.nome, "quantidade": len(da_etapa),
                          "valor": sv.soma(o.valor_unico for o in da_etapa), "probabilidade": e.probabilidade})

    # Leitura do momento (regras): vencidos (se o perfil vê o Financeiro), sem próxima ação, além do limite, atrasadas
    empresas = sv.nomes_empresas(db, [o.empresa_id for o in abertas] + [a.empresa_id for a in pendentes])
    titulos: list[TituloResumo] = []
    if ctx.pode("financeiro.titulos.ver") and not ctx.somente_meus_registros():
        vencidos = list(db.scalars(select(Titulo).where(
            Titulo.direcao == "receber", Titulo.status.in_(EM_ABERTO), Titulo.vencimento < ref)))
        nomes_t = sv.nomes_empresas(db, (t.empresa_id for t in vencidos))
        titulos = [TituloResumo(id=t.id, empresa=nomes_t.get(t.empresa_id, "—"), descricao=t.descricao,
                                direcao=t.direcao, status=t.status, vencimento=t.vencimento, saldo=t.saldo)
                   for t in vencidos]
    leitura = ler_momento(
        hoje=ref, titulos=titulos,
        oportunidades=[OportunidadeResumo(
            id=o.id, titulo=o.titulo, empresa=empresas.get(o.empresa_id),
            etapa=etapas[o.etapa_id].nome if o.etapa_id in etapas else None, valor=o.valor_unico,
            proxima_acao=o.proxima_acao, entrou_etapa_em=o.entrou_etapa_em,
            limite_dias=etapas[o.etapa_id].limite_dias if o.etapa_id in etapas else None) for o in abertas],
        atividades=[AtividadeResumo(id=a.id, assunto=a.assunto, prazo=a.prazo, status=a.status,
                                    empresa=empresas.get(a.empresa_id)) for a in pendentes],
        ia_ligada=ia.ligada(db))
    return HojeOut(
        nome=ctx.usuario.nome, hoje=ref,
        pipeline_aberto=sv.soma(o.valor_unico for o in abertas), oportunidades_ativas=len(abertas),
        em_negociacao=sv.soma(o.valor_unico for o in negociacao), em_negociacao_qtd=len(negociacao),
        em_negociacao_etapa=nome_negociacao, tarefas_do_dia=len(do_dia), recebiveis_vinculados=recebiveis,
        atencao=sv.serializar_atividades(db, atencao, ref), agenda=sv.serializar_atividades(db, agenda, ref),
        agenda_conectada=False, saude_funil=saude, funil_nome=funil.nome if funil else None, leitura=leitura,
        ia_ligada=ia.ligada(db))
