"""API do Financeiro (`/api/financeiro`): títulos, baixas/estornos, aprovações, transferências, recorrências,
cobranças, caixa, dashboards e o Hoje financeiro.

A rota só orquestra: carrega, chama o domínio (app/domain), grava, audita e faz commit. As permissões vêm do mapa
padrão de app/core/permissoes.py (prefixos /financeiro/titulos, /baixas, /aprovacoes, /caixa, /transferencias,
/dashboards, /cobrancas, /recorrencias, /hoje); aprovar exige `financeiro.aprovacoes.editar`.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.core import audit, envio, ia
from app.core.db import agora, hoje
from app.core.deps import Ctx
from app.core.models import Usuario
from app.core.permissoes import adicionar_regras
from app.core.schemas import EnvioEmailIn, EnvioEmailOut, EnvioWhatsAppIn, EnvioWhatsAppOut, Pagina
from app.domain import RegraViolada
from app.domain import caixa as dom_caixa
from app.domain import cobranca as dom_cob
from app.domain import envio as dom_envio
from app.domain import recorrencia as dom_rec
from app.domain import titulos as dom
from app.domain.dinheiro import formatar_brl
from app.domain.leitura import TituloResumo, ler_momento
from app.domain.modelos_comunicacao import CONTEXTOS
from app.modules.comercial import regras as regras_modelo
from app.modules.comercial.models import ModeloComunicacao
from app.modules.comercial.schemas import ModeloOut, PreviaModeloOut
from app.modules.financeiro import operacoes as op
from app.modules.financeiro.models import Baixa, Cobranca, Recorrencia, Titulo, Transferencia
from app.modules.financeiro.schemas import (
    BaixaIn,
    BaixaOut,
    CaixaOut,
    CobrancaAtualizar,
    CobrancaIn,
    CobrancaOut,
    ContestadosOut,
    DashboardsOut,
    GerarCompetenciaIn,
    HojeOut,
    MotivoIn,
    OpcoesFinanceiro,
    RecorrenciaAtualizar,
    RecorrenciaIn,
    RecorrenciaOut,
    TituloAtualizar,
    TituloDetalhe,
    TituloIn,
    TituloOut,
    TransferenciaIn,
    TransferenciaOut,
)
from app.modules.financeiro.servico import filtrar_direcao_visivel, pode_ver_caixa, pode_ver_pagar
from app.modules.nucleo.models import Categoria, CentroCusto, ContaFinanceira, Empresa, Pessoa

# prévia de modelo não grava nada: basta ver as cobranças (o padrão de POST seria `editar`)
adicionar_regras([("POST", r"/financeiro/cobrancas/\d+/modelos/\d+/previa$", "financeiro.cobrancas.ver")])

router = APIRouter(prefix="/financeiro", tags=["financeiro"])

APROVAR = "financeiro.aprovacoes.editar"
EstadoTitulo = Literal["todos", "aberto", "rascunho", "parcial", "liquidado", "cancelado", "vencido"]


def _404(o, nome: str = "Registro"):
    if o is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{nome} não encontrado.")
    return o


def _existe(ctx: Ctx, modelo, id_: int | None, mensagem: str, *, ativo: bool = False) -> None:
    if id_ is None:
        return
    o = ctx.db.get(modelo, id_)
    if o is None or (ativo and not getattr(o, "ativo", True)):
        raise RegraViolada(mensagem)


def _pagina(ctx: Ctx, consulta, pagina: int, por_pagina: int):
    total = ctx.db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
    itens = list(ctx.db.scalars(consulta.limit(por_pagina).offset((pagina - 1) * por_pagina)))
    return itens, total


# ================================================================ títulos
def _titulo(ctx: Ctx, titulo_id: int, *, travar: bool = False) -> Titulo:
    t = ctx.db.get(Titulo, titulo_id, with_for_update=travar)
    if t is None or not ctx.pode_acessar(t.responsavel_id) or (t.direcao == "pagar" and not pode_ver_pagar(ctx)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Título não encontrado.")
    return t


def _exigir_direcao(ctx: Ctx, direcao: str | None) -> None:
    if direcao == "pagar" and not pode_ver_pagar(ctx):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu perfil de acesso vê só títulos a receber; contas a pagar "
                                                       "exigem acesso a Aprovações ou Baixas.")


def _meus_titulos(ctx: Ctx, consulta):
    """Escopo do perfil sobre uma consulta que já tem `Titulo`: só meus registros + direções visíveis."""
    return filtrar_direcao_visivel(ctx, ctx.filtrar_meus(consulta, Titulo.responsavel_id))


def _filtro_estado(q, estado: str, h: date):
    if estado == "vencido":
        return q.where(Titulo.status.in_(dom.EM_ABERTO), Titulo.vencimento < h)
    if estado != "todos":
        return q.where(Titulo.status == estado)
    return q


def _busca_titulos(q, termo: str | None):
    if not termo:
        return q
    like = f"%{termo.strip()}%"
    return q.join(Empresa, Empresa.id == Titulo.empresa_id).where(
        or_(Titulo.descricao.ilike(like), Empresa.nome.ilike(like), Titulo.documento.ilike(like)))


def _saida(ctx: Ctx, titulos: list[Titulo]) -> list[TituloOut]:
    return [TituloOut.model_validate(d) for d in op.titulos_para_saida(ctx.db, titulos, hoje())]


@router.get("/titulos/opcoes", response_model=OpcoesFinanceiro)
def opcoes(ctx: Ctx):
    """Listas curtas para os formulários (empresas, categorias, centros de custo, contas).
    Contas financeiras só para quem vê o caixa ou registra baixas (precisa escolher a conta)."""
    db = ctx.db
    ver_contas = pode_ver_caixa(ctx) or ctx.pode("financeiro.baixas.editar")
    return {
        "empresas": [{"id": e.id, "nome": e.nome, "cliente": e.papel_cliente or e.papel_prospect,
                      "fornecedor": e.papel_fornecedor}
                     for e in db.scalars(select(Empresa).where(Empresa.ativo.is_(True)).order_by(Empresa.nome))],
        "categorias": [{"id": c.id, "nome": c.nome, "natureza": c.natureza}
                       for c in db.scalars(select(Categoria).where(Categoria.ativo.is_(True)).order_by(Categoria.nome))],
        "centros_custo": [{"id": c.id, "nome": f"{c.nome} ({c.codigo})"} for c in db.scalars(
            select(CentroCusto).where(CentroCusto.ativo.is_(True)).order_by(CentroCusto.nome))],
        "contas": [{"id": c.id, "nome": c.nome, "data_base": c.data_base} for c in db.scalars(
            select(ContaFinanceira).where(ContaFinanceira.ativo.is_(True)).order_by(ContaFinanceira.nome))]
        if ver_contas else [],
    }


@router.get("/titulos/contagens", response_model=dict[str, int])
def contagens(ctx: Ctx, direcao: Literal["receber", "pagar"], q: str | None = None):
    """Números dos chips de estado (Todos, Aberto, Rascunho, Parcial, Liquidado, Cancelado, Vencido)."""
    _exigir_direcao(ctx, direcao)
    h = hoje()
    base = ctx.filtrar_meus(_busca_titulos(select(Titulo.id).where(Titulo.direcao == direcao), q),
                            Titulo.responsavel_id)
    out = {}
    for estado in ("todos", "aberto", "rascunho", "parcial", "liquidado", "cancelado", "vencido"):
        out[estado] = ctx.db.scalar(select(func.count()).select_from(_filtro_estado(base, estado, h).subquery())) or 0
    return out


@router.get("/titulos", response_model=Pagina[TituloOut])
def listar_titulos(ctx: Ctx, direcao: Literal["receber", "pagar"] | None = None, estado: EstadoTitulo = "todos",
                   q: str | None = None, empresa_id: int | None = None, origem_oportunidade_id: int | None = None,
                   pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200)):
    _exigir_direcao(ctx, direcao)
    consulta = select(Titulo)
    if direcao:
        consulta = consulta.where(Titulo.direcao == direcao)
    if empresa_id:
        consulta = consulta.where(Titulo.empresa_id == empresa_id)
    if origem_oportunidade_id:
        consulta = consulta.where(Titulo.origem_oportunidade_id == origem_oportunidade_id)
    consulta = _busca_titulos(_filtro_estado(consulta, estado, hoje()), q)
    consulta = _meus_titulos(ctx, consulta).order_by(Titulo.vencimento, Titulo.id)
    itens, total = _pagina(ctx, consulta, pagina, por_pagina)
    return Pagina[TituloOut](itens=_saida(ctx, itens), total=total, pagina=pagina, por_pagina=por_pagina)


def _validar_vinculos(ctx: Ctx, d: dict) -> None:
    _existe(ctx, Empresa, d.get("empresa_id"), "Selecione um cliente ou fornecedor cadastrado.")
    _existe(ctx, Categoria, d.get("categoria_id"), "Categoria não encontrada.")
    _existe(ctx, CentroCusto, d.get("centro_custo_id"), "Centro de custo não encontrado.")
    _existe(ctx, ContaFinanceira, d.get("conta_prevista_id"), "Conta prevista não encontrada.")
    _existe(ctx, Usuario, d.get("responsavel_id"), "Responsável não encontrado.")


def _aplicar_aprovacao(ctx: Ctx, t: Titulo, nova: str | None) -> None:
    if t.direcao != "pagar":
        t.aprovacao = None
        return
    nova = nova or "pendente"
    if nova == t.aprovacao:
        return
    if nova == "aprovado" or t.aprovacao == "aprovado":
        ctx.exigir(APROVAR)  # alçada: só quem aprova muda a aprovação
    t.aprovacao = nova
    t.aprovado_por_id, t.aprovado_em = (ctx.usuario.id, agora()) if nova == "aprovado" else (None, None)


@router.post("/titulos", response_model=TituloOut, status_code=201)
def criar_titulo(dados: TituloIn, ctx: Ctx):
    _exigir_direcao(ctx, dados.direcao)
    valor = dom.validar_valor(dados.valor_original)
    d = dados.model_dump(exclude={"rascunho", "aprovacao"})
    _validar_vinculos(ctx, d)
    d["valor_original"] = valor
    t = Titulo(**d, saldo=valor, status="rascunho" if dados.rascunho else "aberto")
    if t.status == "aberto":
        t.confirmado_em = agora()
    _aplicar_aprovacao(ctx, t, dados.aprovacao)
    ctx.db.add(t)
    ctx.db.flush()
    ctx.auditar("titulo.criar", "titulo", t.id, descricao=f"{t.direcao} / {t.descricao}", depois=audit.snapshot(t))
    ctx.db.commit()
    return _saida(ctx, [t])[0]


@router.get("/titulos/{titulo_id}", response_model=TituloDetalhe)
def detalhe_titulo(titulo_id: int, ctx: Ctx):
    t = _titulo(ctx, titulo_id)
    h = hoje()
    baixas = list(ctx.db.scalars(select(Baixa).where(Baixa.titulo_id == t.id).order_by(Baixa.data, Baixa.id)))
    cobrancas = list(ctx.db.scalars(select(Cobranca).where(Cobranca.titulo_id == t.id).order_by(Cobranca.id.desc())))
    return {**op.titulos_para_saida(ctx.db, [t], h)[0], "origem": op.origem_do_titulo(ctx.db, t),
            "baixas": op.baixas_para_saida(ctx.db, baixas), "cobrancas": op.cobrancas_para_saida(ctx.db, cobrancas, h)}


_OBRIGATORIOS = {"empresa_id": "o cliente ou fornecedor", "descricao": "a descrição", "vencimento": "o vencimento",
                 "valor_original": "o valor", "responsavel_id": "o responsável"}


@router.patch("/titulos/{titulo_id}", response_model=TituloOut)
def editar_titulo(titulo_id: int, dados: TituloAtualizar, ctx: Ctx):
    t = _titulo(ctx, titulo_id, travar=True)
    if t.status == "cancelado":
        raise RegraViolada("Título cancelado não pode ser editado.")
    if t.id in op.baixas_ativas_por_titulo(ctx.db, {t.id}):
        raise RegraViolada(dom.MSG_ESTORNE_EDITAR)
    d = dados.model_dump(exclude_unset=True)
    for campo, rotulo in _OBRIGATORIOS.items():
        if campo in d and d[campo] is None:
            raise RegraViolada(f"Informe {rotulo}.")
    _validar_vinculos(ctx, d)
    antes = audit.snapshot(t)
    if dom.exige_nova_aprovacao(direcao=t.direcao, aprovacao=t.aprovacao,
                                antes={c: getattr(t, c) for c in dom.CAMPOS_DA_ALCADA}, mudancas=d):
        t.aprovacao, t.aprovado_por_id, t.aprovado_em = "pendente", None, None  # a alçada aprova de novo
    if "aprovacao" in d:
        _aplicar_aprovacao(ctx, t, d.pop("aprovacao"))
    if "valor_original" in d:
        novo = dom.validar_edicao_valor(tem_baixa_ativa=False, status=t.status, novo_valor=d.pop("valor_original"))
        t.valor_original, t.saldo = novo, novo
    for k, v in d.items():
        setattr(t, k, v)
    a, dep = audit.diff(antes, audit.snapshot(t))
    ctx.auditar("titulo.editar", "titulo", t.id, descricao=t.descricao, antes=a, depois=dep)
    ctx.db.commit()
    return _saida(ctx, [t])[0]


@router.post("/titulos/{titulo_id}/confirmar", response_model=TituloOut)
def confirmar_titulo(titulo_id: int, ctx: Ctx):
    """Rascunho → aberto. Confirmar NÃO é baixa: não mexe em saldo nem em caixa."""
    t = _titulo(ctx, titulo_id, travar=True)
    t.status = dom.validar_confirmacao(t.status)
    t.confirmado_em = agora()
    ctx.auditar("titulo.confirmar", "titulo", t.id, descricao=f"{t.descricao} (recebível confirmado, sem baixa)",
                antes={"status": "rascunho"}, depois={"status": t.status})
    ctx.db.commit()
    return _saida(ctx, [t])[0]


@router.post("/titulos/{titulo_id}/cancelar", response_model=TituloOut)
def cancelar_titulo(titulo_id: int, dados: MotivoIn, ctx: Ctx):
    t = _titulo(ctx, titulo_id, travar=True)
    ativa = t.id in op.baixas_ativas_por_titulo(ctx.db, {t.id})
    antes = t.status
    t.status = dom.validar_cancelamento(status=t.status, tem_baixa_ativa=ativa, motivo=dados.motivo)
    t.motivo_cancelamento, t.cancelado_em = dados.motivo.strip(), agora()
    ctx.auditar("titulo.cancelar", "titulo", t.id, descricao=f"{t.descricao}: {t.motivo_cancelamento}",
                antes={"status": antes}, depois={"status": t.status, "motivo_cancelamento": t.motivo_cancelamento})
    ctx.db.commit()
    return _saida(ctx, [t])[0]


@router.post("/titulos/{titulo_id}/aprovar", response_model=TituloOut)
def aprovar_titulo(titulo_id: int, ctx: Ctx):
    """Alçada (permissão financeiro.aprovacoes.editar, garantida pelo mapa): registra quem aprovou e quando."""
    t = _titulo(ctx, titulo_id, travar=True)
    antes = t.aprovacao
    t.aprovacao = dom.validar_aprovacao(t.direcao, t.status, t.aprovacao)
    t.aprovado_por_id, t.aprovado_em = ctx.usuario.id, agora()
    ctx.auditar("titulo.aprovar", "titulo", t.id, descricao=f"Pagamento aprovado: {t.descricao}",
                antes={"aprovacao": antes}, depois={"aprovacao": t.aprovacao, "aprovado_por_id": ctx.usuario.id})
    ctx.db.commit()
    return _saida(ctx, [t])[0]


@router.get("/titulos/{titulo_id}/baixas", response_model=list[BaixaOut])
def baixas_do_titulo(titulo_id: int, ctx: Ctx):
    t = _titulo(ctx, titulo_id)
    return op.baixas_para_saida(ctx.db, list(ctx.db.scalars(
        select(Baixa).where(Baixa.titulo_id == t.id).order_by(Baixa.data, Baixa.id))))


@router.post("/titulos/{titulo_id}/baixas", response_model=BaixaOut, status_code=201)
def registrar_baixa(titulo_id: int, dados: BaixaIn, ctx: Ctx):
    """Recebimento/pagamento gerencial. Parcial mantém saldo; a pagar só aprovado; nada de operação bancária."""
    t = _titulo(ctx, titulo_id, travar=True)
    b = op.registrar_baixa(ctx.db, titulo=t, valor=dados.valor, data=dados.data, conta_id=dados.conta_id,
                           forma=dados.forma, referencia_comprovante=dados.referencia_comprovante,
                           observacao=dados.observacao, usuario=ctx.usuario, hoje=hoje())
    ctx.db.commit()
    return op.baixas_para_saida(ctx.db, [b])[0]


# ================================================================ baixas e estornos (trilha)
@router.get("/baixas", response_model=Pagina[BaixaOut])
def listar_baixas(ctx: Ctx, situacao: Literal["todas", "confirmada", "estornada"] = "todas",
                  direcao: Literal["receber", "pagar"] | None = None, q: str | None = None,
                  pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200)):
    consulta = _meus_titulos(ctx, select(Baixa).join(Titulo, Titulo.id == Baixa.titulo_id))
    if situacao != "todas":
        consulta = consulta.where(Baixa.estornada.is_(situacao == "estornada"))
    if direcao:
        consulta = consulta.where(Titulo.direcao == direcao)
    if q:
        like = f"%{q.strip()}%"
        consulta = consulta.join(Empresa, Empresa.id == Titulo.empresa_id).where(
            or_(Empresa.nome.ilike(like), Titulo.descricao.ilike(like), Baixa.referencia_comprovante.ilike(like)))
    consulta = consulta.order_by(Baixa.data.desc(), Baixa.id.desc())
    itens, total = _pagina(ctx, consulta, pagina, por_pagina)
    return Pagina[BaixaOut](itens=op.baixas_para_saida(ctx.db, itens), total=total, pagina=pagina,
                            por_pagina=por_pagina)


@router.post("/baixas/{baixa_id}/estornar", response_model=BaixaOut)
def estornar_baixa(baixa_id: int, dados: MotivoIn, ctx: Ctx):
    """Nunca apaga: a baixa fica com estornada=True, motivo, quem e quando; o título volta a ter saldo."""
    b = _404(ctx.db.get(Baixa, baixa_id), "Baixa")
    try:
        _titulo(ctx, b.titulo_id)  # fora do escopo do perfil = não existe
    except HTTPException:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Baixa não encontrada.") from None
    op.estornar_baixa(ctx.db, baixa=b, motivo=dados.motivo, usuario=ctx.usuario)
    ctx.db.commit()
    return op.baixas_para_saida(ctx.db, [b])[0]


# ================================================================ aprovações
@router.get("/aprovacoes", response_model=list[TituloOut])
def listar_aprovacoes(ctx: Ctx, situacao: Literal["pendente", "aprovado", "todos"] = "pendente"):
    consulta = ctx.filtrar_meus(select(Titulo).where(Titulo.direcao == "pagar", Titulo.status != "cancelado"),
                                Titulo.responsavel_id)
    if situacao == "pendente":
        consulta = consulta.where(or_(Titulo.aprovacao.is_(None), Titulo.aprovacao != "aprovado"))
    elif situacao == "aprovado":
        consulta = consulta.where(Titulo.aprovacao == "aprovado")
    return _saida(ctx, list(ctx.db.scalars(consulta.order_by(Titulo.vencimento, Titulo.id))))


# ================================================================ transferências
def _conta_info(ctx: Ctx, conta_id: int) -> dom_caixa.Conta | None:
    c = op.conta_ativa(ctx.db, conta_id)
    return dom_caixa.Conta(c.id, c.saldo_inicial, c.data_base) if c else None


def _transf_saida(ctx: Ctx, ts: list[Transferencia]) -> list[dict]:
    nomes = op._nomes(ctx.db, ContaFinanceira, {t.conta_origem_id for t in ts} | {t.conta_destino_id for t in ts})
    return [{"id": t.id, "conta_origem_id": t.conta_origem_id, "conta_origem_nome": nomes.get(t.conta_origem_id, "—"),
             "conta_destino_id": t.conta_destino_id, "conta_destino_nome": nomes.get(t.conta_destino_id, "—"),
             "valor": t.valor, "data": t.data, "descricao": t.descricao, "criado_em": t.criado_em} for t in ts]


@router.get("/transferencias", response_model=Pagina[TransferenciaOut])
def listar_transferencias(ctx: Ctx, pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200)):
    itens, total = _pagina(ctx, select(Transferencia).order_by(Transferencia.data.desc(), Transferencia.id.desc()),
                           pagina, por_pagina)
    return Pagina[TransferenciaOut](itens=_transf_saida(ctx, itens), total=total, pagina=pagina, por_pagina=por_pagina)


@router.post("/transferencias", response_model=TransferenciaOut, status_code=201)
def criar_transferencia(dados: TransferenciaIn, ctx: Ctx):
    """Movimento interno entre contas: não é receita nem despesa (o saldo gerencial total não muda)."""
    valor = dom_caixa.validar_transferencia(origem=_conta_info(ctx, dados.conta_origem_id),
                                            destino=_conta_info(ctx, dados.conta_destino_id), valor=dados.valor,
                                            data=dados.data, hoje=hoje())
    t = Transferencia(**{**dados.model_dump(), "valor": valor})
    ctx.db.add(t)
    ctx.db.flush()
    ctx.auditar("transferencia.criar", "transferencia", t.id,
                descricao=f"Conta #{t.conta_origem_id} → conta #{t.conta_destino_id}", depois=audit.snapshot(t))
    ctx.db.commit()
    return _transf_saida(ctx, [t])[0]


# ================================================================ recorrências
def _rec_saida(ctx: Ctx, recs: list[Recorrencia]) -> list[dict]:
    empresas = op._nomes(ctx.db, Empresa, {r.empresa_id for r in recs})
    cats = op._nomes(ctx.db, Categoria, {r.categoria_id for r in recs})
    centros = op._nomes(ctx.db, CentroCusto, {r.centro_custo_id for r in recs})
    h = hoje()
    out = []
    for r in recs:
        geradas = op.competencias_geradas(ctx.db, r.id)
        out.append({
            **{c: getattr(r, c) for c in ("id", "descricao", "direcao", "empresa_id", "valor_ciclo", "frequencia",
                                          "inicio", "fim", "dia_vencimento", "categoria_id", "centro_custo_id",
                                          "responsavel_id", "situacao", "criado_em")},
            "empresa_nome": empresas.get(r.empresa_id, "—"), "categoria_nome": cats.get(r.categoria_id),
            "centro_custo_nome": centros.get(r.centro_custo_id), "competencias_geradas": sorted(geradas),
            "proxima_competencia": op.proxima_competencia(r, geradas, h) if r.situacao == "ativa" else None,
        })
    return out


def _validar_recorrencia(ctx: Ctx, d: dict):
    _existe(ctx, Empresa, d.get("empresa_id"), "Selecione um cliente ou fornecedor cadastrado.")
    _existe(ctx, Categoria, d.get("categoria_id"), "Categoria não encontrada.")
    _existe(ctx, CentroCusto, d.get("centro_custo_id"), "Centro de custo não encontrado.")
    _existe(ctx, Usuario, d.get("responsavel_id"), "Responsável não encontrado.")
    return dom_rec.validar_recorrencia(valor_ciclo=d["valor_ciclo"], dia_vencimento=d["dia_vencimento"],
                                       inicio=d["inicio"], fim=d["fim"], frequencia=d["frequencia"])


def _recorrencia(ctx: Ctx, rec_id: int) -> Recorrencia:
    r = ctx.db.get(Recorrencia, rec_id)
    if r is None or not ctx.pode_acessar(r.responsavel_id) or (r.direcao == "pagar" and not pode_ver_pagar(ctx)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recorrência não encontrada.")
    return r


@router.get("/recorrencias", response_model=list[RecorrenciaOut])
def listar_recorrencias(ctx: Ctx, situacao: Literal["todas", "ativa", "pausada", "cancelada"] = "todas",
                        q: str | None = None):
    consulta = ctx.filtrar_meus(select(Recorrencia).join(Empresa, Empresa.id == Recorrencia.empresa_id),
                                Recorrencia.responsavel_id)
    if not pode_ver_pagar(ctx):
        consulta = consulta.where(Recorrencia.direcao == "receber")
    if situacao != "todas":
        consulta = consulta.where(Recorrencia.situacao == situacao)
    if q:
        like = f"%{q.strip()}%"
        consulta = consulta.where(or_(Recorrencia.descricao.ilike(like), Empresa.nome.ilike(like)))
    return _rec_saida(ctx, list(ctx.db.scalars(consulta.order_by(Recorrencia.descricao, Recorrencia.id))))


@router.get("/recorrencias/{rec_id}", response_model=RecorrenciaOut)
def detalhe_recorrencia(rec_id: int, ctx: Ctx):
    return _rec_saida(ctx, [_recorrencia(ctx, rec_id)])[0]


@router.post("/recorrencias", response_model=RecorrenciaOut, status_code=201)
def criar_recorrencia(dados: RecorrenciaIn, ctx: Ctx):
    d = dados.model_dump()
    d["valor_ciclo"] = _validar_recorrencia(ctx, d)
    r = Recorrencia(**d)
    ctx.db.add(r)
    ctx.db.flush()
    ctx.auditar("recorrencia.criar", "recorrencia", r.id, descricao=r.descricao, depois=audit.snapshot(r))
    ctx.db.commit()
    return _rec_saida(ctx, [r])[0]


@router.patch("/recorrencias/{rec_id}", response_model=RecorrenciaOut)
def editar_recorrencia(rec_id: int, dados: RecorrenciaAtualizar, ctx: Ctx):
    r = _recorrencia(ctx, rec_id)
    d = dados.model_dump(exclude_unset=True)
    for campo in ("descricao", "direcao", "empresa_id", "valor_ciclo", "frequencia", "inicio", "fim",
                  "dia_vencimento", "situacao"):
        if campo in d and d[campo] is None:
            raise RegraViolada("Preencha os campos obrigatórios da recorrência.")
    atual = {c: getattr(r, c) for c in ("valor_ciclo", "dia_vencimento", "inicio", "fim", "frequencia")}
    d_valid = {**atual, **d}
    d["valor_ciclo"] = _validar_recorrencia(ctx, d_valid)
    antes = audit.snapshot(r)
    for k, v in d.items():
        setattr(r, k, v)
    a, dep = audit.diff(antes, audit.snapshot(r))
    ctx.auditar("recorrencia.editar", "recorrencia", r.id, descricao=r.descricao, antes=a, depois=dep)
    ctx.db.commit()
    return _rec_saida(ctx, [r])[0]


@router.post("/recorrencias/{rec_id}/gerar", response_model=TituloOut, status_code=201)
def gerar_competencia(rec_id: int, dados: GerarCompetenciaIn, ctx: Ctx):
    """Gera o título da competência em RASCUNHO (sem duplicar; dentro da vigência; alinhado à frequência)."""
    r = _recorrencia(ctx, rec_id)
    t = op.gerar_competencia(ctx.db, r, dados.competencia, ctx.usuario)
    ctx.db.commit()
    return _saida(ctx, [t])[0]


# ================================================================ cobranças e acordos
@router.get("/cobrancas/contestados", response_model=ContestadosOut)
def titulos_contestados(ctx: Ctx):
    """Títulos com cobrança "Em contestação": a automação de cobrança deve suspender o envio para eles."""
    return {"titulo_ids": sorted(op.titulos_em_contestacao(ctx.db))}


def _cobranca(ctx: Ctx, cobranca_id: int) -> Cobranca:
    """Só meus registros: a cobrança é minha se sou responsável por ela ou pelo título cobrado."""
    c = ctx.db.get(Cobranca, cobranca_id)
    t = ctx.db.get(Titulo, c.titulo_id) if c else None
    if c is None or t is None or not (ctx.pode_acessar(c.responsavel_id) or ctx.pode_acessar(t.responsavel_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cobrança não encontrada.")
    return c


@router.get("/cobrancas", response_model=list[CobrancaOut])
def listar_cobrancas(ctx: Ctx, situacao: Literal["todas", "em_acompanhamento", "promessa_pagamento",
                                                  "em_contestacao", "resolvida"] = "todas",
                     titulo_id: int | None = None, q: str | None = None):
    consulta = select(Cobranca).join(Titulo, Titulo.id == Cobranca.titulo_id).join(
        Empresa, Empresa.id == Titulo.empresa_id)
    if ctx.somente_meus_registros():
        consulta = consulta.where(or_(Cobranca.responsavel_id == ctx.usuario.id,
                                      Titulo.responsavel_id == ctx.usuario.id))
    if situacao != "todas":
        consulta = consulta.where(Cobranca.situacao == situacao)
    if titulo_id:
        consulta = consulta.where(Cobranca.titulo_id == titulo_id)
    if q:
        like = f"%{q.strip()}%"
        consulta = consulta.where(or_(Cobranca.assunto.ilike(like), Empresa.nome.ilike(like),
                                      Titulo.descricao.ilike(like)))
    itens = list(ctx.db.scalars(consulta.order_by(Cobranca.proximo_contato.is_(None), Cobranca.proximo_contato,
                                                  Cobranca.id.desc())))
    return op.cobrancas_para_saida(ctx.db, itens, hoje())


# Modelos de comunicação do Financeiro (financeiro + geral). O perfil Financeiro não lê /comercial/modelos.
CONTEXTO_MODELOS = "financeiro"


def _modelo_out(m: ModeloComunicacao) -> ModeloOut:
    return ModeloOut.model_validate(m).model_copy(update={
        "variaveis": regras_modelo.variaveis_do_texto(f"{m.assunto or ''} {m.conteudo}")})


@router.get("/cobrancas/modelos", response_model=list[ModeloOut])
def modelos_cobranca(ctx: Ctx, canal: Literal["email", "whatsapp", "ligacao", "reuniao"] | None = None):
    """Modelos ativos classificados como financeiro ou geral, por nome (mesmo formato de /comercial/modelos)."""
    consulta = select(ModeloComunicacao).where(
        ModeloComunicacao.classificacao.in_(CONTEXTOS[CONTEXTO_MODELOS]), ModeloComunicacao.ativo.is_(True))
    if canal:
        consulta = consulta.where(ModeloComunicacao.canal == canal)
    return [_modelo_out(m) for m in ctx.db.scalars(consulta.order_by(ModeloComunicacao.nome, ModeloComunicacao.id))]


def _modelo_financeiro(ctx: Ctx, modelo_id: int | None) -> ModeloComunicacao | None:
    """Modelo do Financeiro (financeiro/geral); comercial ou inexistente = 404."""
    if modelo_id is None:
        return None
    m = ctx.db.get(ModeloComunicacao, modelo_id)
    if m is None or m.classificacao not in CONTEXTOS[CONTEXTO_MODELOS]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modelo não encontrado.")
    return m


@router.get("/cobrancas/{cobranca_id}", response_model=CobrancaOut)
def detalhe_cobranca(cobranca_id: int, ctx: Ctx):
    return op.cobrancas_para_saida(ctx.db, [_cobranca(ctx, cobranca_id)], hoje())[0]


@router.post("/cobrancas", response_model=CobrancaOut, status_code=201)
def criar_cobranca(dados: CobrancaIn, ctx: Ctx):
    t = ctx.db.get(Titulo, dados.titulo_id)
    if t is None or not ctx.pode_acessar(t.responsavel_id):
        raise RegraViolada("Selecione um título a receber cadastrado.")
    _existe(ctx, Usuario, dados.responsavel_id, "Responsável não encontrado.")
    d = dados.model_dump()
    d["valor_prometido"] = dom_cob.validar_cobranca(
        titulo_direcao=t.direcao, titulo_status=t.status, titulo_saldo=t.saldo, situacao=d["situacao"],
        canal=d["canal"], data_prometida=d["data_prometida"], valor_prometido=d["valor_prometido"],
        historico=d["historico"])
    c = Cobranca(**d)
    ctx.db.add(c)
    ctx.db.flush()
    ctx.auditar("cobranca.criar", "cobranca", c.id, descricao=f"{c.assunto} (título #{t.id})",
                depois=audit.snapshot(c))
    ctx.db.commit()
    return op.cobrancas_para_saida(ctx.db, [c], hoje())[0]


@router.patch("/cobrancas/{cobranca_id}", response_model=CobrancaOut)
def editar_cobranca(cobranca_id: int, dados: CobrancaAtualizar, ctx: Ctx):
    c = _cobranca(ctx, cobranca_id)
    t = ctx.db.get(Titulo, c.titulo_id)
    d = dados.model_dump(exclude_unset=True)
    for campo in ("assunto", "responsavel_id", "canal", "situacao", "historico"):
        if campo in d and d[campo] is None:
            raise RegraViolada("Preencha os campos obrigatórios da cobrança.")
    _existe(ctx, Usuario, d.get("responsavel_id"), "Responsável não encontrado.")
    m = {k: d.get(k, getattr(c, k)) for k in ("situacao", "canal", "data_prometida", "valor_prometido", "historico")}
    d_valor = dom_cob.validar_cobranca(titulo_direcao=t.direcao, titulo_status=t.status, titulo_saldo=t.saldo,
                                       nova=False, **m)
    if "valor_prometido" in d:
        d["valor_prometido"] = d_valor
    antes = audit.snapshot(c)
    for k, v in d.items():
        setattr(c, k, v)
    a, dep = audit.diff(antes, audit.snapshot(c))
    ctx.auditar("cobranca.editar", "cobranca", c.id, descricao=c.assunto, antes=a, depois=dep)
    ctx.db.commit()
    return op.cobrancas_para_saida(ctx.db, [c], hoje())[0]


@router.post("/cobrancas/{cobranca_id}/modelos/{modelo_id}/previa", response_model=PreviaModeloOut)
def previa_modelo_cobranca(cobranca_id: int, modelo_id: int, ctx: Ctx):
    """Preenche o modelo com os dados da cobrança (empresa, primeiro contato, saldo, vencimento). Não envia nada."""
    c = _cobranca(ctx, cobranca_id)
    m = _modelo_financeiro(ctx, modelo_id)
    t = ctx.db.get(Titulo, c.titulo_id)
    empresa = ctx.db.get(Empresa, t.empresa_id)
    contato = ctx.db.scalar(select(Pessoa).where(Pessoa.empresa_id == t.empresa_id).order_by(
        Pessoa.ativo.desc(), Pessoa.id).limit(1))
    valores: dict[str, str | None] = {
        "empresa.nome": empresa.nome if empresa else None, "contato.nome": contato.nome if contato else None,
        "titulo.valor": formatar_brl(t.saldo), "titulo.vencimento": t.vencimento.strftime("%d/%m/%Y"),
        "titulo.descricao": t.descricao}
    assunto, falta_a = regras_modelo.renderizar_modelo(m.assunto, valores) if m.assunto else (None, [])
    conteudo, falta_c = regras_modelo.renderizar_modelo(m.conteudo, valores)
    return PreviaModeloOut(assunto=assunto, conteudo=conteudo, faltando=list(dict.fromkeys(falta_a + falta_c)),
                           aviso="Prévia para revisão. Nada é enviado até você clicar em Enviar.")


@router.post("/cobrancas/{cobranca_id}/enviar-email", response_model=EnvioEmailOut)
def enviar_email_cobranca(cobranca_id: int, dados: EnvioEmailIn, ctx: Ctx):
    """Envia o e-mail (app.core.envio: opt-out, SMTP, assinatura) e acrescenta a linha ao histórico da cobrança."""
    c = _cobranca(ctx, cobranca_id)
    _modelo_financeiro(ctx, dados.modelo_id)
    m = envio.enviar_por_usuario(ctx.db, ctx.usuario, para=dados.para, cc=dados.cc, assunto=dados.assunto,
                                 corpo=dados.corpo)
    linha = dom_envio.linha_historico_cobranca(hoje(), m, ctx.usuario.nome)
    antes = c.historico
    c.historico = dom_envio.acrescentar_historico(c.historico, linha)
    ctx.auditar("cobranca.enviar_email", "cobranca", c.id, descricao=linha, antes={"historico": antes},
                depois={"historico": c.historico, "para": m.para, "cc": m.cc, "assunto": m.assunto,
                        "modelo_id": dados.modelo_id})
    ctx.db.commit()
    return EnvioEmailOut(enviado_para=m.para + m.cc, registro=f"Histórico da cobrança atualizado: {linha}")


@router.post("/cobrancas/{cobranca_id}/enviar-whatsapp", response_model=EnvioWhatsAppOut)
def enviar_whatsapp_cobranca(cobranca_id: int, dados: EnvioWhatsAppIn, ctx: Ctx):
    """Envia pelo WhatsApp (app.core.envio: telefone, opt-out, Evolution, assinatura) e acrescenta a linha ao
    histórico da cobrança."""
    c = _cobranca(ctx, cobranca_id)
    _modelo_financeiro(ctx, dados.modelo_id)
    m = envio.enviar_whatsapp_por_usuario(ctx.db, ctx.usuario, para=dados.para, texto=dados.texto)
    linha = dom_envio.linha_historico_cobranca_whatsapp(hoje(), m, ctx.usuario.nome)
    antes = c.historico
    c.historico = dom_envio.acrescentar_historico(c.historico, linha)
    ctx.auditar("cobranca.enviar_whatsapp", "cobranca", c.id, descricao=linha, antes={"historico": antes},
                depois={"historico": c.historico, "para": m.para, "modelo_id": dados.modelo_id})
    ctx.db.commit()
    return EnvioWhatsAppOut(enviado_para=m.para, registro=f"Histórico da cobrança atualizado: {linha}")


# ================================================================ caixa, dashboards e hoje
def _caixa_saida(cx: op.Caixa) -> dict:
    p = cx.projecao
    return {
        "saldo_gerencial": {"valor": p.saldo_atual, "detalhe": "Saldo inicial + movimentos confirmados",
                            "formula": "Σ contas (saldo inicial + recebimentos − pagamentos ± transferências; "
                                       "baixas estornadas fora)"},
        "entradas_abertas": {"valor": p.entradas_abertas, "detalhe": "Inclui vencidos; exclui rascunhos",
                             "formula": "Σ saldo aberto dos títulos a receber aberto/parcial"},
        "saidas_abertas": {"valor": p.saidas_abertas, "detalhe": "Títulos a pagar não liquidados",
                           "formula": "Σ saldo aberto dos títulos a pagar aberto/parcial"},
        "saldo_apos_titulos": {"valor": p.saldo_projetado, "detalhe": "Projeção simples sem horizonte",
                               "formula": p.formula},
        "contas": [{"id": c.id, "nome": c.nome, "instituicao": c.instituicao, "saldo_inicial": c.saldo_inicial,
                    "data_base": c.data_base, "saldo_atual": cx.saldos[c.id], "ativo": c.ativo} for c in cx.contas],
        "limites": [op.LIMITE_CAIXA],
    }


@router.get("/caixa", response_model=CaixaOut)
def caixa(ctx: Ctx):
    return _caixa_saida(op.calcular_caixa(ctx.db))


@router.get("/dashboards", response_model=DashboardsOut)
def dashboards(ctx: Ctx):
    h = hoje()
    abertos = op.titulos_aging(ctx.db)
    faixas = lambda d: [f.__dict__ for f in dom.aging(abertos, h, d)]
    return {"caixa": _caixa_saida(op.calcular_caixa(ctx.db)), "aging_receber": faixas("receber"),
            "aging_pagar": faixas("pagar"), "hoje": h, "limites": [op.LIMITE_AGING, op.LIMITE_CAIXA]}


@router.get("/hoje", response_model=HojeOut)
def hoje_financeiro(ctx: Ctx):
    """KPIs, fila de cobrança e a Leitura do momento DETERMINÍSTICA (app.domain.leitura), com ou sem IA.
    Respeita o perfil: saldo só com `financeiro.caixa.ver`, aprovações só para quem vê contas a pagar,
    recorrências só com `financeiro.recorrencias.ver` (senão `null`); fila e totais no escopo "só meus registros"."""
    h = hoje()
    escopo = lambda q: _meus_titulos(ctx, q)  # noqa: E731
    vencidos = op.vencidos_a_receber(ctx.db, h, escopo)
    empresas = op._nomes(ctx.db, Empresa, {t.empresa_id for t in vencidos})
    contestados = op.titulos_em_contestacao(ctx.db, {t.id for t in vencidos})
    total_vencido = sum((t.saldo for t in vencidos), dom.ZERO)
    ligada = ia.ligada(ctx.db)
    leitura = ler_momento(hoje=h, ia_ligada=ligada, titulos=[
        TituloResumo(t.id, empresas.get(t.empresa_id, "—"), t.descricao, t.direcao, t.status, t.vencimento, t.saldo)
        for t in vencidos if t.id not in contestados])
    recorrencias = None
    if ctx.pode("financeiro.recorrencias.ver"):
        recorrencias = ctx.db.scalar(ctx.filtrar_meus(
            select(func.count(Recorrencia.id)).where(Recorrencia.situacao == "ativa"), Recorrencia.responsavel_id)) or 0
    saldo = None
    if pode_ver_caixa(ctx):
        saldo = {"valor": op.calcular_caixa(ctx.db).projecao.saldo_atual, "detalhe": "Saldo inicial + baixas confirmadas",
                 "formula": "Σ contas (saldo inicial + baixas não estornadas ± transferências)"}
    return {
        "hoje": h,
        "saldo_gerencial": saldo,
        "recebiveis_vencidos": {"valor": total_vencido, "detalhe": f"{len(vencidos)} título(s) em aberto",
                                "formula": "Σ saldo aberto a receber com vencimento antes de hoje"},
        "recebiveis_vencidos_qtd": len(vencidos),
        "aprovacoes_pendentes": op.aprovacoes_pendentes(ctx.db, escopo) if pode_ver_pagar(ctx) else None,
        "recorrencias_ativas": recorrencias,
        "fila_cobranca": [{"titulo_id": t.id, "empresa_nome": empresas.get(t.empresa_id, "—"),
                           "descricao": t.descricao, "saldo": t.saldo, "vencimento": t.vencimento,
                           "dias_atraso": (h - t.vencimento).days, "em_contestacao": t.id in contestados}
                          for t in vencidos],
        "leitura": leitura,
        "ia_ligada": ligada,
        "limites": [op.LIMITE_OPERACAO],
    }
