"""API do Comercial (/api/comercial). O main.py descobre este `router` e exige login.

As permissões vêm do mapa padrão em app/core/permissoes.py (prefixos /comercial/oportunidades|funis, /atividades,
/comunicacoes, /propostas, /metas|forecast, /desempenho|dashboards|indicadores, /playbooks|modelos, /hoje); aqui só
refinamos as prévias, que não gravam nada e por isso exigem apenas `ver`.
"""

from fastapi import APIRouter

from app.core.permissoes import adicionar_regras
from app.modules.comercial import (
    rotas_gestao,
    rotas_oportunidades,
    rotas_proposta_documento,
    rotas_trabalho,
    rotas_whatsapp,  # WhatsApp pela Evolution (contrato 11/2026, parte B)
)

adicionar_regras([
    ("POST", r"/comercial/indicadores/previa$", "comercial.desempenho.ver"),
    ("POST", r"/comercial/modelos/\d+/previa$", "comercial.recursos.ver"),
    # proposta automatizada + PDF (contrato 11/2026)
    ("*", r"/comercial/modelos-proposta", "comercial.recursos.*e"),
    ("POST", r"/comercial/oportunidades/\d+/proposta-automatica$", "comercial.propostas.editar"),
])

router = APIRouter(prefix="/comercial")
router.include_router(rotas_oportunidades.router)
router.include_router(rotas_trabalho.router)
router.include_router(rotas_gestao.router)
router.include_router(rotas_proposta_documento.router)
router.include_router(rotas_whatsapp.router)
