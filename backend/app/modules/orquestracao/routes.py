"""API /api/orquestracao: IA unificada, automações e integrações.

| Rota | Permissão |
|---|---|
| GET  /orquestracao/leitura?modulo=                       | orquestracao.ia.ver |
| GET  /orquestracao/ia/estado · /ia/conversas[/{id}/mensagens] | orquestracao.ia.ver |
| POST /orquestracao/ia/perguntar                          | orquestracao.ia.editar (grava a conversa) |
| POST /orquestracao/ia/enriquecer                         | orquestracao.ia.ver (+ ver do cadastro do objeto) |
| POST /orquestracao/ia/comunicacoes/{id}/analisar         | comercial.comunicacoes.editar (+ orquestracao.ia.ver) |
| POST /orquestracao/acoes/executar                        | orquestracao.ia.editar (+ comercial.atividades.editar) |
| /orquestracao/automacoes*                                | orquestracao.automacoes.ver/editar (+ acesso à área) |
| GET  /orquestracao/automacoes/avisos                     | livre (só os avisos do próprio usuário) |
| /orquestracao/integracoes*                               | orquestracao.integracoes.ver/editar |
| /orquestracao/integracoes/whatsapp/evolution[/instancias|testar|qrcode] | orquestracao.integracoes.ver/editar |
| GET  /orquestracao/consumo                               | nucleo.administracao.ver (Plano e consumo) |
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import hoje
from app.core.deps import Ctx
from app.core.models import Usuario
from app.core.notificador import definir_notificador
from app.core.permissoes import adicionar_regras
from app.modules.orquestracao import evolution, rotas_automacoes, rotas_ia, rotas_integracoes
from app.modules.orquestracao.models import Automacao, AutomacaoExecucao, IaMensagem

adicionar_regras([
    ("POST", r"/orquestracao/ia/comunicacoes/\d+/analisar$", "comercial.comunicacoes.editar"),
    ("POST", r"/orquestracao/acoes/executar$", "orquestracao.ia.editar"),
    ("POST", r"/orquestracao/ia/enriquecer$", "orquestracao.ia.ver"),  # + ver do cadastro (na rota); nada grava
    ("GET", r"/orquestracao/automacoes/avisos$", None),
    ("GET", r"/orquestracao/consumo$", "nucleo.administracao.ver"),
])

# código de recuperação de senha por WhatsApp sai pela Evolution da organização (Núcleo › Integrações › WhatsApp)
definir_notificador(evolution.NotificadorEvolution())

router = APIRouter(prefix="/orquestracao", tags=["orquestracao"])
router.include_router(rotas_ia.router)
router.include_router(rotas_automacoes.router)
router.include_router(rotas_integracoes.router)


class ConsumoOut(BaseModel):
    """Uso do mês corrente (fuso de negócio) da organização."""

    competencia: str  # "AAAA-MM"
    usuarios_ativos: int
    perguntas_ia_mes: int
    perguntas_ia_com_provedor_mes: int
    automacoes_ativas: int
    execucoes_mes: int


@router.get("/consumo", response_model=ConsumoOut)
def consumo(ctx: Ctx):
    """Plano e consumo: usuários ativos, perguntas à IA, automações ativas e execuções do mês (sem simulações)."""
    d = hoje()
    inicio = datetime(d.year, d.month, 1, tzinfo=ZoneInfo(settings.fuso))
    db = ctx.db
    perguntas = db.scalar(select(func.count(IaMensagem.id)).where(IaMensagem.quando >= inicio)) or 0
    com_provedor = db.scalar(select(func.count(IaMensagem.id)).where(IaMensagem.quando >= inicio,
                                                                      IaMensagem.origem == "ia")) or 0
    return ConsumoOut(
        competencia=f"{d.year:04d}-{d.month:02d}",
        usuarios_ativos=db.scalar(select(func.count(Usuario.id)).where(Usuario.ativo.is_(True))) or 0,
        perguntas_ia_mes=perguntas,
        perguntas_ia_com_provedor_mes=com_provedor,
        automacoes_ativas=db.scalar(select(func.count(Automacao.id)).where(Automacao.estado == "ativa")) or 0,
        execucoes_mes=db.scalar(select(func.count(AutomacaoExecucao.id)).where(
            AutomacaoExecucao.quando >= inicio, AutomacaoExecucao.simulacao.is_(False))) or 0,
    )
