"""Proposta automatizada + PDF (modelo de proposta) e WhatsApp pela Evolution API (11/2026).

- `modelo_proposta`: textos do documento (introdução, termos, rodapé), validade e condição padrão; um é o padrão.
- `proposta.modelo_proposta_id`: modelo usado para gerar o documento/PDF.
- `integracao.provedor|url|instancia`: conector WhatsApp "evolution" (URL da API, instância; a apikey vai no
  `segredo_cifrado`, somente escrita).

Revision ID: 0008_proposta_whatsapp
Revises: 0007_envio_email
Create Date: 2026-11-11 21:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

import app.core.db
from alembic import op

revision: str = '0008_proposta_whatsapp'
down_revision: str | Sequence[str] | None = '0007_envio_email'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('modelo_proposta',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=150), nullable=False),
    sa.Column('padrao', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('introducao', sa.Text(), nullable=True),
    sa.Column('termos', sa.Text(), nullable=True),
    sa.Column('rodape', sa.Text(), nullable=True),
    sa.Column('validade_dias', sa.Integer(), server_default='15', nullable=False),
    sa.Column('condicao_padrao', sa.String(length=40), nullable=True),
    sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('criado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_modelo_proposta'))
    )
    with op.batch_alter_table('proposta') as b:
        b.add_column(sa.Column('modelo_proposta_id', sa.Integer(), nullable=True))
        b.create_foreign_key(op.f('fk_proposta_modelo_proposta_id_modelo_proposta'), 'modelo_proposta',
                             ['modelo_proposta_id'], ['id'])
    with op.batch_alter_table('integracao') as b:
        b.add_column(sa.Column('provedor', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('url', sa.String(length=300), nullable=True))
        b.add_column(sa.Column('instancia', sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('integracao') as b:
        b.drop_column('instancia')
        b.drop_column('url')
        b.drop_column('provedor')
    with op.batch_alter_table('proposta') as b:
        b.drop_constraint(op.f('fk_proposta_modelo_proposta_id_modelo_proposta'), type_='foreignkey')
        b.drop_column('modelo_proposta_id')
    op.drop_table('modelo_proposta')
