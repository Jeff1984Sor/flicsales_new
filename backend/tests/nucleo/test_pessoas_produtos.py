"""Pessoas e contatos · Produtos e serviços."""

from app.core.models import Auditoria
from app.modules.nucleo.models import CampoCustom


# ------------------------------------------------------------------------------------------------- pessoas
def test_pessoa_crud(gestor, db):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    r = gestor.post("/nucleo/pessoas", {"nome": "Paula Mendes", "empresa_id": e["id"], "cargo": "Diretora (decisora)",
                                        "email": "paula@aurora.demo", "telefone": "", "canal_preferido": "email"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["empresa_nome"] == "Aurora" and p["telefone"] is None and p["responsavel_nome"]
    assert gestor.get(f"/nucleo/pessoas/{p['id']}").json()["nome"] == "Paula Mendes"
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"cargo": "CEO"})
    assert r.status_code == 200 and r.json()["cargo"] == "CEO" and r.json()["email"] == "paula@aurora.demo"
    lista = gestor.get("/nucleo/pessoas", params={"q": "paula"}).json()
    assert lista["total"] == 1
    assert gestor.get("/nucleo/pessoas", params={"empresa_id": e["id"]}).json()["total"] == 1
    assert gestor.get("/nucleo/pessoas", params={"q": "aurora"}).json()["total"] == 1  # busca pela empresa
    r = gestor.delete(f"/nucleo/pessoas/{p['id']}")
    assert r.json()["ativo"] is False
    acoes = {a.acao for a in db.query(Auditoria).filter_by(entidade="pessoa")}
    assert acoes == {"pessoa.criar", "pessoa.alterar", "pessoa.inativar"}


def test_pessoa_validacoes(gestor, db):
    assert gestor.post("/nucleo/pessoas", {"nome": " "}).json()["detail"] == "Informe o nome da pessoa."
    assert gestor.post("/nucleo/pessoas", {"nome": "A", "empresa_id": 99}).json()["detail"] == "Empresa não encontrada."
    assert gestor.post("/nucleo/pessoas", {"nome": "A", "email": "sem-arroba"}).json()["detail"] == \
        "Informe um e-mail válido."
    assert gestor.post("/nucleo/pessoas", {"nome": "A", "canal_preferido": "fax"}).status_code == 422
    db.add(CampoCustom(nome="Aniversário", slug="aniversario", tipo="data", objeto="pessoa"))
    db.commit()
    r = gestor.post("/nucleo/pessoas", {"nome": "A", "campos_custom": {"aniversario": "31/12"}})
    assert r.status_code == 400 and "AAAA-MM-DD" in r.json()["detail"]
    r = gestor.post("/nucleo/pessoas", {"nome": "A", "campos_custom": {"aniversario": "2000-12-31"}})
    assert r.json()["campos_custom"] == {"aniversario": "2000-12-31"}


def test_pessoa_404_e_403(gestor, leitura):
    assert gestor.get("/nucleo/pessoas/9").status_code == 404
    assert gestor.patch("/nucleo/pessoas/9", {"nome": "x"}).status_code == 404
    assert gestor.delete("/nucleo/pessoas/9").status_code == 404
    assert leitura.get("/nucleo/pessoas").status_code == 200
    assert leitura.post("/nucleo/pessoas", {"nome": "A"}).status_code == 403


# ------------------------------------------------------------------------------------------------- produtos
def test_produto_crud(gestor, db):
    r = gestor.post("/nucleo/produtos", {"nome": "Consultoria estratégica", "tipo": "servico", "codigo": "CONS",
                                         "unidade": "projeto", "preco_referencia": "24000.00", "recorrente": False})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["preco_referencia"] == "24000.00" and p["ativo"] is True
    r = gestor.patch(f"/nucleo/produtos/{p['id']}", {"preco_referencia": "25000", "recorrente": True})
    assert r.json()["preco_referencia"] == "25000.00" and r.json()["recorrente"] is True
    assert gestor.get("/nucleo/produtos", params={"q": "cons"}).json()["total"] == 1
    assert gestor.get("/nucleo/produtos", params={"tipo": "produto"}).json()["total"] == 0
    assert gestor.delete(f"/nucleo/produtos/{p['id']}").json()["ativo"] is False
    assert db.query(Auditoria).filter_by(entidade="produto").count() == 3


def test_produto_validacoes(gestor):
    gestor.post("/nucleo/produtos", {"nome": "Consultoria", "tipo": "servico", "codigo": "C1"})
    assert gestor.post("/nucleo/produtos", {"nome": "consultoria", "tipo": "servico"}).json()["detail"] == \
        "Já existe produto ou serviço com este nome."
    assert gestor.post("/nucleo/produtos", {"nome": "Outro", "tipo": "servico", "codigo": "C1"}).json()["detail"] == \
        "Já existe produto ou serviço com este código."
    assert gestor.post("/nucleo/produtos", {"nome": "X", "tipo": "pacote"}).status_code == 422
    assert gestor.post("/nucleo/produtos", {"nome": "X", "tipo": "servico", "preco_referencia": "-1"}).status_code == 422


def test_produto_404_e_403(gestor, leitura, financeiro):
    assert gestor.get("/nucleo/produtos/9").status_code == 404
    assert gestor.patch("/nucleo/produtos/9", {"nome": "x"}).status_code == 404
    assert leitura.get("/nucleo/produtos").status_code == 200
    assert leitura.post("/nucleo/produtos", {"nome": "A", "tipo": "servico"}).status_code == 403
    assert financeiro.get("/nucleo/produtos").status_code == 200
