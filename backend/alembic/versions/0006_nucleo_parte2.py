"""Ajustes do Núcleo, parte 2 (11/2026): vários telefones/e-mails na pessoa (cópia do e-mail/telefone atuais como
principal), desconto e recorrência no produto (+ campos personalizados de produto), campo personalizado "exibir na
etapa", preferência `visivel` e objeto produto, campos padrões configuráveis (`campo_padrao_config`), listas da Governança de ajustes
(`opcao_lista`, semeada com os portes, os segmentos e os motivos de perda já usados + exemplos), classificação do modelo
de comunicação e imagem da assinatura padrão da Identidade. Nada é apagado.

Revision ID: 0006_nucleo_parte2
Revises: 0005_nucleo_ajustes
Create Date: 2026-11-11 10:00:00

"""
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

import app.core.db
from alembic import op

revision: str = '0006_nucleo_parte2'
down_revision: str | Sequence[str] | None = '0005_nucleo_ajustes'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OBJETOS_NOVOS = "objeto IN ('empresa', 'pessoa', 'oportunidade', 'produto')"
OBJETOS_ANTIGOS = "objeto IN ('empresa', 'pessoa', 'oportunidade')"

# valores congelados nesta migração (o domínio pode evoluir: app.domain.listas.PADROES)
PADROES = {
    'porte': ('ME', 'EPP', 'Médio', 'Grande'),
    'segmento': ('Consultoria', 'Serviços', 'Gestão', 'Tecnologia', 'Indústria', 'Varejo', 'Saúde', 'Educação'),
    'motivo_perda': ('Preço', 'Concorrente', 'Sem orçamento', 'Sem resposta', 'Fora do momento', 'Escopo não atende'),
}
LIMITE = {'segmento': 100, 'porte': 30, 'motivo_perda': 120}


def _chave(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', s).strip()


def _copiar_contatos(conn) -> None:
    pessoa = sa.table('pessoa', sa.column('id', sa.Integer), sa.column('email', sa.String),
                      sa.column('telefone', sa.String), sa.column('emails', sa.JSON), sa.column('telefones', sa.JSON))
    for pid, email, telefone in conn.execute(sa.select(pessoa.c.id, pessoa.c.email, pessoa.c.telefone)).all():
        emails = [{'email': email.strip(), 'tipo': 'comercial', 'principal': True}] if (email or '').strip() else []
        telefones = ([{'numero': telefone.strip(), 'tipo': 'celular', 'principal': True}]
                     if (telefone or '').strip() else [])
        if emails or telefones:
            conn.execute(pessoa.update().where(pessoa.c.id == pid).values(emails=emails, telefones=telefones))


def _semear_listas(conn) -> None:
    agora = datetime.now(UTC)
    opcao = sa.table('opcao_lista', sa.column('tipo', sa.String), sa.column('nome', sa.String),
                     sa.column('ordem', sa.Integer), sa.column('ativo', sa.Boolean),
                     sa.column('criado_em', app.core.db.UtcDateTime()), sa.column('atualizado_em', app.core.db.UtcDateTime()))
    usados = {
        'segmento': [r[0] for r in conn.execute(sa.text('SELECT DISTINCT segmento FROM empresa WHERE segmento IS NOT NULL'))],
        'porte': [],
        'motivo_perda': [r[0] for r in conn.execute(
            sa.text('SELECT DISTINCT motivo_perda FROM oportunidade WHERE motivo_perda IS NOT NULL'))],
    }
    linhas = []
    for tipo, padroes in PADROES.items():
        vistos: set[str] = set()
        ordem = 0
        for v in (*padroes, *sorted({u for u in usados[tipo] if u}, key=_chave)):
            nome = re.sub(r'\s+', ' ', v or '').strip()
            if not nome or len(nome) > LIMITE[tipo] or _chave(nome) in vistos:
                continue
            vistos.add(_chave(nome))
            ordem += 1
            linhas.append({'tipo': tipo, 'nome': nome, 'ordem': ordem, 'ativo': True, 'criado_em': agora,
                           'atualizado_em': agora})
    if linhas:
        op.bulk_insert(opcao, linhas)


def upgrade() -> None:
    # pessoa: vários telefones e e-mails (o principal continua espelhado em email/telefone)
    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telefones', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('emails', sa.JSON(), server_default='[]', nullable=False))

    # produto: desconto, recorrência e campos personalizados
    with op.batch_alter_table('produto', schema=None) as batch_op:
        batch_op.add_column(sa.Column('desconto_tipo', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('desconto_valor', sa.Numeric(precision=15, scale=2), nullable=True))
        batch_op.add_column(sa.Column('frequencia', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('intervalo', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('dias_semana', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('campos_custom', sa.JSON(), server_default='{}', nullable=False))
        batch_op.create_check_constraint('desconto_tipo', "desconto_tipo IN ('percentual', 'valor')")
        batch_op.create_check_constraint('frequencia',
                                         "frequencia IN ('diaria', 'semanal', 'mensal', 'semestral', 'anual')")

    # campo personalizado: objeto produto e "exibir na etapa"
    with op.batch_alter_table('campo_custom', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_campo_custom_objeto'), type_='check')
        batch_op.create_check_constraint('objeto', OBJETOS_NOVOS)
        batch_op.add_column(sa.Column('exibir_funil_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('exibir_etapa_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('visivel', sa.Boolean(), server_default='1', nullable=False))
        batch_op.create_foreign_key(batch_op.f('fk_campo_custom_exibir_funil_id_funil'), 'funil',
                                    ['exibir_funil_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_campo_custom_exibir_etapa_id_etapa'), 'etapa',
                                    ['exibir_etapa_id'], ['id'])

    with op.batch_alter_table('identidade', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assinatura_imagem', sa.String(length=300), nullable=True))

    with op.batch_alter_table('modelo_comunicacao', schema=None) as batch_op:
        batch_op.add_column(sa.Column('classificacao', sa.String(length=12), server_default='comercial',
                                      nullable=False))
        batch_op.create_check_constraint('classificacao', "classificacao IN ('comercial', 'financeiro', 'geral')")

    op.create_table('campo_padrao_config',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('objeto', sa.String(length=15), nullable=False),
    sa.Column('campo', sa.String(length=60), nullable=False),
    sa.Column('obrigatorio', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('visivel', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('ordem', sa.Integer(), server_default='0', nullable=False),
    sa.Column('criado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.CheckConstraint(OBJETOS_NOVOS, name=op.f('ck_campo_padrao_config_objeto')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_campo_padrao_config')),
    sa.UniqueConstraint('objeto', 'campo', name='uq_campo_padrao_config_objeto_campo')
    )

    op.create_table('opcao_lista',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=15), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('ordem', sa.Integer(), server_default='0', nullable=False),
    sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('criado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', app.core.db.UtcDateTime(timezone=True), nullable=False),
    sa.CheckConstraint("tipo IN ('segmento', 'porte', 'motivo_perda')", name=op.f('ck_opcao_lista_tipo')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_opcao_lista')),
    sa.UniqueConstraint('tipo', 'nome', name='uq_opcao_lista_tipo_nome')
    )

    conn = op.get_bind()
    _copiar_contatos(conn)
    # produto recorrente antigo: mensal, a cada 1 mês (o texto da tela fica "Todo mês")
    conn.execute(sa.text("UPDATE produto SET frequencia = 'mensal', intervalo = 1 WHERE recorrente = :sim"),
                 {'sim': True})
    _semear_listas(conn)


def downgrade() -> None:
    op.drop_table('opcao_lista')
    op.drop_table('campo_padrao_config')

    with op.batch_alter_table('modelo_comunicacao', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_modelo_comunicacao_classificacao'), type_='check')
        batch_op.drop_column('classificacao')

    with op.batch_alter_table('identidade', schema=None) as batch_op:
        batch_op.drop_column('assinatura_imagem')

    with op.batch_alter_table('campo_custom', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_campo_custom_exibir_etapa_id_etapa'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_campo_custom_exibir_funil_id_funil'), type_='foreignkey')
        batch_op.drop_column('visivel')
        batch_op.drop_column('exibir_etapa_id')
        batch_op.drop_column('exibir_funil_id')
        batch_op.drop_constraint(op.f('ck_campo_custom_objeto'), type_='check')
        batch_op.create_check_constraint('objeto', OBJETOS_ANTIGOS)

    with op.batch_alter_table('produto', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_produto_frequencia'), type_='check')
        batch_op.drop_constraint(op.f('ck_produto_desconto_tipo'), type_='check')
        batch_op.drop_column('campos_custom')
        batch_op.drop_column('dias_semana')
        batch_op.drop_column('intervalo')
        batch_op.drop_column('frequencia')
        batch_op.drop_column('desconto_valor')
        batch_op.drop_column('desconto_tipo')

    with op.batch_alter_table('pessoa', schema=None) as batch_op:
        batch_op.drop_column('emails')
        batch_op.drop_column('telefones')
