"""Módulos de negócio do FlicSales OS: nucleo, comercial, financeiro, orquestracao.

Cada módulo é dono de `app/modules/<modulo>/` (models.py, routes.py com `router`, schemas.py, servico.py, tarefas.py).
Prefixos de API combinados com o frontend: /api/nucleo, /api/comercial, /api/financeiro, /api/orquestracao.
"""

import importlib
import pkgutil


def registrar_modelos() -> None:
    """Importa os modelos do core e de todo módulo com `models.py` (Base.metadata completo: create_all, Alembic)."""
    import app.core.models  # noqa: F401
    import app.modules as pacote

    for info in pkgutil.iter_modules(pacote.__path__):
        try:
            importlib.import_module(f"app.modules.{info.name}.models")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{info.name}.models":
                raise
