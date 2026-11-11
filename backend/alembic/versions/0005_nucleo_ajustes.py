"""Ajustes do Núcleo (11/2026): LGPD na pessoa (base legal + permissões de comunicação), campos personalizados
"multipla" (seleção múltipla) e "link" (hiperlink), e assinatura de e-mail por usuário (texto + imagem no storage).

Revision ID: 0005_nucleo_ajustes
Revises: 0004_dados_receita
Create Date: 2026-11-10 23:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '0005_nucleo_ajustes'
down_revision: str | Sequence[str] | None = '0004_dados_receita'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_NOVOS = "tipo IN ('texto', 'numero', 'moeda', 'data', 'sim_nao', 'lista', 'multipla', 'link')"
TIPOS_ANTIGOS = "tipo IN ('texto', 'numero', 'moeda', 'data', 'sim_nao', 'lista')"


def upgrade() -> None:
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('base_legal', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('permissoes_comunicacao', sa.JSON(), server_default='[]', nullable=False))

    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assinatura_email', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_imagem', sa.String(length=300), nullable=True))

    with op.batch_alter_table('campo_custom', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_campo_custom_tipo'), type_='check')
        batch_op.create_check_constraint('tipo', TIPOS_NOVOS)


def downgrade() -> None:
    with op.batch_alter_table('campo_custom', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_campo_custom_tipo'), type_='check')
        batch_op.create_check_constraint('tipo', TIPOS_ANTIGOS)

    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('assinatura_imagem')
        batch_op.drop_column('assinatura_email')

    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.drop_column('permissoes_comunicacao')
        batch_op.drop_column('base_legal')
