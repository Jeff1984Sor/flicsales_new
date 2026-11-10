"""Orquestração: motor de automações (ativada_em; registro criado e detalhe da execução — também usados pelos avisos
internos de "Notificar responsável") e estado do teste das integrações. Sem tabela nova.

Revision ID: 0002_orquestracao
Revises: 0001
Create Date: 2026-11-10 15:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

import app.core.db
from alembic import op

revision: str = '0002_orquestracao'
down_revision: str | Sequence[str] | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('automacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ativada_em', app.core.db.UtcDateTime(timezone=True), nullable=True))
    with op.batch_alter_table('automacao_execucao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('registro_criado', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('detalhe', sa.Text(), nullable=True))
    with op.batch_alter_table('integracao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('testado_em', app.core.db.UtcDateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('aguardando_conector', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('integracao', schema=None) as batch_op:
        batch_op.drop_column('aguardando_conector')
        batch_op.drop_column('testado_em')
    with op.batch_alter_table('automacao_execucao', schema=None) as batch_op:
        batch_op.drop_column('detalhe')
        batch_op.drop_column('registro_criado')
    with op.batch_alter_table('automacao', schema=None) as batch_op:
        batch_op.drop_column('ativada_em')
