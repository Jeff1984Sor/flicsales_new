"""Perfis de acesso padrão: criação idempotente (usada pelo seed e pelo startup)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import PerfilAcesso
from app.core.permissoes import PERFIS_PADRAO


def garantir_padrao(db: Session) -> dict[str, PerfilAcesso]:
    """Cria os perfis padrão que faltarem. Os existentes NÃO são alterados (o administrador pode tê-los editado),
    exceto o Gestor (sistema), que sempre mantém acesso total."""
    existentes = {p.nome: p for p in db.scalars(select(PerfilAcesso))}
    for modelo in PERFIS_PADRAO:
        p = existentes.get(modelo["nome"])
        if p is None:
            p = PerfilAcesso(**modelo)
            db.add(p)
            existentes[p.nome] = p
        elif modelo["sistema"]:
            p.administrador = True
            p.sistema = True
    db.flush()
    return existentes
