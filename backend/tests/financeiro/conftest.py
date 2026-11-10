"""Cenário financeiro mínimo: empresas, categoria, centro de custo, conta (data-base 30 dias atrás) e usuários."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.core.db import hoje
from app.modules.nucleo.models import Categoria, CentroCusto, ContaFinanceira, Empresa
from tests.conftest import auth, criar_usuario, entrar

D = Decimal


@dataclass
class Cenario:
    hoje: date
    cliente: Empresa
    fornecedor: Empresa
    receita: Categoria
    centro: CentroCusto
    conta: ContaFinanceira
    conta2: ContaFinanceira
    admin_id: int
    h_admin: dict
    h_fin: dict
    h_leitura: dict
    fin_id: int


@pytest.fixture
def cen(db, client, admin, token_admin) -> Cenario:
    h = hoje()
    cliente = Empresa(nome="Ponto Norte", papel_cliente=True)
    fornecedor = Empresa(nome="Espaço Compartilhado", papel_fornecedor=True)
    receita = Categoria(nome="Serviços prestados", natureza="receita")
    centro = CentroCusto(nome="Operação", codigo="OP")
    conta = ContaFinanceira(nome="Conta operacional", saldo_inicial=D("25000.00"), data_base=h - timedelta(days=30))
    conta2 = ContaFinanceira(nome="Reserva", saldo_inicial=D("1000.00"), data_base=h - timedelta(days=30))
    db.add_all([cliente, fornecedor, receita, centro, conta, conta2])
    db.commit()
    fin = criar_usuario(db, "Financeiro", email="fin@exemplo.com")
    criar_usuario(db, "Somente leitura", email="leitor@exemplo.com")
    h_fin = auth(entrar(client, "fin").json()["access_token"])
    h_leitura = auth(entrar(client, "leitor").json()["access_token"])
    return Cenario(h, cliente, fornecedor, receita, centro, conta, conta2, admin.id, auth(token_admin), h_fin,
                   h_leitura, fin.id)


def novo_titulo(client, cen: Cenario, *, direcao="receber", valor="1000.00", vencimento: date | None = None,
                headers=None, **extra) -> dict:
    corpo = {"direcao": direcao, "empresa_id": (cen.cliente if direcao == "receber" else cen.fornecedor).id,
             "descricao": extra.pop("descricao", "Consultoria"), "vencimento": str(vencimento or cen.hoje),
             "valor_original": valor, "responsavel_id": cen.admin_id, **extra}
    r = client.post("/api/financeiro/titulos", json=corpo, headers=headers or cen.h_admin)
    assert r.status_code == 201, r.text
    return r.json()


def baixa(client, cen: Cenario, titulo_id: int, valor: str, *, data: date | None = None, conta_id=None,
          headers=None):
    return client.post(f"/api/financeiro/titulos/{titulo_id}/baixas", headers=headers or cen.h_admin, json={
        "valor": valor, "data": str(data or cen.hoje), "conta_id": conta_id or cen.conta.id, "forma": "pix"})
