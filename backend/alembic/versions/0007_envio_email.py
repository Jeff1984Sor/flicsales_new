"""Envio de e-mail pelos usuários (11/2026): SMTP próprio opcional por usuário (`config_email_usuario`, senha cifrada).
Sem ele, os e-mails enviados por um usuário saem pelo SMTP da organização com Reply-To = e-mail do usuário.

Revision ID: 0007_envio_email
Revises: 0006_nucleo_parte2
Create Date: 2026-11-11 18:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

import app.core.db
from alembic import op

revision: str = '0007_envio_email'
down_revision: str | Sequence[str] | None = '0006_nucleo_parte2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('config_email_usuario',
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('remetente_nome', sa.String(length=150), nullable=False),
    sa.Column('remetente_email', sa.String(length=200), nullable=False),
    sa.Column('smtp_host', sa.String(length=200), nullable=False),
    sa.Column('smtp_porta', sa.Integer(), server_default='587', nullable=False),
    sa.Column('smtp_usuario', sa.String(length=200), nullable=True),
    sa.Column('smtp_senha_cifrada', sa.LargeBinary(), nullable=True),
    sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('criado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'],
                            name=op.f('fk_config_email_usuario_usuario_id_usuario')),
    sa.PrimaryKeyConstraint('usuario_id', name=op.f('pk_config_email_usuario'))
    )


def downgrade() -> None:
    op.drop_table('config_email_usuario')
