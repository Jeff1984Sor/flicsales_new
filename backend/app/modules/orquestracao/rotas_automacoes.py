"""Automações: catálogo, modelos prontos, CRUD por área, Testar (prévia), Ativar/Pausar, histórico e avisos.

Nada é excluído: pausar encerra a execução. Toda mudança é auditada. Área separada: editar automação do Comercial
exige também acesso ao Comercial (e o mesmo para o Financeiro).
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core import audit
from app.core.db import agora, hoje
from app.core.deps import Ctx
from app.domain import RegraViolada
from app.domain import automacao as dom
from app.modules.comercial.models import Etapa, Funil
from app.modules.nucleo.models import CampoCustom
from app.modules.orquestracao import integracoes as integ
from app.modules.orquestracao import motor
from app.modules.orquestracao.models import Automacao, AutomacaoExecucao
from app.modules.orquestracao.schemas import (
    AutomacaoIn,
    AutomacaoOut,
    AutomacaoPatch,
    AvisoOut,
    ExecucaoOut,
    TesteOut,
)

router = APIRouter(prefix="/automacoes")
# área separada: automação comercial cria/acompanha atividades; a financeira acompanha cobranças
PERMISSAO_DA_AREA = {"comercial": "comercial.atividades.ver", "financeiro": "financeiro.cobrancas.ver"}


def _exigir_area(ctx, area: str) -> None:
    ctx.exigir(PERMISSAO_DA_AREA[area])


def _out(a: Automacao) -> AutomacaoOut:
    o = AutomacaoOut.model_validate(a)
    o.gatilho_rotulo = dom.GATILHOS.get(a.area, {}).get(a.gatilho, a.gatilho)
    o.acao_rotulo = dom.ACOES.get(a.acao, a.acao)
    return o


def _obter(ctx, automacao_id: int) -> Automacao:
    a = ctx.db.get(Automacao, automacao_id)
    if a is None:
        raise HTTPException(404, "Automação não encontrada.")
    _exigir_area(ctx, a.area)
    return a


def _config(a: Automacao) -> dom.Configuracao:
    return dom.Configuracao(area=a.area, nome=a.nome, gatilho=a.gatilho, acao=a.acao, conteudo=a.conteudo,
                            funil_id=a.funil_id, etapa_destino_id=a.etapa_destino_id, campo=a.campo, operador=a.operador,
                            valor_esperado=a.valor_esperado, prazo_dias=a.prazo_dias, tipo_atividade=a.tipo_atividade,
                            responsavel_regra=a.responsavel_regra, destinatario=a.destinatario)


def _validar_e_aplicar(ctx, a: Automacao, c: dom.Configuracao) -> None:
    c = dom.validar_configuracao(c)
    if c.funil_id is not None and ctx.db.get(Funil, c.funil_id) is None:
        raise RegraViolada("Funil não encontrado.")
    if c.etapa_destino_id is not None:
        etapa = ctx.db.get(Etapa, c.etapa_destino_id)
        if etapa is None or (c.funil_id is not None and etapa.funil_id != c.funil_id):
            raise RegraViolada("Etapa de destino não pertence ao funil escolhido.")
    for k in ("nome", "gatilho", "acao", "conteudo", "funil_id", "etapa_destino_id", "campo", "operador",
              "valor_esperado", "prazo_dias", "tipo_atividade", "responsavel_regra", "destinatario"):
        setattr(a, k, getattr(c, k))


# ------------------------------------------------------------------------------------------------ catálogo e modelos
@router.get("/catalogo")
def catalogo(ctx: Ctx) -> dict[str, Any]:
    funis = []
    for f in ctx.db.scalars(select(Funil).where(Funil.ativo.is_(True)).order_by(Funil.nome)):
        etapas = ctx.db.scalars(select(Etapa).where(Etapa.funil_id == f.id).order_by(Etapa.ordem, Etapa.id))
        funis.append({"id": f.id, "nome": f.nome, "etapas": [{"id": e.id, "nome": e.nome} for e in etapas]})
    campos = [{"slug": c.slug, "nome": c.nome, "objeto": c.objeto, "tipo": c.tipo, "opcoes": c.opcoes or []}
              for c in ctx.db.scalars(select(CampoCustom).where(CampoCustom.arquivado.is_(False))
                                      .order_by(CampoCustom.objeto, CampoCustom.ordem, CampoCustom.nome))]
    return {
        "gatilhos": {area: [{"id": k, "rotulo": v} for k, v in g.items()] for area, g in dom.GATILHOS.items()},
        "gatilhos_de_evento": sorted(dom.GATILHOS_DE_EVENTO),
        "acoes": [{"id": k, "rotulo": v, "envio": k in dom.CANAL_DA_ACAO} for k, v in dom.ACOES.items()],
        "operadores": [{"id": k, "rotulo": v} for k, v in dom.OPERADORES.items()],
        "tipos_atividade": [{"id": k, "rotulo": v} for k, v in dom.TIPOS_ATIVIDADE_ROTULO.items()],
        "campos_padrao": {"comercial": [{"slug": "valor", "nome": "Valor único"}, {"slug": "etapa", "nome": "Etapa"},
                                        {"slug": "proxima_acao", "nome": "Próxima ação"}],
                          "financeiro": [{"slug": "saldo_em_aberto", "nome": "Saldo em aberto"},
                                         {"slug": "valor", "nome": "Valor original"},
                                         {"slug": "status", "nome": "Estado do título"}]},
        "destinatarios": [{"id": "contato_principal", "rotulo": "Contato principal do registro"},
                          {"id": "responsavel_interno", "rotulo": "Responsável interno"}],
        "variaveis": dom.VARIAVEIS, "funis": funis, "campos": campos,
        "canais_conectados": sorted(integ.canais_conectados(ctx.db)),
    }


@router.get("/modelos")
def modelos(ctx: Ctx, area: str = Query("comercial", pattern="^(comercial|financeiro)$")) -> list[dict[str, Any]]:
    out = []
    for m in dom.modelos_da_area(area):
        m = dict(m)
        m["gatilho_rotulo"] = dom.GATILHOS[area][m["gatilho"]]
        m["acao_rotulo"] = dom.ACOES[m["acao"]]
        m["tipo_atividade_rotulo"] = dom.TIPOS_ATIVIDADE_ROTULO.get(m["tipo_atividade"] or "", "")
        m["etapa_destino_id"] = None
        if m["etapa_destino_nome"]:
            ids = list(ctx.db.scalars(select(Etapa.id).where(Etapa.nome == m["etapa_destino_nome"])))
            m["etapa_destino_id"] = ids[0] if len(ids) == 1 else None
        out.append(m)
    return out


# ------------------------------------------------------------------------------------------------ histórico e avisos
@router.get("/execucoes", response_model=list[ExecucaoOut])
def execucoes(ctx: Ctx, area: str | None = Query(None, pattern="^(comercial|financeiro)$"),
              automacao_id: int | None = None, limite: int = Query(100, ge=1, le=500)):
    q = select(AutomacaoExecucao, Automacao).join(Automacao, Automacao.id == AutomacaoExecucao.automacao_id)
    if area:
        _exigir_area(ctx, area)
        q = q.where(Automacao.area == area)
    if automacao_id:
        q = q.where(AutomacaoExecucao.automacao_id == automacao_id)
    linhas = ctx.db.execute(q.order_by(AutomacaoExecucao.quando.desc(), AutomacaoExecucao.id.desc()).limit(limite)).all()
    return [ExecucaoOut(id=e.id, automacao_id=a.id, automacao_nome=a.nome, area=a.area, quando=e.quando,
                        registro=e.registro, resultado=e.resultado, simulacao=e.simulacao, erro=e.erro,
                        tentativas=e.tentativas, detalhe=e.detalhe, registro_criado=e.registro_criado)
            for e, a in linhas if ctx.pode(PERMISSAO_DA_AREA[a.area])]


@router.get("/avisos", response_model=list[AvisoOut])
def avisos(ctx: Ctx):
    """Avisos de "Notificar responsável" endereçados ao usuário logado."""
    q = (select(AutomacaoExecucao, Automacao).join(Automacao, Automacao.id == AutomacaoExecucao.automacao_id)
         .where(AutomacaoExecucao.resultado == "notificado",
                AutomacaoExecucao.registro_criado == f"usuario:{ctx.usuario.id}")
         .order_by(AutomacaoExecucao.quando.desc()).limit(50))
    return [AvisoOut(id=e.id, automacao_nome=a.nome, texto=e.detalhe, quando=e.quando) for e, a in ctx.db.execute(q)]


# ------------------------------------------------------------------------------------------------ CRUD
@router.get("", response_model=list[AutomacaoOut])
def listar(ctx: Ctx, area: str = Query("comercial", pattern="^(comercial|financeiro)$")):
    _exigir_area(ctx, area)
    return [_out(a) for a in ctx.db.scalars(select(Automacao).where(Automacao.area == area).order_by(Automacao.id))]


@router.post("", response_model=AutomacaoOut, status_code=201)
def criar(dados: AutomacaoIn, ctx: Ctx):
    _exigir_area(ctx, dados.area)
    a = Automacao(area=dados.area, estado="rascunho", revisar_condicoes=dados.revisar_condicoes, nome="", gatilho="",
                  acao="", conteudo="")
    d = dados.model_dump()
    _validar_e_aplicar(ctx, a, dom.Configuracao(**{k: d[k] for k in dom.Configuracao.__dataclass_fields__}))
    ctx.db.add(a)
    ctx.db.flush()
    ctx.auditar("automacao.criar", "automacao", a.id, descricao=f"{a.area} · {a.nome}", depois=audit.snapshot(a))
    ctx.db.commit()
    return _out(a)


@router.get("/{automacao_id}", response_model=AutomacaoOut)
def obter(automacao_id: int, ctx: Ctx):
    return _out(_obter(ctx, automacao_id))


@router.patch("/{automacao_id}", response_model=AutomacaoOut)
def alterar(automacao_id: int, dados: AutomacaoPatch, ctx: Ctx):
    a = _obter(ctx, automacao_id)
    antes = audit.snapshot(a)
    mudancas = dados.model_dump(exclude_unset=True)
    revisar = mudancas.pop("revisar_condicoes", None)
    c = _config(a)
    for k, v in mudancas.items():
        setattr(c, k, v)
    _validar_e_aplicar(ctx, a, c)
    if revisar is not None:
        a.revisar_condicoes = revisar
    if a.estado == "ativa":
        dom.validar_ativacao(a.acao, integ.canais_conectados(ctx.db))
    ctx.db.flush()
    x, y = audit.diff(antes, audit.snapshot(a))
    ctx.auditar("automacao.alterar", "automacao", a.id, antes=x, depois=y)
    ctx.db.commit()
    return _out(a)


@router.post("/{automacao_id}/testar", response_model=TesteOut)
def testar(automacao_id: int, ctx: Ctx):
    a = _obter(ctx, automacao_id)
    r = motor.testar(ctx.db, a, hoje())
    ctx.auditar("automacao.testar", "automacao", a.id, descricao=r["resumo"])
    ctx.db.commit()
    return r


@router.post("/{automacao_id}/ativar", response_model=AutomacaoOut)
def ativar(automacao_id: int, ctx: Ctx):
    a = _obter(ctx, automacao_id)
    dom.validar_configuracao(_config(a))
    dom.validar_ativacao(a.acao, integ.canais_conectados(ctx.db))
    if a.estado != "ativa":
        antes = a.estado
        a.estado, a.ativada_em = "ativa", agora()
        ctx.auditar("automacao.ativar", "automacao", a.id, antes={"estado": antes}, depois={"estado": "ativa"})
        ctx.db.commit()
    return _out(a)


@router.post("/{automacao_id}/pausar", response_model=AutomacaoOut)
def pausar(automacao_id: int, ctx: Ctx):
    a = _obter(ctx, automacao_id)
    if a.estado != "pausada":
        antes = a.estado
        a.estado = "pausada"
        ctx.auditar("automacao.pausar", "automacao", a.id, antes={"estado": antes}, depois={"estado": "pausada"})
        ctx.db.commit()
    return _out(a)
