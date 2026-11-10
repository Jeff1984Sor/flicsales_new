"""Regras de negócio do FlicSales OS como funções puras (sem banco, sem FastAPI, sem relógio implícito).

Toda regra violada levanta `RegraViolada("mensagem PT-BR")`. A API converte em HTTP 400 com `{"detail": mensagem}`
(handler em app/main.py), então a rota só chama o domínio — não precisa de try/except.
"""


class RegraViolada(Exception):
    """Regra de negócio violada. `mensagem` já está pronta para o usuário (vira o toast da tela)."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


__all__ = ["RegraViolada"]
