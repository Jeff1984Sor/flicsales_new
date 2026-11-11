"""Integrações: ver (orquestracao.integracoes.ver), configurar/testar/revogar (orquestracao.integracoes.editar).
Segredo cifrado e somente escrita: a API só devolve "configurado" + os 4 últimos caracteres."""

from fastapi import APIRouter, HTTPException

from app.core import audit, segredos
from app.core.deps import Ctx
from app.core.models import Usuario
from app.domain import RegraViolada
from app.modules.orquestracao import evolution as evo
from app.modules.orquestracao import integracoes as integ
from app.modules.orquestracao.schemas import (
    EvolutionBuscarIn,
    EvolutionIn,
    EvolutionOut,
    InstanciaEvolutionOut,
    IntegracaoIn,
    IntegracaoOut,
    QrCodeOut,
    TesteWhatsAppOut,
)

router = APIRouter(prefix="/integracoes")


def _tipo(tipo: str) -> str:
    if tipo not in integ.CATALOGO:
        raise HTTPException(404, "Integração não encontrada.")
    return tipo


# ------------------------------------------------------------------------------- WhatsApp pela Evolution API (0008)
@router.get("/whatsapp/evolution", response_model=EvolutionOut)
def ler_evolution(ctx: Ctx):
    return evo.saida(evo.integracao(ctx.db))


@router.put("/whatsapp/evolution", response_model=EvolutionOut)
def salvar_evolution(dados: EvolutionIn, ctx: Ctx):
    """URL (http/https, sem barra final), apikey somente escrita (vazia = mantém) e instância. Mudou algo → precisa
    testar de novo (fica desconectado). A auditoria nunca leva a chave."""
    d = dados.model_dump(exclude_unset=True)
    url = evo.validar_url(d["url"])
    i = integ.obter_ou_criar(ctx.db, "whatsapp")
    antes = audit.snapshot(i)
    novos = {"provedor": evo.PROVEDOR, "url": url}
    if "instancia" in d:
        novos["instancia"] = evo.validar_instancia(d["instancia"])
    mudou = False
    for k, v in novos.items():
        if getattr(i, k) != v:
            setattr(i, k, v)
            mudou = True
    apikey = (d.get("apikey") or "").strip()
    if apikey:
        if len(apikey) < 8:
            raise RegraViolada("A API key parece incompleta (mínimo de 8 caracteres). Copie de novo do servidor.")
        if apikey != evo.apikey_salva(i):
            i.segredo_cifrado = segredos.cifrar_texto(apikey)
            mudou = True
    if mudou:
        i.estado, i.aguardando_conector, i.conectado_em = "desconectado", False, None
    ctx.db.flush()
    x, y = audit.diff(antes, audit.snapshot(i))
    ctx.auditar("integracao.configurar", "integracao", i.id,
                descricao="WhatsApp (Evolution)" + (" · API key alterada" if apikey else ""), antes=x, depois=y)
    ctx.db.commit()
    return evo.saida(i)


@router.post("/whatsapp/evolution/instancias", response_model=list[InstanciaEvolutionOut])
def instancias_evolution(ctx: Ctx, dados: EvolutionBuscarIn | None = None):
    """Lista as instâncias do servidor (para escolher na tela). Usa a URL/apikey do formulário ou as salvas."""
    d = dados or EvolutionBuscarIn()
    cfg = evo.config_de(evo.integracao(ctx.db), url=d.url, apikey=d.apikey)
    try:
        return evo.cliente(cfg).instancias()
    except evo.ErroEvolution as e:
        raise RegraViolada(f"Não foi possível buscar as instâncias: {e.mensagem}.") from None


@router.post("/whatsapp/evolution/testar", response_model=TesteWhatsAppOut)
def testar_evolution(ctx: Ctx):
    i = integ.obter_ou_criar(ctx.db, "whatsapp")
    antes = audit.snapshot(i)
    r = evo.testar(i)
    ctx.db.flush()
    x, y = audit.diff(antes, audit.snapshot(i))
    for k in ("testado_em", "atualizado_em"):  # a tela consulta a cada 5 s com o QR aberto: só audita mudança real
        x.pop(k, None)
        y.pop(k, None)
    if x or y:
        ctx.auditar("integracao.testar", "integracao", i.id, descricao=r["mensagem"], antes=x, depois=y)
    ctx.db.commit()
    return r


@router.post("/whatsapp/evolution/qrcode", response_model=QrCodeOut)
def qrcode_evolution(ctx: Ctx):
    """QR code para conectar o número (cria a instância na Evolution se ela ainda não existir)."""
    i = evo.integracao(ctx.db)
    if i is None:
        raise RegraViolada("Salve a URL e a API key da Evolution antes de conectar o número.")
    try:
        r = evo.qrcode(i)
    except RegraViolada:
        ctx.db.commit()  # guarda o último erro (sem a chave)
        raise
    ctx.auditar("integracao.qrcode", "integracao", i.id, descricao=f"QR code solicitado para a instância {i.instancia}")
    ctx.db.commit()
    return r


# ------------------------------------------------------------------------------- genéricas
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
