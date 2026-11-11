"""Fornecedores · Categorias · Centros de custo · Contas financeiras (permissão financeiro.cadastros)."""

from datetime import date
from decimal import Decimal

from app.core.models import Auditoria
from app.modules.financeiro.models import Baixa, Titulo, Transferencia
from app.modules.nucleo.models import Empresa, Pessoa


# ------------------------------------------------------------------------------------------------- fornecedores
def test_fornecedor_criar_e_editar(financeiro, db):
    cat = financeiro.post("/nucleo/categorias", {"nome": "Estrutura", "natureza": "despesa"}).json()
    r = financeiro.post("/nucleo/fornecedores", {
        "nome": "Espaço Compartilhado", "documento": "44.775.566/0001-60", "contato": "Joana", "email": "a@b.demo",
        "telefone": "11 3333", "categoria_padrao_id": cat["id"], "condicao_habitual": "Boleto todo dia 5"})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["papeis"] == ["fornecedor"] and f["contato"] == "Joana" and f["categoria_padrao_nome"] == "Estrutura"
    e = db.get(Empresa, f["id"])
    assert e.papel_fornecedor and e.email_financeiro == "a@b.demo"  # é a MESMA empresa (cadastro único)
    assert db.query(Pessoa).filter_by(empresa_id=e.id, nome="Joana").count() == 1
    r = financeiro.patch(f"/nucleo/fornecedores/{f['id']}", {"condicao_habitual": "Pix", "contato": "Joana"})
    assert r.json()["condicao_habitual"] == "Pix"
    assert db.query(Pessoa).filter_by(empresa_id=e.id).count() == 1  # não duplica o contato
    assert financeiro.get("/nucleo/fornecedores").json()["total"] == 1
    assert financeiro.get(f"/nucleo/fornecedores/{f['id']}").status_code == 200
    assert financeiro.delete(f"/nucleo/fornecedores/{f['id']}").json()["ativo"] is False


def test_fornecedor_a_partir_de_empresa_existente(gestor, db):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora", "papeis": ["cliente"]}).json()
    r = gestor.post("/nucleo/fornecedores", {"empresa_id": e["id"], "condicao_habitual": "30 dias"})
    assert r.status_code == 201 and r.json()["papeis"] == ["cliente", "fornecedor"]
    assert db.query(Empresa).count() == 1


def test_fornecedor_validacoes(gestor):
    gestor.post("/nucleo/empresas", {"nome": "Aurora"})
    assert gestor.post("/nucleo/fornecedores", {"nome": "aurora"}).json()["detail"] == "Já existe empresa com este nome"
    assert gestor.post("/nucleo/fornecedores", {}).json()["detail"] == "Informe o nome do fornecedor."
    rec = gestor.post("/nucleo/categorias", {"nome": "Vendas", "natureza": "receita"}).json()
    assert gestor.post("/nucleo/fornecedores", {"nome": "N", "categoria_padrao_id": rec["id"]}).json()["detail"] == \
        "A categoria padrão do fornecedor deve ser de despesa."
    # empresa que não é fornecedor não abre pela rota de fornecedores
    cliente = gestor.post("/nucleo/empresas", {"nome": "Cliente"}).json()
    assert gestor.get(f"/nucleo/fornecedores/{cliente['id']}").status_code == 404
    assert gestor.patch("/nucleo/fornecedores/999", {"nome": "x"}).status_code == 404


def test_fornecedor_permissoes(comercial, leitura, financeiro):
    assert comercial.get("/nucleo/fornecedores").status_code == 403  # Comercial não tem cadastros financeiros
    assert leitura.get("/nucleo/fornecedores").status_code == 200
    assert leitura.post("/nucleo/fornecedores", {"nome": "X"}).status_code == 403
    assert financeiro.post("/nucleo/fornecedores", {"nome": "X"}).status_code == 201


# ------------------------------------------------------------------------------------------------- categorias
def test_categorias(financeiro, db):
    r = financeiro.post("/nucleo/categorias", {"nome": "Estrutura", "natureza": "despesa"})
    assert r.status_code == 201
    sup = r.json()
    sub = financeiro.post("/nucleo/categorias", {"nome": "Aluguel", "natureza": "despesa",
                                                 "superior_id": sup["id"]}).json()
    assert sub["superior_nome"] == "Estrutura"
    assert financeiro.post("/nucleo/categorias", {"nome": "estrutura", "natureza": "despesa"}).json()["detail"] == \
        "Já existe categoria com este nome neste nível."
    assert financeiro.post("/nucleo/categorias", {"nome": "Estrutura", "natureza": "receita"}).status_code == 201
    assert financeiro.post("/nucleo/categorias", {"nome": "X", "natureza": "receita", "superior_id": sup["id"]}) \
        .json()["detail"] == "A categoria superior precisa ter a mesma natureza."
    assert financeiro.patch(f"/nucleo/categorias/{sup['id']}", {"superior_id": sub["id"]}).json()["detail"] == \
        "Uma categoria não pode ficar abaixo dela mesma."
    assert financeiro.patch(f"/nucleo/categorias/{sup['id']}", {"natureza": "receita"}).json()["detail"] == \
        "Categoria com subcategorias: altere a natureza delas antes."
    assert financeiro.post("/nucleo/categorias", {"nome": "X", "natureza": "lucro"}).status_code == 422
    r = financeiro.patch(f"/nucleo/categorias/{sub['id']}", {"nome": "Aluguel e condomínio"})
    assert r.json()["nome"] == "Aluguel e condomínio"
    assert len(financeiro.get("/nucleo/categorias", params={"natureza": "despesa"}).json()) == 2
    assert financeiro.delete(f"/nucleo/categorias/{sub['id']}").json()["ativo"] is False
    assert financeiro.get("/nucleo/categorias/999").status_code == 404
    assert db.query(Auditoria).filter_by(entidade="categoria").count() == 5


def test_categorias_permissao(leitura, comercial):
    assert leitura.get("/nucleo/categorias").status_code == 200
    assert leitura.post("/nucleo/categorias", {"nome": "X", "natureza": "receita"}).status_code == 403
    assert comercial.post("/nucleo/categorias", {"nome": "X", "natureza": "receita"}).status_code == 403


# ------------------------------------------------------------------------------------------------- centros de custo
def test_centros(financeiro, leitura):
    r = financeiro.post("/nucleo/centros-custo", {"nome": "Operação", "codigo": " op ",
                                                  "responsavel_id": financeiro.usuario.id})
    assert r.status_code == 201 and r.json()["codigo"] == "OP" and r.json()["responsavel_nome"]
    c = r.json()
    assert financeiro.post("/nucleo/centros-custo", {"nome": "Outra", "codigo": "Op"}).json()["detail"] == \
        "Já existe centro de custo com este código."
    assert financeiro.post("/nucleo/centros-custo", {"nome": "Outra", "codigo": " "}).json()["detail"] == \
        "Informe o código do centro de custo."
    assert financeiro.patch(f"/nucleo/centros-custo/{c['id']}", {"nome": "Operações"}).json()["nome"] == "Operações"
    assert len(financeiro.get("/nucleo/centros-custo").json()) == 1
    assert financeiro.delete(f"/nucleo/centros-custo/{c['id']}").json()["ativo"] is False
    assert financeiro.get("/nucleo/centros-custo/99").status_code == 404
    assert leitura.post("/nucleo/centros-custo", {"nome": "X", "codigo": "X"}).status_code == 403


# ------------------------------------------------------------------------------------------------- contas financeiras
def test_conta_saldo_negativo_e_edicao_sem_movimento(financeiro):
    r = financeiro.post("/nucleo/contas", {"nome": "Conta operacional", "instituicao": "Banco",
                                           "saldo_inicial": "-1500.00", "data_base": "2026-10-01"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["saldo_inicial"] == "-1500.00" and c["tem_movimento"] is False
    r = financeiro.patch(f"/nucleo/contas/{c['id']}", {"saldo_inicial": "25000", "data_base": "2026-09-01"})
    assert r.status_code == 200 and r.json()["saldo_inicial"] == "25000.00"
    assert financeiro.post("/nucleo/contas", {"nome": "conta operacional", "saldo_inicial": "0",
                                              "data_base": "2026-10-01"}).json()["detail"] == \
        "Já existe conta com este nome."
    assert financeiro.post("/nucleo/contas", {"nome": "X"}).status_code == 422


def test_conta_com_movimento_preserva_saldo_e_data_base(financeiro, db):
    c1 = financeiro.post("/nucleo/contas", {"nome": "A", "saldo_inicial": "100", "data_base": "2026-10-01"}).json()
    c2 = financeiro.post("/nucleo/contas", {"nome": "B", "saldo_inicial": "0", "data_base": "2026-10-01"}).json()
    db.add(Transferencia(conta_origem_id=c1["id"], conta_destino_id=c2["id"], valor=Decimal("10"),
                         data=date(2026, 10, 5)))
    db.commit()
    for cid in (c1["id"], c2["id"]):
        r = financeiro.patch(f"/nucleo/contas/{cid}", {"saldo_inicial": "999"})
        assert r.status_code == 400 and r.json()["detail"] == "Conta com movimentos: preserve saldo inicial e data-base."
        assert financeiro.patch(f"/nucleo/contas/{cid}", {"data_base": "2026-01-01"}).status_code == 400
    # nome e instituição continuam editáveis; mandar o mesmo saldo não conta como mudança
    r = financeiro.patch(f"/nucleo/contas/{c1['id']}", {"nome": "A2", "saldo_inicial": "100.00"})
    assert r.status_code == 200 and r.json()["tem_movimento"] is True


def test_conta_com_baixa(financeiro, db):
    c = financeiro.post("/nucleo/contas", {"nome": "A", "saldo_inicial": "0", "data_base": "2026-10-01"}).json()
    e = Empresa(nome="Cliente")
    db.add(e)
    db.flush()
    t = Titulo(direcao="receber", empresa_id=e.id, descricao="x", vencimento=date(2026, 11, 1),
               valor_original=Decimal("10"), saldo=Decimal("5"), responsavel_id=financeiro.usuario.id, status="parcial")
    db.add(t)
    db.flush()
    b = Baixa(titulo_id=t.id, valor=Decimal("5"), data=date(2026, 10, 2), conta_id=c["id"], forma="pix")
    db.add(b)
    db.commit()
    assert financeiro.patch(f"/nucleo/contas/{c['id']}", {"saldo_inicial": "1"}).status_code == 400
    b.estornada = True  # baixa estornada não conta como movimento (o saldo não é afetado por ela)
    db.commit()
    assert financeiro.patch(f"/nucleo/contas/{c['id']}", {"saldo_inicial": "1"}).status_code == 200


def test_conta_404_403(financeiro, leitura, comercial):
    assert financeiro.get("/nucleo/contas/9").status_code == 404
    assert financeiro.delete("/nucleo/contas/9").status_code == 404
    assert leitura.get("/nucleo/contas").status_code == 200
    assert leitura.post("/nucleo/contas", {"nome": "X", "saldo_inicial": "0", "data_base": "2026-01-01"}) \
        .status_code == 403
    assert comercial.get("/nucleo/contas").status_code == 403
    c = financeiro.post("/nucleo/contas", {"nome": "A", "saldo_inicial": "0", "data_base": "2026-10-01"}).json()
    assert financeiro.delete(f"/nucleo/contas/{c['id']}").json()["ativo"] is False
