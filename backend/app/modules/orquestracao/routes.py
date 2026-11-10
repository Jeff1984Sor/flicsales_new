"""API /api/orquestracao: IA unificada, automações e integrações.

| Rota | Permissão |
|---|---|
| GET  /orquestracao/leitura?modulo=                       | orquestracao.ia.ver |
| GET  /orquestracao/ia/estado · /ia/conversas[/{id}/mensagens] | orquestracao.ia.ver |
| POST /orquestracao/ia/perguntar                          | orquestracao.ia.editar (grava a conversa) |
| POST /orquestracao/ia/comunicacoes/{id}/analisar         | comercial.comunicacoes.editar (+ orquestracao.ia.ver) |
| POST /orquestracao/acoes/executar                        | orquestracao.ia.editar (+ comercial.atividades.editar) |
| /orquestracao/automacoes*                                | orquestracao.automacoes.ver/editar (+ acesso à área) |
| GET  /orquestracao/automacoes/avisos                     | livre (só os avisos do próprio usuário) |
| /orquestracao/integracoes*                               | orquestracao.integracoes.ver/editar |
"""

from fastapi import APIRouter

from app.core.permissoes import adicionar_regras
from app.modules.orquestracao import rotas_automacoes, rotas_ia, rotas_integracoes

adicionar_regras([
    ("POST", r"/orquestracao/ia/comunicacoes/\d+/analisar$", "comercial.comunicacoes.editar"),
    ("POST", r"/orquestracao/acoes/executar$", "orquestracao.ia.editar"),
    ("GET", r"/orquestracao/automacoes/avisos$", None),
])

router = APIRouter(prefix="/orquestracao", tags=["orquestracao"])
router.include_router(rotas_ia.router)
router.include_router(rotas_automacoes.router)
router.include_router(rotas_integracoes.router)
