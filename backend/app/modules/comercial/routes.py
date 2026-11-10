"""API do Comercial (/api/comercial). O main.py descobre este `router` e exige login.

As permissões vêm do mapa padrão em app/core/permissoes.py (prefixos /comercial/oportunidades|funis, /atividades,
/comunicacoes, /propostas, /metas|forecast, /desempenho|dashboards|indicadores, /playbooks|modelos, /hoje); aqui só
refinamos as prévias, que não gravam nada e por isso exigem apenas `ver`.
"""

from fastapi import APIRouter

from app.core.permissoes import adicionar_regras
from app.modules.comercial import rotas_gestao, rotas_oportunidades, rotas_trabalho

adicionar_regras([
    ("POST", r"/comercial/indicadores/previa$", "comercial.desempenho.ver"),
    ("POST", r"/comercial/modelos/\d+/previa$", "comercial.recursos.ver"),
])

router = APIRouter(prefix="/comercial")
router.include_router(rotas_oportunidades.router)
router.include_router(rotas_trabalho.router)
router.include_router(rotas_gestao.router)
