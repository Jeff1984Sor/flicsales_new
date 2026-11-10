"""Empresas: cadastro único compartilhado (nome basta, sem duplicar, renomear mantém vínculos, inativar)."""

from datetime import date
from decimal import Decimal

from app.core.models import Auditoria
from app.modules.comercial.models import Funil, Oportunidade
from app.modules.financeiro.models import Titulo
from app.modules.nucleo.models import CampoCustom, Empresa


def _vinculos(db, empresa_id, usuario_id):
    funil = Funil(nome="Serviços B2B")
    db.add(funil)
    db.flush()
    db.add_all([
        Oportunidade(titulo="Projeto", funil_id=funil.id, empresa_id=empresa_id, responsavel_id=usuario_id),
        Oportunidade(titulo="Expansão", funil_id=funil.id, empresa_id=empresa_id, responsavel_id=usuario_id),
        Titulo(direcao="receber", empresa_id=empresa_id, descricao="Parcela 1", vencimento=date(2026, 11, 20),
               valor_original=Decimal("6000"), saldo=Decimal("6000"), responsavel_id=usuario_id, status="aberto"),
        Titulo(direcao="receber", empresa_id=empresa_id, descricao="Cancelado", vencimento=date(2026, 11, 20),
               valor_original=Decimal("100"), saldo=Decimal("100"), responsavel_id=usuario_id, status="cancelado"),
        Titulo(direcao="pagar", empresa_id=empresa_id, descricao="Conta", vencimento=date(2026, 11, 20),
               valor_original=Decimal("50"), saldo=Decimal("50"), responsavel_id=usuario_id, status="aberto"),
    ])
    db.commit()


def test_criar_so_com_nome(gestor, db):
    r = gestor.post("/nucleo/empresas", {"nome": "  Aurora   Consultoria "})
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["nome"] == "Aurora Consultoria"
    assert e["papeis"] == ["prospect"] and e["ativo"] is True
    assert e["responsavel_id"] == gestor.usuario.id and e["contatos"] == []
    assert db.query(Auditoria).filter_by(acao="empresa.criar", entidade_id=str(e["id"])).count() == 1


def test_criar_completa_com_papeis_e_campos(gestor, db):
    db.add(CampoCustom(nome="Origem", slug="origem", tipo="lista", objeto="empresa", opcoes=["Site", "Evento"]))
    db.commit()
    r = gestor.post("/nucleo/empresas", {
        "nome": "Vértice Serviços", "documento": "12.345.678/0001-90", "nome_fantasia": "Vértice", "segmento": "Serviços",
        "porte": "Média", "site": "https://vertice.demo", "email_financeiro": "fin@vertice.demo", "telefone": "11 9999",
        "endereco": "Rua A, 1", "papeis": ["cliente", "fornecedor"], "origem": "Site", "observacoes": "",
        "campos_custom": {"origem": "Site"}})
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["papeis"] == ["cliente", "fornecedor"] and e["campos_custom"] == {"origem": "Site"}
    assert e["observacoes"] is None  # "" vira None


def test_nome_duplicado_pela_forma_normalizada(gestor):
    gestor.post("/nucleo/empresas", {"nome": "Aurora Consultoria"})
    r = gestor.post("/nucleo/empresas", {"nome": "aurora  consultória"})
    assert r.status_code == 400 and r.json()["detail"] == "Já existe empresa com este nome"


def test_validacoes(gestor, db):
    assert gestor.post("/nucleo/empresas", {"nome": "   "}).json()["detail"] == "Informe o nome da empresa."
    assert gestor.post("/nucleo/empresas", {}).status_code == 422
    assert gestor.post("/nucleo/empresas", {"nome": "X", "papeis": ["dono"]}).status_code == 422
    assert gestor.post("/nucleo/empresas", {"nome": "X", "responsavel_id": 999}).json()["detail"] == \
        "Responsável não encontrado."
    r = gestor.post("/nucleo/empresas", {"nome": "X", "campos_custom": {"nao_existe": 1}})
    assert r.status_code == 400 and "desconhecido" in r.json()["detail"]
    db.add(CampoCustom(nome="Setor", slug="setor", tipo="texto", objeto="empresa", obrigatorio=True))
    db.commit()
    assert gestor.post("/nucleo/empresas", {"nome": "Y"}).json()["detail"] == "Preencha o campo obrigatório: Setor."


def test_listar_com_busca_papel_contagens(gestor, db):
    a = gestor.post("/nucleo/empresas", {"nome": "Aurora Consultoria", "papeis": ["cliente"]}).json()
    gestor.post("/nucleo/empresas", {"nome": "Nuvem Digital", "papeis": ["fornecedor"]})
    _vinculos(db, a["id"], gestor.usuario.id)
    itens = gestor.get("/nucleo/empresas").json()
    assert itens["total"] == 2
    aurora = next(i for i in itens["itens"] if i["id"] == a["id"])
    assert aurora["oportunidades"] == 2 and aurora["titulos_receber"] == 1 and Decimal(aurora["saldo_receber"]) == 6000
    assert [i["nome"] for i in gestor.get("/nucleo/empresas", params={"q": "aurora"}).json()["itens"]] == [
        "Aurora Consultoria"]
    assert [i["nome"] for i in gestor.get("/nucleo/empresas", params={"papel": "fornecedor"}).json()["itens"]] == [
        "Nuvem Digital"]
    pag = gestor.get("/nucleo/empresas", params={"por_pagina": 1, "pagina": 2}).json()
    assert pag["total"] == 2 and len(pag["itens"]) == 1


def test_ver_detalhe_com_contatos(gestor):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    gestor.post("/nucleo/pessoas", {"nome": "Paula", "empresa_id": e["id"]})
    r = gestor.get(f"/nucleo/empresas/{e['id']}")
    assert r.status_code == 200 and [c["nome"] for c in r.json()["contatos"]] == ["Paula"]
    assert gestor.get("/nucleo/empresas/999").status_code == 404


def test_renomear_mantem_vinculos_e_audita(gestor, db):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    _vinculos(db, e["id"], gestor.usuario.id)
    r = gestor.patch(f"/nucleo/empresas/{e['id']}", {"nome": "Aurora Consultoria S.A."})
    assert r.status_code == 200, r.text
    assert r.json()["nome"] == "Aurora Consultoria S.A." and r.json()["oportunidades"] == 2
    db.expire_all()
    assert {o.empresa_id for o in db.query(Oportunidade)} == {e["id"]}
    aud = db.query(Auditoria).filter_by(acao="empresa.alterar").one()
    assert aud.descricao == "Aurora → Aurora Consultoria S.A." and aud.depois_json["nome"] == "Aurora Consultoria S.A."


def test_atualizar_so_o_enviado(gestor):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora", "segmento": "Consultoria", "telefone": "1"}).json()
    r = gestor.patch(f"/nucleo/empresas/{e['id']}", {"telefone": "2"}).json()
    assert r["segmento"] == "Consultoria" and r["telefone"] == "2"


def test_renomear_para_nome_de_outra_recusa(gestor):
    gestor.post("/nucleo/empresas", {"nome": "Aurora"})
    b = gestor.post("/nucleo/empresas", {"nome": "Atlas"}).json()
    r = gestor.patch(f"/nucleo/empresas/{b['id']}", {"nome": "AURORA"})
    assert r.status_code == 400 and r.json()["detail"] == "Já existe empresa com este nome"
    # renomear para ela mesma (só caixa) é permitido
    assert gestor.patch(f"/nucleo/empresas/{b['id']}", {"nome": "ATLAS"}).status_code == 200
    assert gestor.patch("/nucleo/empresas/999", {"nome": "Z"}).status_code == 404


def test_inativar(gestor, db):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    r = gestor.delete(f"/nucleo/empresas/{e['id']}")
    assert r.status_code == 200 and r.json()["ativo"] is False
    assert db.get(Empresa, e["id"]) is not None  # nada é apagado
    assert gestor.get("/nucleo/empresas").json()["total"] == 0
    assert gestor.get("/nucleo/empresas", params={"situacao": "inativos"}).json()["total"] == 1
    assert db.query(Auditoria).filter_by(acao="empresa.inativar").count() == 1
    assert gestor.delete("/nucleo/empresas/999").status_code == 404
    # reativar pelo PATCH
    assert gestor.patch(f"/nucleo/empresas/{e['id']}", {"ativo": True}).json()["ativo"] is True


def test_permissoes(gestor, comercial, financeiro, leitura):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    assert leitura.get("/nucleo/empresas").status_code == 200
    assert leitura.get(f"/nucleo/empresas/{e['id']}").status_code == 200
    assert leitura.post("/nucleo/empresas", {"nome": "B"}).status_code == 403
    assert leitura.patch(f"/nucleo/empresas/{e['id']}", {"nome": "B"}).status_code == 403
    assert leitura.delete(f"/nucleo/empresas/{e['id']}").status_code == 403
    # Comercial e Financeiro criam empresa (ela nasce dentro da oportunidade / do título)
    assert comercial.post("/nucleo/empresas", {"nome": "C"}).status_code == 201
    assert financeiro.post("/nucleo/empresas", {"nome": "F"}).status_code == 201
