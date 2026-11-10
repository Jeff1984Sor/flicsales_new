"""Ponte Comercial → Financeiro: venda ganha vira recebíveis em rascunho, sem duplicar."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain import RegraViolada
from app.modules.comercial.models import Funil, Oportunidade
from app.modules.financeiro.servico import preparar_recebiveis_do_ganho
from app.modules.nucleo.models import Empresa


@pytest.fixture
def cenario(db, admin):
    empresa = Empresa(nome="Aurora Consultoria")
    funil = Funil(nome="Serviços B2B")
    db.add_all([empresa, funil])
    db.flush()
    op = Oportunidade(titulo="Projeto de consultoria", funil_id=funil.id, empresa_id=empresa.id,
                      responsavel_id=admin.id, valor_unico=Decimal("24000"))
    db.add(op)
    db.flush()
    return op, empresa, admin


def _preparar(db, op, empresa, usuario, **kw):
    args = dict(oportunidade_id=op.id, titulo=op.titulo, empresa_id=empresa.id, valor=Decimal("24000"),
                condicao="2 parcelas iguais", primeiro_vencimento=date(2026, 11, 20), responsavel_id=usuario.id)
    args.update(kw)
    return preparar_recebiveis_do_ganho(db, **args)


def test_ganho_gera_rascunhos_mensais(db, cenario):
    op, empresa, usuario = cenario
    titulos = _preparar(db, op, empresa, usuario)
    assert [(t.parcela, t.valor_original, t.vencimento, t.status) for t in titulos] == [
        (1, Decimal("12000.00"), date(2026, 11, 20), "rascunho"),
        (2, Decimal("12000.00"), date(2026, 12, 20), "rascunho"),
    ]
    assert all(t.direcao == "receber" and t.saldo == t.valor_original for t in titulos)
    assert titulos[0].descricao == "Projeto de consultoria • 1/2"


def test_ganhar_de_novo_nao_duplica(db, cenario):
    op, empresa, usuario = cenario
    _preparar(db, op, empresa, usuario)
    assert len(_preparar(db, op, empresa, usuario)) == 2


def test_sem_empresa_e_recusado(db, cenario):
    op, _, usuario = cenario
    with pytest.raises(RegraViolada):
        _preparar(db, op, cenario[1], usuario, empresa_id=None)
