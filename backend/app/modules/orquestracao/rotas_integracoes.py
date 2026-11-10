"""Integrações: ver (orquestracao.integracoes.ver), configurar/testar/revogar (orquestracao.integracoes.editar).
Segredo cifrado e somente escrita: a API só devolve "configurado" + os 4 últimos caracteres."""

from fastapi import APIRouter, HTTPException

from app.core import audit, segredos
from app.core.deps import Ctx
from app.core.models import Usuario
from app.modules.orquestracao import integracoes as integ
from app.modules.orquestracao.schemas import IntegracaoIn, IntegracaoOut

router = APIRouter(prefix="/integracoes")


def _tipo(tipo: str) -> str:
    if tipo not in integ.CATALOGO:
        raise HTTPException(404, "Integração não encontrada.")
    return tipo


@router.get("", response_model=list[IntegracaoOut])
def listar(ctx: Ctx):
    return [integ.saida(ctx.db, t, integ.obter(ctx.db, t)) for t in integ.CATALOGO]


@router.get("/{tipo}", response_model=IntegracaoOut)
def obter(tipo: str, ctx: Ctx):
    return integ.saida(ctx.db, _tipo(tipo), integ.obter(ctx.db, tipo))


@router.put("/{tipo}", response_model=IntegracaoOut)
def salvar(tipo: str, dados: IntegracaoIn, ctx: Ctx):
    i = integ.obter_ou_criar(ctx.db, _tipo(tipo))
    antes = audit.snapshot(i)
    mudou = False
    d = dados.model_dump(exclude_unset=True)
    if "responsavel_id" in d and d["responsavel_id"] is not None and ctx.db.get(Usuario, d["responsavel_id"]) is None:
        raise HTTPException(400, "Responsável não encontrado.")
    if "escopos" in d:
        validos = set(integ.CATALOGO[tipo]["escopos"])
        if any(e not in validos for e in d["escopos"] or []):
            raise HTTPException(400, "Escopo desconhecido para esta integração.")
        d["escopos"] = list(dict.fromkeys(d["escopos"] or []))
    segredo = d.pop("segredo", None)
    for k, v in d.items():
        if getattr(i, k) != v:
            setattr(i, k, v)
            mudou = True
    if segredo:
        i.segredo_cifrado = segredos.cifrar_texto(segredo.strip())
        mudou = True
    if mudou:
        # dados da conexão mudaram: precisa testar de novo
        i.estado, i.aguardando_conector, i.conectado_em = "desconectado", False, None
    ctx.db.flush()
    x, y = audit.diff(antes, audit.snapshot(i))
    ctx.auditar("integracao.configurar", "integracao", i.id, descricao="Segredo alterado" if segredo else None,
                antes=x, depois=y)
    ctx.db.commit()
    return integ.saida(ctx.db, tipo, i)


@router.post("/{tipo}/testar")
def testar(tipo: str, ctx: Ctx):
    i = integ.obter_ou_criar(ctx.db, _tipo(tipo))
    antes = audit.snapshot(i)
    mensagem = integ.testar(ctx.db, i, ctx.usuario.email)
    ctx.db.flush()
    x, y = audit.diff(antes, audit.snapshot(i))
    ctx.auditar("integracao.testar", "integracao", i.id, descricao=mensagem, antes=x, depois=y)
    ctx.db.commit()
    return {"mensagem": mensagem, "integracao": integ.saida(ctx.db, tipo, i)}


@router.post("/{tipo}/revogar")
def revogar(tipo: str, ctx: Ctx):
    i = integ.obter(ctx.db, _tipo(tipo))
    if i is None:
        raise HTTPException(404, "Integração ainda não configurada.")
    antes = audit.snapshot(i)
    pausadas = integ.revogar(ctx.db, i)
    ctx.db.flush()
    x, y = audit.diff(antes, audit.snapshot(i))
    ctx.auditar("integracao.revogar", "integracao", i.id, antes=x, depois=y,
                descricao=f"{len(pausadas)} automação(ões) de envio pausada(s)" if pausadas else None)
    for a in pausadas:
        ctx.auditar("automacao.pausar", "automacao", a.id, descricao=f"Canal {tipo} revogado",
                    antes={"estado": "ativa"}, depois={"estado": "pausada"})
    ctx.db.commit()
    msg = "Conexão revogada. O segredo foi apagado."
    if pausadas:
        msg += f" {len(pausadas)} automação(ões) de envio foram pausadas."
    return {"mensagem": msg, "integracao": integ.saida(ctx.db, tipo, i)}
