"""Gestão: propostas, metas e forecast, desempenho, dashboards/indicadores, playbooks e modelos de comunicação."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, or_, select

from app.core import audit
from app.core.deps import Ctx
from app.core.models import Usuario
from app.domain import RegraViolada
from app.domain.dinheiro import ZERO, formatar_brl
from app.domain.funil import ItemForecast, alem_do_limite, forecast_ponderado
from app.domain.indicadores import FORMULAS, apuracao_meta, ciclo_mediano, conversao, ticket_medio
from app.domain.proposta import exige_aprovacao_desconto, proxima_versao, validar_proposta
from app.modules.comercial import regras
from app.modules.comercial import servico as sv
from app.modules.comercial.models import (
    Atividade,
    Etapa,
    Funil,
    IndicadorConfig,
    Meta,
    ModeloComunicacao,
    Oportunidade,
    Playbook,
    Proposta,
)
from app.modules.comercial.schemas import (
    DashboardOut,
    DesempenhoOut,
    EvidenciasOut,
    ForecastOut,
    IndicadorCalculado,
    IndicadorConfigAtualizar,
    IndicadorConfigCriar,
    IndicadorConfigOut,
    MetaAtualizar,
    MetaCriar,
    MetaOut,
    ModeloAtualizar,
    ModeloCriar,
    ModeloOut,
    PlaybookAtualizar,
    PlaybookCriar,
    PlaybookOut,
    PreviaIndicador,
    PreviaIndicadorIn,
    PreviaModeloIn,
    PreviaModeloOut,
    PropostaAtualizar,
    PropostaCriar,
    PropostaOut,
    VendedorDesempenho,
)
from app.modules.financeiro.models import Titulo
from app.modules.financeiro.servico import recebiveis_da_oportunidade
from app.modules.nucleo.models import CampoCustom, Pessoa, Produto

router = APIRouter(tags=["comercial · gestão"])

STATUS_ROTULO = {"rascunho": "Rascunho", "em_aprovacao": "Em aprovação",
                 "aprovada_internamente": "Aprovada internamente", "enviada": "Enviada", "aceita": "Aceita",
                 "recusada": "Recusada"}


# ================================================================================================ propostas
def _serializar_propostas(db, ps: list[Proposta]) -> list[PropostaOut]:
    ops = sv.nomes_oportunidades(db, (p.oportunidade_id for p in ps))
    emps = sv.nomes_empresas(db, (p.empresa_id for p in ps))
    prods = sv.nomes_produtos(db, (p.produto_id for p in ps))
    users = sv.nomes_usuarios(db, (p.responsavel_id for p in ps))
    return [PropostaOut.model_validate(p).model_copy(update={
        "oportunidade_titulo": ops.get(p.oportunidade_id), "empresa_nome": emps.get(p.empresa_id),
        "produto_nome": prods.get(p.produto_id), "responsavel_nome": users.get(p.responsavel_id)}) for p in ps]


def _conferir_status(ctx: Ctx, atual: str | None, novo: str, desconto) -> None:
    """Desconto > 0 passa por aprovação interna (alçada de quem aprova no Financeiro) antes de enviar."""
    if novo == atual or not exige_aprovacao_desconto(desconto):
        return
    if novo == "aprovada_internamente":
        ctx.exigir("financeiro.aprovacoes.editar")
    if novo in ("enviada", "aceita") and atual not in ("aprovada_internamente", "enviada", "aceita"):
        raise RegraViolada("Proposta com desconto precisa de aprovação interna antes do envio.")


def _conferir_produto(db, produto_id: int | None) -> None:
    if produto_id is not None and db.get(Produto, produto_id) is None:
        raise RegraViolada("Produto ou serviço não encontrado.")


@router.get("/propostas", response_model=list[PropostaOut])
def listar_propostas(ctx: Ctx, oportunidade_id: int | None = None, status: str | None = None, q: str | None = None):
    consulta = ctx.filtrar_meus(select(Proposta), Proposta.responsavel_id)
    if oportunidade_id:
        consulta = consulta.where(Proposta.oportunidade_id == oportunidade_id)
    if status:
        consulta = consulta.where(Proposta.status == status)
    if q and q.strip():
        consulta = consulta.where(func.lower(Proposta.titulo).like(f"%{q.strip().lower()}%"))
    return _serializar_propostas(ctx.db, list(ctx.db.scalars(consulta.order_by(Proposta.id.desc()))))


@router.get("/propostas/{proposta_id}", response_model=PropostaOut)
def obter_proposta(proposta_id: int, ctx: Ctx):
    return _serializar_propostas(ctx.db, [sv.obter(ctx, Proposta, proposta_id, "Proposta não encontrada.")])[0]


def _versoes(db, oportunidade_id: int) -> list[int]:
    return list(db.scalars(select(Proposta.versao).where(Proposta.oportunidade_id == oportunidade_id)))


@router.post("/propostas", response_model=PropostaOut, status_code=201)
def criar_proposta(dados: PropostaCriar, ctx: Ctx):
    db = ctx.db
    op = sv.conferir_oportunidade_vinculo(ctx, dados.oportunidade_id)
    empresa_id = dados.empresa_id or op.empresa_id
    if empresa_id is None:
        raise RegraViolada("Informe a empresa da proposta.")
    sv.conferir_empresa(db, empresa_id)
    _conferir_produto(db, dados.produto_id)
    total = validar_proposta(quantidade=dados.quantidade, preco_unitario=dados.preco_unitario,
                             desconto_pct=dados.desconto_pct, justificativa_desconto=dados.justificativa_desconto)
    versoes = _versoes(db, op.id)
    versao = dados.versao or proxima_versao(versoes)
    if versao in versoes:
        raise RegraViolada(f"Já existe a versão {versao} desta proposta. Use Duplicar para criar uma nova versão.")
    _conferir_status(ctx, None, dados.status, dados.desconto_pct)
    p = Proposta(**dados.model_dump(exclude={"empresa_id", "versao", "responsavel_id", "desconto_pct",
                                             "mensalidade_adicional"}),
                 empresa_id=empresa_id, versao=versao, responsavel_id=sv.responsavel_efetivo(ctx, dados.responsavel_id),
                 desconto_pct=dados.desconto_pct or Decimal("0"),
                 mensalidade_adicional=dados.mensalidade_adicional or Decimal("0"), total=total)
    db.add(p)
    db.flush()
    sv.registrar_evento(db, op.id, "proposta", f"Proposta v{versao} registrada: {p.titulo} · {formatar_brl(total)}",
                        ctx.usuario.id)
    ctx.auditar("proposta.criar", "proposta", p.id, descricao=f"{p.titulo} v{versao}", depois=audit.snapshot(p))
    db.commit()
    return _serializar_propostas(db, [p])[0]


@router.patch("/propostas/{proposta_id}", response_model=PropostaOut)
def atualizar_proposta(proposta_id: int, dados: PropostaAtualizar, ctx: Ctx):
    db = ctx.db
    p = sv.obter(ctx, Proposta, proposta_id, "Proposta não encontrada.")
    antes = audit.snapshot(p)
    d = dados.model_dump(exclude_unset=True)
    if "produto_id" in d:
        _conferir_produto(db, d["produto_id"])
    for chave in ("desconto_pct", "mensalidade_adicional"):
        if chave in d and d[chave] is None:
            d[chave] = Decimal("0")
    novo = {k: d.get(k, getattr(p, k)) for k in ("quantidade", "preco_unitario", "desconto_pct",
                                                  "justificativa_desconto")}
    p.total = validar_proposta(**novo)
    status_antes = p.status
    if "status" in d and d["status"]:
        _conferir_status(ctx, p.status, d["status"], novo["desconto_pct"])
    if "responsavel_id" in d:
        if d["responsavel_id"] is None or ctx.somente_meus_registros():
            d.pop("responsavel_id")
        else:
            d["responsavel_id"] = sv.responsavel_efetivo(ctx, d["responsavel_id"])
    for k, v in d.items():
        if v is not None or k in ("produto_id", "justificativa_desconto"):
            setattr(p, k, v)
    if p.status != status_antes:
        extra = " (a oportunidade segue aberta até o fechamento ser revisado)" if p.status == "aceita" else ""
        sv.registrar_evento(db, p.oportunidade_id, "proposta",
                            f"Proposta v{p.versao}: {STATUS_ROTULO[p.status]}{extra}", ctx.usuario.id)
    a, dd = audit.diff(antes, audit.snapshot(p))
    ctx.auditar("proposta.atualizar", "proposta", p.id, descricao=f"{p.titulo} v{p.versao}", antes=a, depois=dd)
    db.commit()
    return _serializar_propostas(db, [p])[0]


@router.post("/propostas/{proposta_id}/duplicar", response_model=PropostaOut, status_code=201)
def duplicar_proposta(proposta_id: int, ctx: Ctx):
    """Nova versão (rascunho) com os mesmos termos."""
    db = ctx.db
    p = sv.obter(ctx, Proposta, proposta_id, "Proposta não encontrada.")
    versao = proxima_versao(_versoes(db, p.oportunidade_id))
    campos = {k: v for k, v in audit.snapshot(p).items()
              if k not in ("id", "versao", "status", "criado_em", "atualizado_em")}
    nova = Proposta(**{k: getattr(p, k) for k in campos}, versao=versao, status="rascunho")
    db.add(nova)
    db.flush()
    sv.registrar_evento(db, p.oportunidade_id, "proposta", f"Proposta v{versao} criada a partir da v{p.versao}",
                        ctx.usuario.id)
    ctx.auditar("proposta.duplicar", "proposta", nova.id, descricao=f"{nova.titulo} v{versao}",
                depois=audit.snapshot(nova))
    db.commit()
    return _serializar_propostas(db, [nova])[0]


# ================================================================================================ metas e forecast
FORMULA_META = {
    "receita_unica_ganha": "Σ valor único das oportunidades ganhas no período",
    "mrr_novo": "Σ valor recorrente mensal das oportunidades ganhas no período",
    "vendas_ganhas": "quantidade de oportunidades ganhas no período",
    "atividades_concluidas": "quantidade de atividades concluídas no período",
}


def _apurar(db, m: Meta) -> Decimal:
    if m.indicador == "atividades_concluidas":
        q = select(Atividade).where(Atividade.status == "concluida")
        if m.responsavel_tipo == "pessoa" and m.responsavel_id:
            q = q.where(Atividade.responsavel_id == m.responsavel_id)
        return Decimal(sum(1 for a in db.scalars(q) if sv.no_periodo(a.concluida_em, m.inicio, m.fim)))
    q = select(Oportunidade).where(Oportunidade.resultado == "ganha", Oportunidade.ganha_em >= m.inicio,
                                   Oportunidade.ganha_em <= m.fim)
    if m.responsavel_tipo == "pessoa" and m.responsavel_id:
        q = q.where(Oportunidade.responsavel_id == m.responsavel_id)
    if m.funil_id:
        q = q.where(Oportunidade.funil_id == m.funil_id)
    ganhas = list(db.scalars(q))
    if m.indicador == "receita_unica_ganha":
        return sv.soma(o.valor_unico for o in ganhas)
    if m.indicador == "mrr_novo":
        return sv.soma(o.valor_recorrente_mensal for o in ganhas)
    return Decimal(len(ganhas))


def _serializar_metas(db, ms: list[Meta]) -> list[MetaOut]:
    users = sv.nomes_usuarios(db, (m.responsavel_id for m in ms))
    funis = sv.nomes_funis(db, (m.funil_id for m in ms))
    out = []
    for m in ms:
        realizado = _apurar(db, m)
        out.append(MetaOut.model_validate(m).model_copy(update={
            "responsavel_nome": users.get(m.responsavel_id), "funil_nome": funis.get(m.funil_id),
            "realizado": realizado, "percentual": apuracao_meta(realizado, m.alvo),
            "formula": f"{FORMULA_META[m.indicador]} ÷ meta"}))
    return out


def _validar_meta(db, d: dict) -> None:
    regras.validar_meta(nome=d.get("nome"), responsavel_tipo=d.get("responsavel_tipo") or "pessoa",
                        responsavel_id=d.get("responsavel_id"), equipe=d.get("equipe"), inicio=d.get("inicio"),
                        fim=d.get("fim"), indicador=d.get("indicador"), alvo=d.get("alvo"))
    if d.get("funil_id") and db.get(Funil, d["funil_id"]) is None:
        raise RegraViolada("Funil não encontrado.")
    if d.get("responsavel_id") and db.get(Usuario, d["responsavel_id"]) is None:
        raise RegraViolada("Responsável não encontrado ou inativo.")


def _metas_visiveis(ctx: Ctx):
    q = select(Meta)
    if ctx.somente_meus_registros():
        q = q.where(or_(Meta.responsavel_id == ctx.usuario.id, Meta.responsavel_tipo == "equipe"))
    return q


@router.get("/metas", response_model=list[MetaOut])
def listar_metas(ctx: Ctx):
    return _serializar_metas(ctx.db, list(ctx.db.scalars(_metas_visiveis(ctx).order_by(Meta.inicio.desc(), Meta.id))))


def _obter_meta(ctx: Ctx, meta_id: int) -> Meta:
    m = ctx.db.scalar(_metas_visiveis(ctx).where(Meta.id == meta_id))
    if m is None:
        raise HTTPException(404, "Meta não encontrada.")
    return m


@router.get("/metas/{meta_id}", response_model=MetaOut)
def obter_meta(meta_id: int, ctx: Ctx):
    return _serializar_metas(ctx.db, [_obter_meta(ctx, meta_id)])[0]


@router.post("/metas", response_model=MetaOut, status_code=201)
def criar_meta(dados: MetaCriar, ctx: Ctx):
    d = dados.model_dump()
    if d["responsavel_tipo"] == "equipe":
        d["responsavel_id"] = None
    else:
        d["equipe"] = None
    _validar_meta(ctx.db, d)
    m = Meta(**d)
    ctx.db.add(m)
    ctx.db.flush()
    ctx.auditar("meta.criar", "meta", m.id, descricao=m.nome, depois=audit.snapshot(m))
    ctx.db.commit()
    return _serializar_metas(ctx.db, [m])[0]


@router.patch("/metas/{meta_id}", response_model=MetaOut)
def atualizar_meta(meta_id: int, dados: MetaAtualizar, ctx: Ctx):
    m = _obter_meta(ctx, meta_id)
    antes = audit.snapshot(m)
    d = {**{k: getattr(m, k) for k in ("nome", "responsavel_tipo", "responsavel_id", "equipe", "inicio", "fim",
                                       "indicador", "alvo", "funil_id")}, **dados.model_dump(exclude_unset=True)}
    if d["responsavel_tipo"] == "equipe":
        d["responsavel_id"] = None
    else:
        d["equipe"] = None
    _validar_meta(ctx.db, d)
    for k, v in d.items():
        setattr(m, k, v)
    a, dd = audit.diff(antes, audit.snapshot(m))
    ctx.auditar("meta.atualizar", "meta", m.id, descricao=m.nome, antes=a, depois=dd)
    ctx.db.commit()
    return _serializar_metas(ctx.db, [m])[0]


@router.get("/forecast", response_model=ForecastOut)
def forecast(ctx: Ctx, funil_id: int | None = None):
    """Projeção por parâmetros (probabilidade da etapa), sem previsão estatística e sem compor o caixa."""
    q = ctx.filtrar_meus(select(Oportunidade).where(Oportunidade.resultado == "aberta"), Oportunidade.responsavel_id)
    if funil_id:
        q = q.where(Oportunidade.funil_id == funil_id)
    abertas = list(ctx.db.scalars(q))
    etapas = {e.id: e for e in ctx.db.scalars(select(Etapa))}
    itens = [ItemForecast(o.valor_unico, etapas[o.etapa_id].probabilidade if o.etapa_id in etapas else 0)
             for o in abertas]
    por_etapa = []
    for e in sorted(etapas.values(), key=lambda e: (e.funil_id, e.ordem)):
        if funil_id and e.funil_id != funil_id:
            continue
        da = [o for o in abertas if o.etapa_id == e.id]
        if not da and not funil_id:
            continue
        por_etapa.append({"etapa": e.nome, "probabilidade": e.probabilidade, "quantidade": len(da),
                          "valor": sv.soma(o.valor_unico for o in da),
                          "ponderado": forecast_ponderado([ItemForecast(o.valor_unico, e.probabilidade) for o in da])})
    return ForecastOut(
        pipeline_aberto=sv.soma(o.valor_unico for o in abertas), ponderado=forecast_ponderado(itens),
        mrr_potencial=sv.soma(o.valor_recorrente_mensal for o in abertas),
        sem_previsao=sum(1 for o in abertas if o.previsao_fechamento is None), abertas=len(abertas),
        por_etapa=por_etapa,
        formulas={"pipeline_aberto": "Σ valor único das oportunidades abertas (exclui ganhos e perdas)",
                  "ponderado": FORMULAS["forecast_ponderado"],
                  "mrr_potencial": "Σ valor recorrente mensal das abertas (separado do valor único)",
                  "sem_previsao": "abertas sem data de previsão de fechamento"},
        limite="Projeção comercial por parâmetros, sem previsão estatística e sem compor o caixa.")


# ================================================================================================ desempenho
def _periodo(inicio: date | None, fim: date | None) -> tuple[date, date]:
    ref = sv.hoje()
    inicio = inicio or ref.replace(day=1)
    fim = fim or ref
    regras.validar_periodo(inicio, fim)
    return inicio, fim


def _ops_escopo(ctx: Ctx, funil_id: int | None, usuario_id: int | None = None) -> list[Oportunidade]:
    q = ctx.filtrar_meus(select(Oportunidade), Oportunidade.responsavel_id)
    if funil_id:
        q = q.where(Oportunidade.funil_id == funil_id)
    if usuario_id:
        q = q.where(Oportunidade.responsavel_id == usuario_id)
    return list(ctx.db.scalars(q))


@router.get("/desempenho", response_model=DesempenhoOut)
def desempenho(ctx: Ctx, inicio: date | None = None, fim: date | None = None, funil_id: int | None = None):
    """Indicadores calculados em código, com fórmula visível. Sem ranking: vendedores em ordem alfabética."""
    inicio, fim = _periodo(inicio, fim)
    ops = _ops_escopo(ctx, funil_id)
    ganhas = [o for o in ops if o.resultado == "ganha" and sv.no_periodo(o.ganha_em, inicio, fim)]
    perdidas = [o for o in ops if o.resultado == "perdida" and sv.no_periodo(o.perdida_em, inicio, fim)]
    receita = sv.soma(o.valor_unico for o in ganhas)
    conv = conversao(len(ganhas), len(perdidas))
    ticket = ticket_medio(receita, len(ganhas))
    ciclo = ciclo_mediano([(o.criado_em.date(), o.ganha_em) for o in ganhas])
    nomes = sv.nomes_usuarios(ctx.db, {o.responsavel_id for o in ops})
    vendedores = []
    for uid, nome in sorted(nomes.items(), key=lambda x: x[1].lower()):
        g = [o for o in ganhas if o.responsavel_id == uid]
        p = [o for o in perdidas if o.responsavel_id == uid]
        vendedores.append(VendedorDesempenho(
            usuario_id=uid, nome=nome, ganhas=len(g), perdidas=len(p), encerradas=len(g) + len(p),
            conversao=conversao(len(g), len(p)), receita=sv.soma(o.valor_unico for o in g),
            sem_proxima_acao=sum(1 for o in ops if o.responsavel_id == uid and o.resultado == "aberta"
                                 and not (o.proxima_acao or "").strip())))
    return DesempenhoOut(
        inicio=inicio, fim=fim, encerradas=len(ganhas) + len(perdidas),
        conversao=IndicadorCalculado(valor=conv, detalhe=f"{len(ganhas)} ganhas / {len(ganhas) + len(perdidas)} encerradas",
                                     formula=FORMULAS["conversao"]),
        receita_ganha=IndicadorCalculado(valor=receita, detalhe="Valores únicos no período",
                                         formula=FORMULAS["receita_ganha"]),
        ticket_medio=IndicadorCalculado(valor=ticket, detalhe=f"{formatar_brl(receita)} / {len(ganhas)} venda(s)",
                                        formula=FORMULAS["ticket_medio"]),
        ciclo_mediano=IndicadorCalculado(valor=ciclo, detalhe=f"{len(ganhas)} oportunidade(s) ganha(s)",
                                         formula=FORMULAS["ciclo_mediano"]),
        vendedores=vendedores,
        limites=["Sem ranking, nota única ou inferência de personalidade.",
                 "Comparações exigem carteiras e períodos equivalentes.",
                 "Precisão do forecast: sem base histórica suficiente para medir."])


@router.get("/desempenho/evidencias", response_model=EvidenciasOut)
def evidencias(ctx: Ctx, usuario_id: int, inicio: date | None = None, fim: date | None = None,
               funil_id: int | None = None):
    """As oportunidades e atividades que sustentam os números de uma pessoa (Ver evidências)."""
    if ctx.somente_meus_registros() and usuario_id != ctx.usuario.id:
        raise HTTPException(404, "Pessoa não encontrada.")
    u = ctx.db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(404, "Pessoa não encontrada.")
    inicio, fim = _periodo(inicio, fim)
    ref = sv.hoje()
    ops = _ops_escopo(ctx, funil_id, usuario_id)
    etapas = {e.id: e for e in ctx.db.scalars(select(Etapa))}
    ganhas = [o for o in ops if o.resultado == "ganha" and sv.no_periodo(o.ganha_em, inicio, fim)]
    perdidas = [o for o in ops if o.resultado == "perdida" and sv.no_periodo(o.perdida_em, inicio, fim)]
    abertas = [o for o in ops if o.resultado == "aberta"]
    sem_prox = [o for o in abertas if not (o.proxima_acao or "").strip()]
    alem = [o for o in abertas if o.etapa_id in etapas
            and alem_do_limite(o.entrou_etapa_em, etapas[o.etapa_id].limite_dias, ref)]
    atrasadas = list(ctx.db.scalars(select(Atividade).where(
        Atividade.responsavel_id == usuario_id, Atividade.status == "pendente", Atividade.prazo < ref)
        .order_by(Atividade.prazo)))
    gargalo, acao = regras.gargalo_do_vendedor(sem_proxima_acao=len(sem_prox), atividades_atrasadas=len(atrasadas),
                                               alem_do_limite=len(alem), encerradas=len(ganhas) + len(perdidas))
    ser = lambda lst: sv.serializar_oportunidades(ctx.db, lst, ref)
    return EvidenciasOut(
        usuario_id=u.id, nome=u.nome, inicio=inicio, fim=fim, ganhas=ser(ganhas), perdidas=ser(perdidas),
        sem_proxima_acao=ser(sem_prox), alem_do_limite=ser(alem),
        atividades_atrasadas=sv.serializar_atividades(ctx.db, atrasadas, ref), gargalo=gargalo, acao_sugerida=acao,
        limites=["Fontes: oportunidades e atividades registradas no FlicSales.",
                 "Falta de próxima ação indica lacuna no registro; não prova ausência de contato com o cliente.",
                 "Análise de qualidade de comunicação exige conteúdo autorizado."])


# ================================================================================================ dashboards
def _calcular(ctx: Ctx, metrica: str, filtro_campo_id: int | None, filtro_valor: str | None) -> PreviaIndicador:
    abertas = list(ctx.db.scalars(ctx.filtrar_meus(select(Oportunidade).where(Oportunidade.resultado == "aberta"),
                                                   Oportunidade.responsavel_id)))
    descricao = "Oportunidades abertas"
    if filtro_campo_id:
        campo = ctx.db.get(CampoCustom, filtro_campo_id)
        if campo is None or campo.objeto != "oportunidade":
            raise RegraViolada("Campo personalizado não encontrado para oportunidades.")
        if not (filtro_valor or "").strip():
            raise RegraViolada("Informe o valor do filtro do campo personalizado.")
        alvo = filtro_valor.strip().lower()
        abertas = [o for o in abertas if str((o.campos_custom or {}).get(campo.slug, "")).strip().lower() == alvo]
        descricao += f" · {campo.nome} = {filtro_valor.strip()}"
    if metrica == "soma_valor_unico":
        valor, formula = sv.soma(o.valor_unico for o in abertas), "Σ valor único das oportunidades abertas filtradas"
    else:
        valor, formula = Decimal(len(abertas)), "quantidade de oportunidades abertas filtradas"
    return PreviaIndicador(valor=valor, quantidade=len(abertas), descricao=descricao,
                           formula=formula + " (exclui ganhos e perdas)")


def _serializar_indicadores(ctx: Ctx, its: list[IndicadorConfig], calcular: bool = True) -> list[IndicadorConfigOut]:
    campos = dict(ctx.db.execute(select(CampoCustom.id, CampoCustom.nome)).all())
    out = []
    for i in its:
        res = None
        if calcular and i.ativo:
            try:
                res = _calcular(ctx, i.metrica, i.filtro_campo_id, i.filtro_valor)
            except RegraViolada:
                res = None
        out.append(IndicadorConfigOut.model_validate(i).model_copy(update={
            "filtro_campo_nome": campos.get(i.filtro_campo_id), "resultado": res}))
    return out


@router.get("/dashboards", response_model=DashboardOut)
def dashboard(ctx: Ctx, funil_id: int | None = None):
    db = ctx.db
    ops = _ops_escopo(ctx, None)
    abertas = [o for o in ops if o.resultado == "aberta"]
    funil = db.get(Funil, funil_id) if funil_id else db.scalar(
        select(Funil).where(Funil.ativo.is_(True)).order_by(Funil.id).limit(1))
    por_etapa = []
    if funil:
        for e in sv.etapas_do_funil(db, funil.id):
            da = [o for o in abertas if o.etapa_id == e.id]
            por_etapa.append({"etapa": e.nome, "quantidade": len(da), "valor": sv.soma(o.valor_unico for o in da)})
    ids = [o.id for o in ops]
    recebiveis = db.scalar(select(func.count()).select_from(Titulo).where(
        Titulo.origem_oportunidade_id.in_(ids), Titulo.status != "cancelado")) if ids else 0
    pendentes = db.scalar(ctx.filtrar_meus(select(func.count()).select_from(Atividade).where(
        Atividade.status == "pendente"), Atividade.responsavel_id)) or 0
    alto = [o for o in abertas if str((o.campos_custom or {}).get("interesse", "")).lower() == "alto"]
    indicadores = list(db.scalars(select(IndicadorConfig).where(IndicadorConfig.ativo.is_(True))
                                  .order_by(IndicadorConfig.id)))
    return DashboardOut(pipeline_alto_interesse=sv.soma(o.valor_unico for o in alto), oportunidades=len(ops),
                        recebiveis=recebiveis or 0, proximas_acoes=pendentes, funil_id=funil.id if funil else None,
                        pipeline_por_etapa=por_etapa, indicadores=_serializar_indicadores(ctx, indicadores))


@router.get("/indicadores", response_model=list[IndicadorConfigOut])
def listar_indicadores(ctx: Ctx, incluir_inativos: bool = False):
    q = select(IndicadorConfig).order_by(IndicadorConfig.id)
    if not incluir_inativos:
        q = q.where(IndicadorConfig.ativo.is_(True))
    return _serializar_indicadores(ctx, list(ctx.db.scalars(q)))


@router.post("/indicadores/previa", response_model=PreviaIndicador)
def previa_indicador(dados: PreviaIndicadorIn, ctx: Ctx):
    """Calcular prévia (sem salvar)."""
    return _calcular(ctx, dados.metrica, dados.filtro_campo_id, dados.filtro_valor)


@router.post("/indicadores", response_model=IndicadorConfigOut, status_code=201)
def criar_indicador(dados: IndicadorConfigCriar, ctx: Ctx):
    _calcular(ctx, dados.metrica, dados.filtro_campo_id, dados.filtro_valor)  # valida o filtro
    i = IndicadorConfig(**dados.model_dump())
    ctx.db.add(i)
    ctx.db.flush()
    ctx.auditar("indicador.criar", "indicador_config", i.id, descricao=i.nome, depois=audit.snapshot(i))
    ctx.db.commit()
    return _serializar_indicadores(ctx, [i])[0]


@router.patch("/indicadores/{indicador_id}", response_model=IndicadorConfigOut)
def atualizar_indicador(indicador_id: int, dados: IndicadorConfigAtualizar, ctx: Ctx):
    i = sv.obter(ctx, IndicadorConfig, indicador_id, "Indicador não encontrado.", responsavel=None)
    antes = audit.snapshot(i)
    for k, v in dados.model_dump(exclude_unset=True).items():
        if v is not None or k in ("filtro_campo_id", "filtro_valor"):
            setattr(i, k, v)
    _calcular(ctx, i.metrica, i.filtro_campo_id, i.filtro_valor)
    a, d = audit.diff(antes, audit.snapshot(i))
    ctx.auditar("indicador.atualizar", "indicador_config", i.id, descricao=i.nome, antes=a, depois=d)
    ctx.db.commit()
    return _serializar_indicadores(ctx, [i])[0]


# ================================================================================================ playbooks
def _serializar_playbooks(db, ps: list[Playbook]) -> list[PlaybookOut]:
    funis = sv.nomes_funis(db, (p.funil_id for p in ps))
    etapas = sv.nomes_etapas(db, (p.etapa_id for p in ps))
    users = sv.nomes_usuarios(db, (p.responsavel_id for p in ps))
    return [PlaybookOut.model_validate(p).model_copy(update={
        "funil_nome": funis.get(p.funil_id), "etapa_nome": etapas.get(p.etapa_id),
        "responsavel_nome": users.get(p.responsavel_id)}) for p in ps]


def _validar_playbook(db, d: dict) -> None:
    regras.validar_playbook(nome=d.get("nome"), objetivo=d.get("objetivo"), criterios_avanco=d.get("criterios_avanco"))
    if d.get("funil_id") and db.get(Funil, d["funil_id"]) is None:
        raise RegraViolada("Funil não encontrado.")
    if d.get("etapa_id"):
        e = db.get(Etapa, d["etapa_id"])
        if e is None or (d.get("funil_id") and e.funil_id != d["funil_id"]):
            raise RegraViolada("A etapa não pertence ao funil escolhido.")


@router.get("/playbooks", response_model=list[PlaybookOut])
def listar_playbooks(ctx: Ctx, q: str | None = None, funil_id: int | None = None, incluir_inativos: bool = False):
    consulta = select(Playbook)
    if not incluir_inativos:
        consulta = consulta.where(Playbook.ativo.is_(True))
    if funil_id:
        consulta = consulta.where(Playbook.funil_id == funil_id)
    if q and q.strip():
        consulta = consulta.where(func.lower(Playbook.nome).like(f"%{q.strip().lower()}%"))
    return _serializar_playbooks(ctx.db, list(ctx.db.scalars(consulta.order_by(Playbook.nome))))


@router.get("/playbooks/{playbook_id}", response_model=PlaybookOut)
def obter_playbook(playbook_id: int, ctx: Ctx):
    return _serializar_playbooks(ctx.db, [sv.obter(ctx, Playbook, playbook_id, "Playbook não encontrado.",
                                                   responsavel=None)])[0]


@router.post("/playbooks", response_model=PlaybookOut, status_code=201)
def criar_playbook(dados: PlaybookCriar, ctx: Ctx):
    d = dados.model_dump()
    _validar_playbook(ctx.db, d)
    p = Playbook(**d)
    ctx.db.add(p)
    ctx.db.flush()
    ctx.auditar("playbook.criar", "playbook", p.id, descricao=p.nome, depois=audit.snapshot(p))
    ctx.db.commit()
    return _serializar_playbooks(ctx.db, [p])[0]


@router.patch("/playbooks/{playbook_id}", response_model=PlaybookOut)
def atualizar_playbook(playbook_id: int, dados: PlaybookAtualizar, ctx: Ctx):
    p = sv.obter(ctx, Playbook, playbook_id, "Playbook não encontrado.", responsavel=None)
    antes = audit.snapshot(p)
    d = dados.model_dump(exclude_unset=True)
    if d.get("ativo") is None:
        d.pop("ativo", None)
    atual = {k: getattr(p, k) for k in ("nome", "objetivo", "criterios_avanco", "funil_id", "etapa_id")}
    _validar_playbook(ctx.db, {**atual, **d})
    for k, v in d.items():
        setattr(p, k, v)
    a, dd = audit.diff(antes, audit.snapshot(p))
    ctx.auditar("playbook.atualizar", "playbook", p.id, descricao=p.nome, antes=a, depois=dd)
    ctx.db.commit()
    return _serializar_playbooks(ctx.db, [p])[0]


# ================================================================================================ modelos de comunicação
def _modelo_out(m: ModeloComunicacao) -> ModeloOut:
    return ModeloOut.model_validate(m).model_copy(update={
        "variaveis": regras.variaveis_do_texto(f"{m.assunto or ''} {m.conteudo}")})


@router.get("/modelos", response_model=list[ModeloOut])
def listar_modelos(ctx: Ctx, q: str | None = None, canal: str | None = None, finalidade: str | None = None,
                   incluir_inativos: bool = False):
    consulta = select(ModeloComunicacao)
    if not incluir_inativos:
        consulta = consulta.where(ModeloComunicacao.ativo.is_(True))
    if canal:
        consulta = consulta.where(ModeloComunicacao.canal == canal)
    if finalidade:
        consulta = consulta.where(ModeloComunicacao.finalidade == finalidade)
    if q and q.strip():
        consulta = consulta.where(func.lower(ModeloComunicacao.nome).like(f"%{q.strip().lower()}%"))
    return [_modelo_out(m) for m in ctx.db.scalars(consulta.order_by(ModeloComunicacao.nome))]


@router.get("/modelos/{modelo_id}", response_model=ModeloOut)
def obter_modelo(modelo_id: int, ctx: Ctx):
    return _modelo_out(sv.obter(ctx, ModeloComunicacao, modelo_id, "Modelo não encontrado.", responsavel=None))


@router.post("/modelos", response_model=ModeloOut, status_code=201)
def criar_modelo(dados: ModeloCriar, ctx: Ctx):
    regras.validar_modelo(nome=dados.nome, canal=dados.canal, finalidade=dados.finalidade, conteudo=dados.conteudo,
                          status=dados.status)
    m = ModeloComunicacao(**dados.model_dump())
    ctx.db.add(m)
    ctx.db.flush()
    ctx.auditar("modelo.criar", "modelo_comunicacao", m.id, descricao=m.nome, depois=audit.snapshot(m))
    ctx.db.commit()
    return _modelo_out(m)


@router.patch("/modelos/{modelo_id}", response_model=ModeloOut)
def atualizar_modelo(modelo_id: int, dados: ModeloAtualizar, ctx: Ctx):
    m = sv.obter(ctx, ModeloComunicacao, modelo_id, "Modelo não encontrado.", responsavel=None)
    antes = audit.snapshot(m)
    d = {k: v for k, v in dados.model_dump(exclude_unset=True).items() if v is not None or k == "assunto"}
    final = {**{k: getattr(m, k) for k in ("nome", "canal", "finalidade", "conteudo", "status")}, **d}
    regras.validar_modelo(nome=final["nome"], canal=final["canal"], finalidade=final["finalidade"],
                          conteudo=final["conteudo"], status=final["status"])
    for k, v in d.items():
        setattr(m, k, v)
    a, dd = audit.diff(antes, audit.snapshot(m))
    ctx.auditar("modelo.atualizar", "modelo_comunicacao", m.id, descricao=m.nome, antes=a, depois=dd)
    ctx.db.commit()
    return _modelo_out(m)


@router.post("/modelos/{modelo_id}/previa", response_model=PreviaModeloOut)
def previa_modelo(modelo_id: int, dados: PreviaModeloIn, ctx: Ctx):
    """Preenche as variáveis com os dados de uma oportunidade. Não envia nada."""
    m = sv.obter(ctx, ModeloComunicacao, modelo_id, "Modelo não encontrado.", responsavel=None)
    valores: dict[str, str | None] = {}
    if dados.oportunidade_id:
        op = sv.conferir_oportunidade_vinculo(ctx, dados.oportunidade_id)
        valores["oportunidade.titulo"] = op.titulo
        valores["empresa.nome"] = sv.nomes_empresas(ctx.db, [op.empresa_id]).get(op.empresa_id)
        if op.contato_id:
            p = ctx.db.get(Pessoa, op.contato_id)
            valores["contato.nome"] = p.nome if p else None
        titulos = recebiveis_da_oportunidade(ctx.db, op.id)
        if titulos:
            valores["titulo.valor"] = formatar_brl(titulos[0].valor_original or ZERO)
            valores["titulo.vencimento"] = titulos[0].vencimento.strftime("%d/%m/%Y")
        for chave, v in (op.campos_custom or {}).items():
            valores[f"oportunidade.{chave}"] = None if v is None else str(v)
    assunto, falta_a = regras.renderizar_modelo(m.assunto, valores) if m.assunto else (None, [])
    conteudo, falta_c = regras.renderizar_modelo(m.conteudo, valores)
    return PreviaModeloOut(assunto=assunto, conteudo=conteudo, faltando=list(dict.fromkeys(falta_a + falta_c)),
                           aviso="Prévia para revisão. Nenhuma mensagem é enviada.")
