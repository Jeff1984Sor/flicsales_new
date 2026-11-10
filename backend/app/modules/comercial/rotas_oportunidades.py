"""Funis, etapas e oportunidades (Kanban, mover, editar, ganhar, perder, reabrir, histórico)."""

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from app.core import audit
from app.core.deps import Ctx
from app.core.models import Usuario
from app.domain import RegraViolada
from app.domain.dinheiro import formatar_brl, positivo
from app.domain.fechamento import CONDICOES, numero_de_parcelas, validar_ganho
from app.domain.funil import (
    validar_alteracao_valor,
    validar_etapas,
    validar_limite_dias,
    validar_perda,
    validar_probabilidade,
    validar_valores,
)
from app.modules.comercial import regras
from app.modules.comercial import servico as sv
from app.modules.comercial.models import Etapa, Funil, Oportunidade, OportunidadeEvento, Playbook
from app.modules.comercial.schemas import (
    EtapaOut,
    EtapasConfig,
    EventoOut,
    FunilAtualizar,
    FunilCriar,
    FunilOut,
    GanharIn,
    GanhoOut,
    MoverIn,
    NotaIn,
    OpcaoCampo,
    OpcaoOportunidade,
    OpcaoPessoa,
    OpcaoProduto,
    OpcaoSimples,
    OpcoesComerciais,
    OportunidadeAtualizar,
    OportunidadeCriar,
    OportunidadeDetalhe,
    OportunidadeOut,
    PerderIn,
    RecebivelOut,
)
from app.modules.financeiro.servico import preparar_recebiveis_do_ganho, recebiveis_da_oportunidade
from app.modules.nucleo.models import CampoCustom, Empresa, Pessoa, Produto

router = APIRouter(tags=["comercial · oportunidades"])

INTERESSE_PADRAO = ["Baixo", "Médio", "Alto"]


# ------------------------------------------------------------------------------------------------ funis
def _funil_out(db, f: Funil) -> FunilOut:
    return FunilOut(id=f.id, nome=f.nome, ativo=f.ativo,
                    etapas=[EtapaOut.model_validate(e) for e in sv.etapas_do_funil(db, f.id)])


@router.get("/funis", response_model=list[FunilOut])
def listar_funis(ctx: Ctx, incluir_inativos: bool = False):
    q = select(Funil).order_by(Funil.id)
    if not incluir_inativos:
        q = q.where(Funil.ativo.is_(True))
    return [_funil_out(ctx.db, f) for f in ctx.db.scalars(q)]


def _conferir_nome_funil(ctx: Ctx, nome: str, outro_id: int | None = None) -> str:
    nome = " ".join(nome.split())
    q = select(Funil.id).where(func.lower(Funil.nome) == nome.lower())
    if outro_id:
        q = q.where(Funil.id != outro_id)
    if ctx.db.scalar(q):
        raise RegraViolada("Já existe um funil com este nome.")
    return nome


@router.post("/funis", response_model=FunilOut, status_code=201)
def criar_funil(dados: FunilCriar, ctx: Ctx):
    nomes = validar_etapas(dados.etapas)
    nome = _conferir_nome_funil(ctx, dados.nome)
    f = Funil(nome=nome)
    ctx.db.add(f)
    ctx.db.flush()
    for i, (n, p) in enumerate(zip(nomes, regras.probabilidades_padrao(len(nomes)), strict=True), start=1):
        ctx.db.add(Etapa(funil_id=f.id, nome=n, ordem=i, probabilidade=p, limite_dias=7,
                         criterios="Título e responsável"))
    ctx.auditar("funil.criar", "funil", f.id, descricao=nome, depois={"nome": nome, "etapas": nomes})
    ctx.db.commit()
    return _funil_out(ctx.db, f)


@router.patch("/funis/{funil_id}", response_model=FunilOut)
def atualizar_funil(funil_id: int, dados: FunilAtualizar, ctx: Ctx):
    f = sv.obter(ctx, Funil, funil_id, "Funil não encontrado.", responsavel=None)
    antes = audit.snapshot(f)
    d = dados.model_dump(exclude_unset=True)
    if d.get("nome"):
        f.nome = _conferir_nome_funil(ctx, d["nome"], f.id)
    if d.get("ativo") is not None:
        f.ativo = d["ativo"]
    a, dd = audit.diff(antes, audit.snapshot(f))
    ctx.auditar("funil.atualizar", "funil", f.id, descricao=f.nome, antes=a, depois=dd)
    ctx.db.commit()
    return _funil_out(ctx.db, f)


@router.put("/funis/{funil_id}/etapas", response_model=FunilOut)
def configurar_etapas(funil_id: int, dados: EtapasConfig, ctx: Ctx):
    """Configura etapas (probabilidade, limite de dias, critérios), na ordem enviada. Etapa com uso não é removida."""
    f = sv.obter(ctx, Funil, funil_id, "Funil não encontrado.", responsavel=None)
    nomes = validar_etapas([e.nome for e in dados.etapas])
    atuais = {e.id: e for e in sv.etapas_do_funil(ctx.db, f.id)}
    antes = [{"nome": e.nome, "probabilidade": e.probabilidade, "limite_dias": e.limite_dias} for e in atuais.values()]
    enviados = {e.id for e in dados.etapas if e.id}
    if enviados - set(atuais):
        raise RegraViolada("Etapa não pertence a este funil.")
    for eid, e in atuais.items():
        if eid in enviados:
            continue
        em_uso = (ctx.db.scalar(select(func.count()).select_from(Oportunidade).where(Oportunidade.etapa_id == eid))
                  or ctx.db.scalar(select(func.count()).select_from(Playbook).where(Playbook.etapa_id == eid))
                  or ctx.db.scalar(select(func.count()).select_from(CampoCustom).where(
                      CampoCustom.exigido_na_etapa_id == eid)))
        if em_uso:
            raise RegraViolada(f"Mova as oportunidades e vínculos da etapa {e.nome} antes de removê-la.")
        ctx.db.delete(e)
    ctx.db.flush()
    # nomes temporários evitam colisão da UNIQUE (funil, nome) ao trocar nomes entre etapas
    for e in atuais.values():
        if e.id in enviados:
            e.nome = f"__tmp_{e.id}"
    ctx.db.flush()
    for ordem, (cfg, nome) in enumerate(zip(dados.etapas, nomes, strict=True), start=1):
        e = atuais[cfg.id] if cfg.id else Etapa(funil_id=f.id)
        e.nome = nome
        e.ordem = ordem
        e.probabilidade = validar_probabilidade(cfg.probabilidade)
        e.limite_dias = validar_limite_dias(cfg.limite_dias)
        e.criterios = (cfg.criterios or "").strip() or None
        if not cfg.id:
            ctx.db.add(e)
    ctx.db.flush()
    depois = [{"nome": e.nome, "probabilidade": e.probabilidade, "limite_dias": e.limite_dias}
              for e in sv.etapas_do_funil(ctx.db, f.id)]
    ctx.auditar("funil.etapas", "funil", f.id, descricao=f"Etapas de {f.nome}", antes={"etapas": antes},
                depois={"etapas": depois})
    ctx.db.commit()
    return _funil_out(ctx.db, f)


# ------------------------------------------------------------------------------------------------ opções para formulários
@router.get("/oportunidades/opcoes", response_model=OpcoesComerciais)
def opcoes(ctx: Ctx):
    db = ctx.db
    campos = list(db.scalars(select(CampoCustom).where(CampoCustom.arquivado.is_(False))
                             .order_by(CampoCustom.objeto, CampoCustom.ordem, CampoCustom.id)))
    interesse = next((c.opcoes for c in campos if c.objeto == "oportunidade" and c.slug == "interesse" and c.opcoes),
                     INTERESSE_PADRAO)
    ops = db.scalars(ctx.filtrar_meus(select(Oportunidade), Oportunidade.responsavel_id)
                     .order_by(Oportunidade.titulo))
    return OpcoesComerciais(
        empresas=[OpcaoSimples(id=i, nome=n) for i, n in db.execute(
            select(Empresa.id, Empresa.nome).where(Empresa.ativo.is_(True)).order_by(Empresa.nome))],
        pessoas=[OpcaoPessoa(id=p.id, nome=p.nome, empresa_id=p.empresa_id) for p in db.scalars(
            select(Pessoa).where(Pessoa.ativo.is_(True)).order_by(Pessoa.nome))],
        produtos=[OpcaoProduto(id=p.id, nome=p.nome, preco_referencia=p.preco_referencia, recorrente=p.recorrente)
                  for p in db.scalars(select(Produto).where(Produto.ativo.is_(True)).order_by(Produto.nome))],
        oportunidades=[OpcaoOportunidade(id=o.id, nome=o.titulo, empresa_id=o.empresa_id, resultado=o.resultado)
                       for o in ops],
        funis=[_funil_out(db, f) for f in db.scalars(select(Funil).where(Funil.ativo.is_(True)).order_by(Funil.id))],
        campos=[OpcaoCampo(id=c.id, nome=c.nome, slug=c.slug, tipo=c.tipo, objeto=c.objeto, opcoes=c.opcoes or [])
                for c in campos],
        condicoes_ganho=list(CONDICOES),
        interesse=list(interesse),
    )


# ------------------------------------------------------------------------------------------------ oportunidades
@router.get("/oportunidades", response_model=list[OportunidadeOut])
def listar(ctx: Ctx, funil_id: int | None = None, resultado: str | None = None, q: str | None = None,
           responsavel_id: int | None = None, empresa_id: int | None = None):
    consulta = ctx.filtrar_meus(select(Oportunidade), Oportunidade.responsavel_id)
    if funil_id:
        consulta = consulta.where(Oportunidade.funil_id == funil_id)
    if resultado in ("aberta", "ganha", "perdida"):
        consulta = consulta.where(Oportunidade.resultado == resultado)
    if responsavel_id:
        consulta = consulta.where(Oportunidade.responsavel_id == responsavel_id)
    if empresa_id:
        consulta = consulta.where(Oportunidade.empresa_id == empresa_id)
    if q and q.strip():
        termo = f"%{q.strip().lower()}%"
        consulta = consulta.outerjoin(Empresa, Empresa.id == Oportunidade.empresa_id).where(or_(
            func.lower(Oportunidade.titulo).like(termo), func.lower(Empresa.nome).like(termo)))
    ops = list(ctx.db.scalars(consulta.order_by(Oportunidade.valor_unico.desc(), Oportunidade.id)))
    return sv.serializar_oportunidades(ctx.db, ops)


def _detalhe(ctx: Ctx, op: Oportunidade) -> OportunidadeDetalhe:
    base = sv.serializar_oportunidades(ctx.db, [op])[0]
    recebiveis = [RecebivelOut.model_validate(t) for t in recebiveis_da_oportunidade(ctx.db, op.id)] \
        if ctx.pode("financeiro.titulos.ver") or op.resultado == "ganha" else []
    return OportunidadeDetalhe(**base.model_dump(), contexto=sv.contexto_negociacao(ctx.db, op),
                               recebiveis=recebiveis, **sv.contagens_oportunidade(ctx.db, op.id))


@router.get("/oportunidades/{op_id}", response_model=OportunidadeDetalhe)
def detalhe(op_id: int, ctx: Ctx):
    return _detalhe(ctx, sv.obter_oportunidade(ctx, op_id))


def _conferir_contato(ctx: Ctx, contato_id: int | None) -> None:
    if contato_id is not None and ctx.db.get(Pessoa, contato_id) is None:
        raise RegraViolada("Contato não encontrado.")


def _campos(op_campos: dict | None, campos: dict | None, interesse: str | None, enviou_interesse: bool) -> dict:
    novos = dict(op_campos or {})
    novos.update(campos or {})
    if enviou_interesse:
        if interesse:
            novos["interesse"] = interesse
        else:
            novos.pop("interesse", None)
    return novos


@router.post("/oportunidades", response_model=OportunidadeOut, status_code=201)
def criar(dados: OportunidadeCriar, ctx: Ctx):
    db = ctx.db
    funil = db.get(Funil, dados.funil_id)
    if funil is None or not funil.ativo:
        raise RegraViolada("Funil não encontrado.")
    etapa = sv.primeira_etapa(db, funil.id)
    responsavel_id = sv.responsavel_efetivo(ctx, dados.responsavel_id)
    unico, mensal = validar_valores(dados.valor_unico, dados.valor_recorrente_mensal)
    _conferir_contato(ctx, dados.contato_id)
    empresa = sv.resolver_empresa(ctx, empresa_id=dados.empresa_id, empresa_nome=dados.empresa_nome,
                                  responsavel_id=responsavel_id)
    hoje = sv.hoje()
    op = Oportunidade(
        titulo=dados.titulo.strip(), funil_id=funil.id, etapa_id=etapa.id, resultado="aberta",
        empresa_id=empresa.id if empresa else None, contato_id=dados.contato_id, responsavel_id=responsavel_id,
        valor_unico=unico, valor_recorrente_mensal=mensal, previsao_fechamento=dados.previsao_fechamento,
        proxima_acao=(dados.proxima_acao or "").strip() or None, proxima_acao_prazo=dados.proxima_acao_prazo,
        origem=dados.origem, necessidade=dados.necessidade, decisor=dados.decisor,
        orcamento_concorrencia=dados.orcamento_concorrencia, criterio_sucesso=dados.criterio_sucesso,
        entrou_etapa_em=hoje, campos_custom=_campos({}, dados.campos_custom, dados.interesse, True))
    db.add(op)
    db.flush()
    sv.registrar_evento(db, op.id, "criada", f"Oportunidade criada em {etapa.nome}", ctx.usuario.id)
    if op.proxima_acao:
        sv.registrar_evento(db, op.id, "proxima_acao", _texto_proxima(op), ctx.usuario.id)
    ctx.auditar("oportunidade.criar", "oportunidade", op.id, descricao=op.titulo, depois=audit.snapshot(op))
    db.commit()
    return sv.serializar_oportunidades(db, [op])[0]


def _texto_proxima(op: Oportunidade) -> str:
    prazo = f" até {op.proxima_acao_prazo.strftime('%d/%m/%Y')}" if op.proxima_acao_prazo else ""
    return f"Próxima ação: {op.proxima_acao}{prazo}" if op.proxima_acao else "Próxima ação removida"


def _mover(ctx: Ctx, op: Oportunidade, etapa_id: int) -> bool:
    if op.etapa_id == etapa_id:
        return False
    if op.resultado != "aberta":
        raise RegraViolada("Reabra a oportunidade antes de mudar de etapa.")
    etapa = ctx.db.get(Etapa, etapa_id)
    if etapa is None or etapa.funil_id != op.funil_id:
        raise RegraViolada("A etapa não pertence ao funil da oportunidade.")
    sv.conferir_campos_exigidos(ctx.db, op, etapa)
    de = ctx.db.get(Etapa, op.etapa_id).nome if op.etapa_id else "sem etapa"
    op.etapa_id = etapa.id
    op.entrou_etapa_em = sv.hoje()
    sv.registrar_evento(ctx.db, op.id, "etapa", f"Movida de {de} para {etapa.nome}", ctx.usuario.id)
    return True


@router.patch("/oportunidades/{op_id}", response_model=OportunidadeOut)
def atualizar(op_id: int, dados: OportunidadeAtualizar, ctx: Ctx):
    db = ctx.db
    op = sv.obter_oportunidade(ctx, op_id)
    antes = audit.snapshot(op)
    d = dados.model_dump(exclude_unset=True)
    proxima_antes = (op.proxima_acao, op.proxima_acao_prazo)

    if "valor_unico" in d or "valor_recorrente_mensal" in d:
        unico, mensal = validar_valores(d.get("valor_unico", op.valor_unico),
                                        d.get("valor_recorrente_mensal", op.valor_recorrente_mensal))
        if unico != op.valor_unico or mensal != op.valor_recorrente_mensal:
            validar_alteracao_valor(op.resultado)
        op.valor_unico, op.valor_recorrente_mensal = unico, mensal
    if "empresa_id" in d or d.get("empresa_nome"):
        empresa = sv.resolver_empresa(ctx, empresa_id=d.get("empresa_id"), empresa_nome=d.get("empresa_nome"),
                                      responsavel_id=op.responsavel_id)
        op.empresa_id = empresa.id if empresa else None
    if "contato_id" in d:
        _conferir_contato(ctx, d["contato_id"])
        op.contato_id = d["contato_id"]
    if d.get("responsavel_id") and not ctx.somente_meus_registros():
        op.responsavel_id = sv.responsavel_efetivo(ctx, d["responsavel_id"])
    if "titulo" in d and d["titulo"]:
        op.titulo = d["titulo"].strip()
    for campo in ("previsao_fechamento", "proxima_acao_prazo", "origem", "necessidade", "decisor",
                  "orcamento_concorrencia", "criterio_sucesso"):
        if campo in d:
            setattr(op, campo, d[campo])
    if "proxima_acao" in d:
        op.proxima_acao = (d["proxima_acao"] or "").strip() or None
    if "campos_custom" in d or "interesse" in d:
        op.campos_custom = _campos(op.campos_custom, d.get("campos_custom"), d.get("interesse"), "interesse" in d)
    if d.get("funil_id") and d["funil_id"] != op.funil_id:
        if op.resultado != "aberta":
            raise RegraViolada("Reabra a oportunidade antes de mudar de funil.")
        funil = db.get(Funil, d["funil_id"])
        if funil is None or not funil.ativo:
            raise RegraViolada("Funil não encontrado.")
        op.funil_id = funil.id
        op.etapa_id = None
        destino = d.get("etapa_id") or sv.primeira_etapa(db, funil.id).id
        _mover(ctx, op, destino)
    elif d.get("etapa_id"):
        _mover(ctx, op, d["etapa_id"])

    if (op.proxima_acao, op.proxima_acao_prazo) != proxima_antes:
        sv.registrar_evento(db, op.id, "proxima_acao", _texto_proxima(op), ctx.usuario.id)
    a, dd = audit.diff(antes, audit.snapshot(op))
    if a or dd:
        ctx.auditar("oportunidade.atualizar", "oportunidade", op.id, descricao=op.titulo, antes=a, depois=dd)
    db.commit()
    return sv.serializar_oportunidades(db, [op])[0]


@router.post("/oportunidades/{op_id}/mover", response_model=OportunidadeOut)
def mover(op_id: int, dados: MoverIn, ctx: Ctx):
    op = sv.obter_oportunidade(ctx, op_id)
    antes = audit.snapshot(op)
    if _mover(ctx, op, dados.etapa_id):
        a, d = audit.diff(antes, audit.snapshot(op))
        ctx.auditar("oportunidade.mover", "oportunidade", op.id, descricao=op.titulo, antes=a, depois=d)
        ctx.db.commit()
    return sv.serializar_oportunidades(ctx.db, [op])[0]


@router.post("/oportunidades/{op_id}/ganhar", response_model=GanhoOut)
def ganhar(op_id: int, dados: GanharIn, ctx: Ctx):
    """Venda ganha → recebíveis em RASCUNHO no Financeiro. Não registra pagamento nem movimenta caixa.
    Ganhar de novo é recusado (400) e não duplica títulos."""
    db = ctx.db
    op = sv.obter_oportunidade(ctx, op_id)
    validar_ganho(op.resultado)
    antes = audit.snapshot(op)
    if dados.empresa_id is not None or (dados.empresa_nome or "").strip():
        empresa = sv.resolver_empresa(ctx, empresa_id=dados.empresa_id, empresa_nome=dados.empresa_nome,
                                      responsavel_id=op.responsavel_id)
    else:
        empresa = db.get(Empresa, op.empresa_id) if op.empresa_id else None
    valor = positivo(dados.valor, "Informe o valor acordado.")
    n = numero_de_parcelas(dados.condicao)
    recebiveis = preparar_recebiveis_do_ganho(
        db, oportunidade_id=op.id, titulo=op.titulo, empresa_id=empresa.id if empresa else None, valor=valor,
        condicao=dados.condicao, primeiro_vencimento=dados.primeiro_vencimento, responsavel_id=op.responsavel_id)
    op.empresa_id = empresa.id
    op.valor_unico = valor
    op.resultado = "ganha"
    op.ganha_em = sv.hoje()
    sv.registrar_evento(db, op.id, "ganha",
                        f"Venda ganha: {formatar_brl(valor)} em {n} parcela(s). Recebíveis em rascunho para revisão "
                        "financeira.", ctx.usuario.id)
    a, d = audit.diff(antes, audit.snapshot(op))
    ctx.auditar("oportunidade.ganhar", "oportunidade", op.id, descricao=f"{op.titulo} · {len(recebiveis)} recebível(is)",
                antes=a, depois=d)
    db.commit()
    return GanhoOut(oportunidade=sv.serializar_oportunidades(db, [op])[0],
                    recebiveis=[RecebivelOut.model_validate(t) for t in recebiveis],
                    mensagem="Venda ganha. Revise os recebíveis antes de confirmar.")


@router.post("/oportunidades/{op_id}/perder", response_model=OportunidadeOut)
def perder(op_id: int, dados: PerderIn, ctx: Ctx):
    op = sv.obter_oportunidade(ctx, op_id)
    if op.resultado != "aberta":
        raise RegraViolada("Só oportunidades abertas podem ser marcadas como perdidas.")
    motivo = validar_perda(dados.motivo)
    antes = audit.snapshot(op)
    op.resultado = "perdida"
    op.perdida_em = sv.hoje()
    op.motivo_perda = motivo
    op.concorrente = (dados.concorrente or "").strip() or None
    op.data_retomada = dados.data_retomada
    extra = f" · concorrente: {op.concorrente}" if op.concorrente else ""
    retomada = f" · retomar em {op.data_retomada.strftime('%d/%m/%Y')}" if op.data_retomada else ""
    sv.registrar_evento(ctx.db, op.id, "perdida", f"Perdida: {motivo}{extra}{retomada}", ctx.usuario.id)
    a, d = audit.diff(antes, audit.snapshot(op))
    ctx.auditar("oportunidade.perder", "oportunidade", op.id, descricao=motivo, antes=a, depois=d)
    ctx.db.commit()
    return sv.serializar_oportunidades(ctx.db, [op])[0]


@router.post("/oportunidades/{op_id}/reabrir", response_model=OportunidadeOut)
def reabrir(op_id: int, ctx: Ctx):
    op = sv.obter_oportunidade(ctx, op_id)
    if op.resultado == "ganha":
        raise RegraViolada("Venda ganha não é reaberta: ajuste pela revisão financeira dos recebíveis.")
    if op.resultado == "aberta":
        raise RegraViolada("A oportunidade já está aberta.")
    antes = audit.snapshot(op)
    op.resultado = "aberta"
    op.perdida_em = None
    op.entrou_etapa_em = sv.hoje()
    if op.etapa_id is None:
        op.etapa_id = sv.primeira_etapa(ctx.db, op.funil_id).id
    sv.registrar_evento(ctx.db, op.id, "reaberta", f"Reaberta (motivo da perda anterior: {op.motivo_perda})",
                        ctx.usuario.id)
    a, d = audit.diff(antes, audit.snapshot(op))
    ctx.auditar("oportunidade.reabrir", "oportunidade", op.id, descricao=op.titulo, antes=a, depois=d)
    ctx.db.commit()
    return sv.serializar_oportunidades(ctx.db, [op])[0]


@router.get("/oportunidades/{op_id}/historico", response_model=list[EventoOut])
def historico(op_id: int, ctx: Ctx):
    op = sv.obter_oportunidade(ctx, op_id)
    eventos = list(ctx.db.scalars(select(OportunidadeEvento).where(OportunidadeEvento.oportunidade_id == op.id)
                                  .order_by(OportunidadeEvento.quando.desc(), OportunidadeEvento.id.desc())))
    nomes = dict(ctx.db.execute(select(Usuario.id, Usuario.nome).where(
        Usuario.id.in_({e.usuario_id for e in eventos if e.usuario_id}))).all()) if eventos else {}
    return [EventoOut.model_validate(e).model_copy(update={"usuario_nome": nomes.get(e.usuario_id)}) for e in eventos]


@router.post("/oportunidades/{op_id}/notas", response_model=EventoOut, status_code=201)
def nota(op_id: int, dados: NotaIn, ctx: Ctx):
    op = sv.obter_oportunidade(ctx, op_id)
    ev = OportunidadeEvento(oportunidade_id=op.id, tipo="nota", texto=dados.texto.strip(), usuario_id=ctx.usuario.id)
    ctx.db.add(ev)
    ctx.db.flush()
    ctx.auditar("oportunidade.nota", "oportunidade", op.id, descricao=dados.texto.strip()[:200])
    ctx.db.commit()
    return EventoOut.model_validate(ev).model_copy(update={"usuario_nome": ctx.usuario.nome})
