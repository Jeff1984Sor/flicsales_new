"""Validação de CNPJ/CPF ao salvar empresa/fornecedor e dados da Receita gravados por "Atualizar pela Receita"."""

from app.core.models import Auditoria
from app.modules.nucleo import consultas
from app.modules.nucleo.models import Empresa
from tests.nucleo.test_consultas_socios_anexos import BRASILAPI, CNPJ

CPF = "52998224725"


# ------------------------------------------------------------------------------------------------- documento
def test_empresa_documento_valido_sai_com_mascara(gestor):
    r = gestor.post("/nucleo/empresas", {"nome": "Aurora", "documento": CNPJ})
    assert r.status_code == 201 and r.json()["documento"] == "11.222.333/0001-81"
    r = gestor.patch(f"/nucleo/empresas/{r.json()['id']}", {"documento": CPF})
    assert r.status_code == 200 and r.json()["documento"] == "529.982.247-25"
    r = gestor.patch(f"/nucleo/empresas/{r.json()['id']}", {"documento": ""})
    assert r.status_code == 200 and r.json()["documento"] is None  # vazio limpa


def test_empresa_documento_invalido_e_recusado(gestor):
    r = gestor.post("/nucleo/empresas", {"nome": "Aurora", "documento": "12.345.678/0001-90"})
    assert r.status_code == 400 and r.json()["detail"] == "CNPJ ou CPF inválido."
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    r = gestor.patch(f"/nucleo/empresas/{e['id']}", {"documento": "123.456.789-00"})
    assert r.status_code == 400 and r.json()["detail"] == "CNPJ ou CPF inválido."


def test_dado_antigo_invalido_nao_e_tocado_sem_documento_no_patch(gestor, db):
    db.add(Empresa(nome="Legado", documento="12345", campos_custom={}))
    db.commit()
    e = db.query(Empresa).filter_by(nome="Legado").one()
    r = gestor.patch(f"/nucleo/empresas/{e.id}", {"segmento": "Varejo"})
    assert r.status_code == 200 and r.json()["documento"] == "12345"


def test_documento_duplicado_em_empresa_ativa(gestor, db):
    a = gestor.post("/nucleo/empresas", {"nome": "Aurora", "documento": CNPJ}).json()
    r = gestor.post("/nucleo/empresas", {"nome": "Outra", "documento": "11.222.333/0001-81"})
    assert r.status_code == 400 and f"“Aurora” (#{a['id']})" in r.json()["detail"]
    b = gestor.post("/nucleo/empresas", {"nome": "Outra"}).json()
    assert gestor.patch(f"/nucleo/empresas/{b['id']}", {"documento": CNPJ}).status_code == 400
    assert gestor.patch(f"/nucleo/empresas/{a['id']}", {"documento": CNPJ}).status_code == 200  # a própria
    gestor.delete(f"/nucleo/empresas/{a['id']}")  # inativa: documento fica livre
    assert gestor.patch(f"/nucleo/empresas/{b['id']}", {"documento": CNPJ}).status_code == 200


def test_fornecedor_valida_documento(financeiro, gestor):
    r = financeiro.post("/nucleo/fornecedores", {"nome": "Gráfica", "documento": "11.222.333/0001-00"})
    assert r.status_code == 400 and r.json()["detail"] == "CNPJ ou CPF inválido."
    f = financeiro.post("/nucleo/fornecedores", {"nome": "Gráfica", "documento": CPF})
    assert f.status_code == 201 and f.json()["documento"] == "529.982.247-25"
    gestor.post("/nucleo/empresas", {"nome": "Aurora", "documento": CNPJ})
    r = financeiro.patch(f"/nucleo/fornecedores/{f.json()['id']}", {"documento": CNPJ})
    assert r.status_code == 400 and "Aurora" in r.json()["detail"]


def test_campos_da_receita_nao_sao_editaveis(gestor):
    r = gestor.post("/nucleo/empresas", {"nome": "Aurora", "cnae_principal": "x"})
    assert r.status_code == 422
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    assert gestor.patch(f"/nucleo/empresas/{e['id']}", {"capital_social": "1"}).status_code == 422
    assert e["cnaes_secundarios"] == [] and e["cnae_principal"] is None and e["receita_consultada_em"] is None


# ------------------------------------------------------------------------------------------------- dados da Receita
def test_aplicar_cnpj_grava_dados_da_receita_e_sobrescreve(gestor, financeiro, rede, db):
    rede.rotas["brasilapi"] = (200, BRASILAPI)
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora", "documento": CNPJ, "papeis": ["fornecedor"]}).json()
    d = gestor.post(f"/nucleo/empresas/{e['id']}/cnpj/aplicar").json()
    assert d["cnae_principal"].startswith("7020-4/00") and "consultoria" in d["cnae_principal"].lower()
    assert len(d["cnaes_secundarios"]) == 1 and d["cnaes_secundarios"][0].startswith("6201-5/01")
    assert (d["natureza_juridica"], d["capital_social"], d["situacao_cadastral"], d["data_abertura"]) == (
        "Sociedade Empresária Limitada", "10000.00", "ATIVA", "2010-05-01")
    assert d["receita_consultada_em"]
    alt = db.query(Auditoria).filter_by(acao="empresa.alterar", entidade_id=str(e["id"])).one()
    assert alt.depois_json["capital_social"] == "10000.00" and alt.antes_json["cnae_principal"] is None
    # fornecedor também expõe
    f = financeiro.get(f"/nucleo/fornecedores/{e['id']}").json()
    assert f["situacao_cadastral"] == "ATIVA" and f["capital_social"] == "10000.00"
    # nova consulta sobrescreve (são dados da Receita)
    consultas.limpar_cache()
    rede.rotas["brasilapi"] = (200, {**BRASILAPI, "descricao_situacao_cadastral": "BAIXADA", "capital_social": 20000,
                                     "cnaes_secundarios": []})
    d = gestor.post(f"/nucleo/empresas/{e['id']}/cnpj/aplicar").json()
    assert (d["situacao_cadastral"], d["capital_social"], d["cnaes_secundarios"]) == ("BAIXADA", "20000.00", [])
