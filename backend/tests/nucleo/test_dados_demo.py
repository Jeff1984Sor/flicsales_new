"""As telas do Núcleo com os dados de demonstração (seed): todas as listas respondem e os números batem."""

from datetime import date
from decimal import Decimal

from app import seed
from tests.conftest import entrar
from tests.nucleo.conftest import Api


def test_listas_com_dados_demo(client, db):
    seed.semear(db, date(2026, 11, 10))
    api = Api(client, entrar(client, "francine", seed.SENHA_DEMO).json()["access_token"], None)

    empresas = api.get("/nucleo/empresas").json()
    por_nome = {e["nome"]: e for e in empresas["itens"]}
    assert por_nome["Aurora Consultoria"]["oportunidades"] == 1
    assert por_nome["Ponto Norte"]["titulos_receber"] >= 1 and Decimal(por_nome["Ponto Norte"]["saldo_receber"]) > 0
    assert {e["nome"] for e in api.get("/nucleo/fornecedores").json()["itens"]} == {"Espaço Compartilhado",
                                                                                    "Nuvem Digital"}
    assert api.get("/nucleo/pessoas").json()["total"] == 4
    assert api.get("/nucleo/produtos").json()["itens"][0]["nome"] == "Consultoria estratégica"
    assert {c["nome"] for c in api.get("/nucleo/categorias").json()} == {"Serviços prestados", "Estrutura"}
    assert api.get("/nucleo/centros-custo").json()[0]["codigo"] == "OP"
    assert api.get("/nucleo/contas").json()[0]["saldo_inicial"] == "25000.00"
    campos = {c["slug"]: c for c in api.get("/nucleo/campos").json()}
    assert campos["interesse"]["registros_preenchidos"] == 4 and campos["origem"]["objeto"] == "empresa"
    assert api.get(f"/nucleo/campos/{campos['interesse']['id']}/dependencias").status_code == 200
    grupos = {g["tipo"] for g in api.get("/nucleo/busca", params={"q": "aurora"}).json()["grupos"]}
    assert {"empresas", "pessoas", "oportunidades"} <= grupos
    assert api.get("/nucleo/duplicidades").json() == []
    aurora = por_nome["Aurora Consultoria"]["id"]
    detalhe = api.get(f"/nucleo/empresas/{aurora}").json()
    assert [c["nome"] for c in detalhe["contatos"]] == ["Paula Mendes"]
    # editar a empresa reenviando os campos personalizados que já tem não dá erro
    r = api.patch(f"/nucleo/empresas/{aurora}", {"campos_custom": detalhe["campos_custom"], "telefone": "11 4000"})
    assert r.status_code == 200, r.text
