"""Seed da demonstração (idempotente, datas relativas, números do protótipo) e migração 0001 (SQLite limpo = modelos)."""

import re
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

from sqlalchemy import func, select

from app import seed
from app.core.models import Identidade, PerfilAcesso, Usuario
from app.domain import caixa, leitura
from app.modules.comercial.models import Atividade, Comunicacao, Etapa, Oportunidade
from app.modules.financeiro.models import Recorrencia, Titulo
from app.modules.nucleo.models import ContaFinanceira, Empresa
from tests.conftest import auth, entrar

HOJE = date(2026, 11, 10)
BACKEND = Path(seed.__file__).parents[1]


def _contar(db, modelo) -> int:
    return db.scalar(select(func.count()).select_from(modelo))


def test_seed_cria_os_dados_do_prototipo_e_e_idempotente(db):
    assert seed.semear(db, HOJE) is True
    contagem = {m.__name__: _contar(db, m) for m in (Usuario, Empresa, Oportunidade, Titulo, Atividade, Comunicacao,
                                                     Etapa, Recorrencia)}
    assert seed.semear(db, HOJE) is False  # de novo: nada duplica
    assert {m.__name__: _contar(db, m) for m in (Usuario, Empresa, Oportunidade, Titulo, Atividade, Comunicacao,
                                                Etapa, Recorrencia)} == contagem
    assert contagem == {"Usuario": 4, "Empresa": 9, "Oportunidade": 4, "Titulo": 5, "Atividade": 3, "Comunicacao": 3,
                        "Etapa": 4, "Recorrencia": 1}
    assert db.scalar(select(Identidade.nome_exibicao)) == "FlicSales Demo"
    assert sorted(db.scalars(select(PerfilAcesso.nome))) == ["Comercial", "Financeiro", "Gestor", "Somente leitura"]
    perfil = {u.login: u.perfil_acesso.nome for u in db.scalars(select(Usuario))}
    assert perfil == {"francine": "Gestor", "marina": "Comercial", "lucas": "Comercial", "fin": "Financeiro"}
    etapas = [(e.nome, e.probabilidade, e.limite_dias) for e in db.scalars(select(Etapa).order_by(Etapa.ordem))]
    assert etapas == [("Entrada", 10, 2), ("Discovery", 25, 7), ("Proposta", 50, 10), ("Negociação", 75, 14)]


def test_seed_bate_com_o_caixa_do_prototipo(db):
    seed.semear(db, HOJE)
    contas = [caixa.Conta(c.id, c.saldo_inicial, c.data_base) for c in db.scalars(select(ContaFinanceira))]
    saldo = caixa.saldo_gerencial(contas, [], [])
    titulos = [caixa.TituloAberto(t.direcao, t.status, t.saldo) for t in db.scalars(select(Titulo))]
    p = caixa.projecao(saldo, titulos)
    assert (p.saldo_atual, p.entradas_abertas, p.saidas_abertas, p.saldo_projetado) == (
        D("25000.00"), D("19300.00"), D("7200.00"), D("37100.00"))
    pagar = {t.descricao: t.aprovacao for t in db.scalars(select(Titulo).where(Titulo.direcao == "pagar"))}
    assert pagar == {"Aluguel": "pendente", "Serviços de tecnologia": "aprovado"}


def test_seed_usa_datas_relativas_e_so_ponto_norte_vence(db):
    outro_dia = date(2027, 3, 20)
    seed.semear(db, outro_dia)
    vencidos = [t.descricao for t in db.scalars(select(Titulo)) if t.vencimento < outro_dia]
    assert vencidos == ["Consultoria • parcela 1/2"]
    assert db.scalar(select(ContaFinanceira.data_base)) == outro_dia - timedelta(days=30)
    mensalidade = db.scalar(select(Titulo).where(Titulo.origem_recorrencia_id.is_not(None)))
    assert mensalidade.vencimento.day == 12 and mensalidade.competencia == f"{mensalidade.vencimento:%Y-%m}"


def test_seed_alimenta_a_leitura_do_momento(db):
    seed.semear(db, HOJE)
    empresas = {e.id: e.nome for e in db.scalars(select(Empresa))}
    etapas = {e.id: e for e in db.scalars(select(Etapa))}
    r = leitura.ler_momento(
        hoje=HOJE,
        titulos=[leitura.TituloResumo(t.id, empresas[t.empresa_id], t.descricao, t.direcao, t.status, t.vencimento,
                                      t.saldo) for t in db.scalars(select(Titulo))],
        oportunidades=[leitura.OportunidadeResumo(o.id, o.titulo, empresas[o.empresa_id], etapas[o.etapa_id].nome,
                                                  o.valor_unico, o.proxima_acao, o.entrou_etapa_em,
                                                  etapas[o.etapa_id].limite_dias) for o in db.scalars(select(Oportunidade))],
        atividades=[leitura.AtividadeResumo(a.id, a.assunto, a.prazo, a.status) for a in db.scalars(select(Atividade))])
    assert r["titulo"] == "Recebível vencido pede ação" and "Ponto Norte" in r["evidencias"][0]["texto"]
    textos = " | ".join(e["texto"] for e in r["evidencias"])
    assert "Consultoria recorrente" in textos  # sem próxima ação
    assert "Diagnóstico estratégico está há 9 dias em Discovery" in textos  # limite de 7 dias
    assert "Retomar proposta da Vértice" in textos  # atividade atrasada


def test_usuarios_do_seed_entram_com_a_senha_de_demonstracao(client, db):
    seed.semear(db, HOJE)
    r = entrar(client, "francine", seed.SENHA_DEMO)
    assert r.status_code == 200 and r.json()["usuario"]["administrador"] is True
    me = client.get("/api/auth/me", headers=auth(entrar(client, "marina", seed.SENHA_DEMO).json()["access_token"]))
    assert me.json()["perfil_acesso_nome"] == "Comercial" and "comercial.oportunidades.editar" in me.json()["permissoes"]


def test_senha_fixa_so_a_de_demonstracao_do_seed():
    suspeitos = []
    for arq in (BACKEND / "app").rglob("*.py"):
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"""(senha|password|secret)\w*\s*=\s*["'][^"']{6,}["']""", linha, re.I) and \
                    "_DEV" not in linha and "SENHA_DEMO" not in linha:
                suspeitos.append(f"{arq.name}:{n}: {linha.strip()}")
    assert not suspeitos, suspeitos


def test_seed_recusa_fora_de_dev():
    import os

    env = {**os.environ, "AMBIENTE": "hml"}
    r = subprocess.run([sys.executable, "-c", "from app import seed; seed._so_dev()"], capture_output=True, text=True,
                       cwd=BACKEND, env=env)
    assert r.returncode != 0


# ---------------------------------------------------------------------------------------------- migração 0001
def test_migracao_0001_num_sqlite_limpo_bate_com_os_modelos(tmp_path):
    """`alembic upgrade head` num banco vazio e depois compara com os modelos: nenhuma diferença."""
    import os

    url = f"sqlite:///{(tmp_path / 'limpo.db').as_posix()}"
    codigo = (
        "from alembic.config import Config\n"
        "from alembic import command\n"
        "from alembic.migration import MigrationContext\n"
        "from alembic.autogenerate import compare_metadata\n"
        "from app.core.db import engine, Base\n"
        "from app.modules import registrar_modelos\n"
        "registrar_modelos()\n"
        "cfg = Config('alembic.ini'); cfg.attributes['configure_logger'] = False\n"
        "command.upgrade(cfg, 'head')\n"
        "with engine.connect() as c:\n"
        "    print('DIFF', compare_metadata(MigrationContext.configure(c), Base.metadata))\n"
        "    print('TABELAS', len(c.exec_driver_sql(\"select name from sqlite_master where type='table'\").all()))\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=BACKEND,
                       env={**os.environ, "DATABASE_URL": url})
    assert r.returncode == 0, r.stderr[-2000:]
    assert "DIFF []" in r.stdout, r.stdout
    assert "TABELAS 40" in r.stdout, r.stdout  # 39 (0003: empresa_socio, empresa_anexo; 0004 só colunas) + alembic_version


def test_unicos_da_especificacao_existem():
    from app.modules.financeiro.models import Titulo
    from app.modules.orquestracao.models import AutomacaoExecucao

    unicos = {tuple(c.name for c in u.columns) for u in Titulo.__table__.constraints if u.__class__.__name__ == "UniqueConstraint"}
    assert {("origem_oportunidade_id", "parcela"), ("origem_recorrencia_id", "competencia")} <= unicos
    assert AutomacaoExecucao.__table__.c.chave_idempotencia.unique


def test_titulo_duplicado_por_parcela_e_recusado_pelo_banco(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    seed.semear(db, HOJE)
    op = db.scalar(select(Oportunidade).limit(1))
    fin = db.scalar(select(Usuario).where(Usuario.login == "fin"))
    kw = dict(direcao="receber", empresa_id=op.empresa_id, descricao="x", vencimento=HOJE, valor_original=D("10"),
              saldo=D("10"), responsavel_id=fin.id, origem_oportunidade_id=op.id, parcela=1, parcelas_total=1)
    db.add(Titulo(**kw))
    db.commit()
    db.add(Titulo(**kw))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_empresa_com_nome_igual_normalizado_e_recusada(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    db.add(Empresa(nome="Aurora Consultoria"))
    db.commit()
    db.add(Empresa(nome="  aurora   CONSULTÓRIA"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    e = db.scalar(select(Empresa))
    e.papeis = ["fornecedor", "cliente"]
    db.commit()
    assert e.papeis == ["cliente", "fornecedor"] and e.nome_chave == "aurora consultoria"
