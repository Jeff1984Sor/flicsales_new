"""WhatsApp enviado pelo usuário no Comercial (contrato proposta + WhatsApp 11/2026, parte B3).

Mesmas permissões do "✉ Enviar e-mail" (mapa padrão: /comercial/comunicacoes* → comercial.comunicacoes.editar,
/comercial/propostas* → comercial.propostas.editar). O envio passa por `app.core.envio.enviar_whatsapp_por_usuario`
(telefone com DDI 55, opt-out, Evolution conectada, assinatura "— <nome>").
"""

from fastapi import APIRouter

from app.core import audit, envio
from app.core.deps import Ctx
from app.core.schemas import EnvioWhatsAppIn, EnvioWhatsAppOut
from app.domain import RegraViolada
from app.domain import envio as dom_envio
from app.domain.modelo_proposta import nome_arquivo_pdf
from app.modules.comercial import servico as sv
from app.modules.comercial.models import Comunicacao, Proposta
from app.modules.comercial.rotas_gestao import STATUS_ROTULO

router = APIRouter()


class ComunicacaoWhatsAppIn(EnvioWhatsAppIn):
    empresa_id: int | None = None
    oportunidade_id: int | None = None


class PropostaWhatsAppIn(EnvioWhatsAppIn):
    anexar_pdf: bool = True


def _titulo(texto: str) -> str:
    primeira = " ".join(texto.splitlines()[0].split()) if texto else ""
    return f"WhatsApp: {primeira[:80]}" if primeira else "WhatsApp"


@router.post("/comunicacoes/enviar-whatsapp", response_model=EnvioWhatsAppOut)
def enviar_whatsapp_comunicacao(dados: ComunicacaoWhatsAppIn, ctx: Ctx):
    """Envia pelo WhatsApp e registra a Comunicação canal WhatsApp (conteúdo "Para: …" + texto)."""
    if ctx.somente_meus_registros() and dados.oportunidade_id is None:
        raise RegraViolada("Vincule a mensagem a uma das suas oportunidades.")
    op = sv.conferir_oportunidade_vinculo(ctx, dados.oportunidade_id)
    sv.conferir_empresa(ctx.db, dados.empresa_id)
    empresa_id = dados.empresa_id if dados.empresa_id is not None else (op.empresa_id if op else None)
    sv.conferir_modelo_comercial(ctx.db, dados.modelo_id)
    m = envio.enviar_whatsapp_por_usuario(ctx.db, ctx.usuario, para=dados.para, texto=dados.texto)
    c = Comunicacao(canal="whatsapp", titulo=_titulo(dados.texto), conteudo=dom_envio.conteudo_comunicacao_whatsapp(m),
                    data=sv.hoje(), empresa_id=empresa_id, oportunidade_id=dados.oportunidade_id)
    ctx.db.add(c)
    ctx.db.flush()
    destino = ", ".join(dom_envio.formatar_whatsapp(n) for n in m.para)
    if op is not None:
        sv.registrar_evento(ctx.db, op.id, "nota", f"WhatsApp enviado para {destino}", ctx.usuario.id)
    ctx.auditar("comunicacao.enviar_whatsapp", "comunicacao", c.id, descricao=f"WhatsApp para {destino}",
                depois={"para": m.para, "modelo_id": dados.modelo_id, "empresa_id": empresa_id,
                        "oportunidade_id": c.oportunidade_id})
    ctx.db.commit()
    return EnvioWhatsAppOut(enviado_para=m.para, registro=f"Comunicação #{c.id} registrada (WhatsApp).")


@router.post("/propostas/{proposta_id}/enviar-whatsapp", response_model=EnvioWhatsAppOut)
def enviar_whatsapp_proposta(proposta_id: int, dados: PropostaWhatsAppIn, ctx: Ctx):
    """Envia a proposta pelo WhatsApp (PDF como documento, se `anexar_pdf`), registra a Comunicação na oportunidade e
    marca Enviada quando a regra de status permitir (a mesma do e-mail)."""
    db = ctx.db
    p = sv.obter(ctx, Proposta, proposta_id, "Proposta não encontrada.")
    sv.conferir_modelo_comercial(db, dados.modelo_id)
    documento = None
    if dados.anexar_pdf:  # mesmo PDF de GET /propostas/{id}/pdf
        documento = (nome_arquivo_pdf(p.id, p.versao), sv.gerar_pdf_proposta(db, p), "application/pdf")
    m = envio.enviar_whatsapp_por_usuario(db, ctx.usuario, para=dados.para, texto=dados.texto, documento=documento)
    antes = audit.snapshot(p)
    c = Comunicacao(canal="whatsapp", titulo=f"Proposta {p.titulo} v{p.versao}"[:200],
                    conteudo=dom_envio.conteudo_comunicacao_whatsapp(m), data=sv.hoje(), empresa_id=p.empresa_id,
                    oportunidade_id=p.oportunidade_id)
    db.add(c)
    novo_status = dom_envio.status_proposta_apos_envio(p.status, p.desconto_pct)
    mudou = novo_status != p.status
    p.status = novo_status
    db.flush()
    destino = ", ".join(dom_envio.formatar_whatsapp(n) for n in m.para)
    sv.registrar_evento(db, p.oportunidade_id, "proposta",
                        f"Proposta v{p.versao} enviada por WhatsApp para {destino}"
                        + (" (status: Enviada)" if mudou else ""), ctx.usuario.id)
    partes = [f"Comunicação #{c.id} registrada na oportunidade."]
    partes.append("Proposta marcada como Enviada." if mudou else
                  f"Status mantido: {STATUS_ROTULO.get(p.status, p.status)}.")
    if documento:
        partes.append(f"PDF enviado como documento: {documento[0]}.")
    a, d = audit.diff(antes, audit.snapshot(p))
    ctx.auditar("proposta.enviar_whatsapp", "proposta", p.id, descricao=f"{p.titulo} v{p.versao}: WhatsApp para {destino}",
                antes=a, depois={**d, "para": m.para, "modelo_id": dados.modelo_id, "pdf": bool(documento),
                                 "comunicacao_id": c.id})
    db.commit()
    return EnvioWhatsAppOut(enviado_para=m.para, registro=" ".join(partes))
