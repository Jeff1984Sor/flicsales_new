"""Peças comuns aos modelos dos módulos."""

from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column

# Dinheiro: sempre Numeric(15,2) (nunca float). Use `Dinheiro` como tipo da coluna.
Dinheiro = Numeric(15, 2, asdecimal=True)
ZERO = Decimal("0.00")


def coluna_dinheiro(*, nullable: bool = False, default: Decimal | None = None) -> Mapped[Decimal]:
    return mapped_column(Dinheiro, nullable=nullable, default=default)
