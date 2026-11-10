"""Endereço estruturado em empresa e pessoa (cep, logradouro, número, complemento, bairro, cidade, uf) e a marca
`pessoa.usa_endereco_da_empresa` (padrão ligada). O texto antigo `empresa.endereco` fica: nada é apagado.
Também cria `empresa_socio` (quadro societário da consulta CNPJ) e `empresa_anexo` (arquivos da empresa).

Revision ID: 0003_enderecos
Revises: 0002_orquestracao
Create Date: 2026-11-10 18:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

import app.core.db
from alembic import op

revision: str = '0003_enderecos'
down_revision: str | Sequence[str] | None = '0002_orquestracao'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENDERECO = (('cep', 9), ('logradouro', 200), ('numero', 20), ('complemento', 100), ('bairro', 100), ('cidade', 100),
             ('uf', 2))


def upgrade() -> None:
    for tabela in ('empresa', 'pessoa'):
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            for nome, tamanho in _ENDERECO:
                batch_op.add_column(sa.Column(nome, sa.String(length=tamanho), nullable=True))
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('usa_endereco_da_empresa', sa.Boolean(), server_default='1', nullable=False))

    op.create_table('empresa_socio',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('qualificacao', sa.String(length=120), nullable=True),
    sa.Column('documento', sa.String(length=18), nullable=True),
    sa.Column('data_entrada', sa.Date(), nullable=True),
    sa.Column('faixa_etaria', sa.String(length=40), nullable=True),
    sa.Column('criado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_empresa_socio_empresa_id_empresa')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_empresa_socio'))
    )
    with op.batch_alter_table('empresa_socio', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_empresa_socio_empresa_id'), ['empresa_id'], unique=False)

    op.create_table('empresa_anexo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('tipo', sa.String(length=30), nullable=False),
    sa.Column('mime', sa.String(length=100), nullable=True),
    sa.Column('tamanho', sa.Integer(), nullable=False),
    sa.Column('caminho', sa.String(length=300), nullable=False),
    sa.Column('enviado_por_id', sa.Integer(), nullable=True),
    sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('criado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.CheckConstraint("tipo IN ('cartao_cnpj', 'contrato', 'documento', 'outro')", name=op.f('ck_empresa_anexo_tipo')),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_empresa_anexo_empresa_id_empresa')),
    sa.ForeignKeyConstraint(['enviado_por_id'], ['usuario.id'], name=op.f('fk_empresa_anexo_enviado_por_id_usuario')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_empresa_anexo'))
    )
    with op.batch_alter_table('empresa_anexo', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_empresa_anexo_empresa_id'), ['empresa_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('empresa_anexo', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_empresa_anexo_empresa_id'))
    op.drop_table('empresa_anexo')
    with op.batch_alter_table('empresa_socio', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_empresa_socio_empresa_id'))
    op.drop_table('empresa_socio')
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.drop_column('usa_endereco_da_empresa')
    for tabela in ('pessoa', 'empresa'):
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            for nome, _ in reversed(_ENDERECO):
                batch_op.drop_column(nome)
