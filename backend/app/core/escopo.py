"""Escopo "só meus registros" (opção do perfil; pensado para o Comercial).

Quem usa um perfil com `somente_meus_registros` só enxerga os registros de que é o RESPONSÁVEL
(`responsavel_id == usuario.id`). Administrador (Gestor) nunca é restrito.

CONTRATO para os módulos:
    consulta = escopo.filtrar_meus(ctx, select(Oportunidade), Oportunidade.responsavel_id)
    if not escopo.pode_acessar(ctx, oportunidade.responsavel_id): raise HTTPException(404, ...)
"""

from typing import Any

from app.core.models import Usuario


def usuario_restrito(usuario: Usuario) -> bool:
    p = usuario.perfil_acesso
    return bool(p and not p.administrador and p.somente_meus_registros)


def filtrar_meus(ctx: Any, consulta, coluna_responsavel):
    """Restringe `consulta` (select) às linhas em que o usuário logado é o responsável."""
    if not usuario_restrito(ctx.usuario):
        return consulta
    return consulta.where(coluna_responsavel == ctx.usuario.id)


def pode_acessar(ctx: Any, responsavel_id: int | None) -> bool:
    """Item específico: quem é restrito só abre o que é seu (responda 404, não 403, para não revelar que existe)."""
    return not usuario_restrito(ctx.usuario) or responsavel_id == ctx.usuario.id
