"""Dados da Receita Federal persistidos na empresa (gravados por "Atualizar pela Receita"): CNAE principal e
secundários, natureza jurídica, capital social, situação cadastral, data de abertura e quando foi consultado.

Revision ID: 0004_dados_receita
Revises: 0003_enderecos
Create Date: 2026-11-10 21:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

import app.core.db
from alembic import op

revision: str = '0004_dados_receita'
down_revision: str | Sequence[str] | None = '0003_enderecos'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('empresa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cnae_principal', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('cnaes_secundarios', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('natureza_juridica', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('capital_social', sa.Numeric(precision=15, scale=2), nullable=True))
        batch_op.add_column(sa.Column('situacao_cadastral', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('data_abertura', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('receita_consultada_em', app.core.db.UtcDateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('empresa', schema=None) as batch_op:
        for nome in ('receita_consultada_em', 'data_abertura', 'situacao_cadastral', 'capital_social',
                     'natureza_juridica', 'cnaes_secundarios', 'cnae_principal'):
            batch_op.drop_column(nome)
