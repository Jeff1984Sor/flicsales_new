"""Consultas públicas (CNPJ/CEP) com provedores falsos, aplicar CNPJ (sócios + comprovante PDF) e anexos da empresa."""

import httpx
import pytest

from app.core.models import Auditoria
from app.domain import RegraViolada
from app.modules.nucleo import consultas
from app.modules.nucleo.models import EmpresaAnexo, EmpresaSocio, Pessoa

CNPJ = "11222333000181"

BRASILAPI = {
    "cnpj": CNPJ, "razao_social": "AURORA CONSULTORIA LTDA", "nome_fantasia": "AURORA",
    "cnae_fiscal": 7020400, "cnae_fiscal_descricao": "Atividades de consultoria em gestão empresarial",
    "cnaes_secundarios": [{"codigo": 6201501, "descricao": "Desenvolvimento de programas de computador sob encomenda"},
                          {"codigo": 0, "descricao": ""}],
    "porte": "EMPRESA DE PEQUENO PORTE", "descricao_situacao_cadastral": "ATIVA", "data_inicio_atividade": "2010-05-01",
    "ddd_telefone_1": "1133334444", "email": "Financeiro@Aurora.com.br", "cep": "01310100",
    "descricao_tipo_de_logradouro": "AVENIDA", "logradouro": "PAULISTA", "numero": "1000", "complemento": "CONJ 12",
    "bairro": "BELA VISTA", "municipio": "SAO PAULO", "uf": "SP",
    "natureza_juridica": "Sociedade Empresária Limitada", "capital_social": 10000,
    "qsa": [{"nome_socio": "PAULA MENDES", "qualificacao_socio": "Sócio-Administrador",
             "cnpj_cpf_do_socio": "***982247**", "data_entrada_sociedade": "2010-05-01", "faixa_etaria": "Entre 41 a 50 anos"}],
}

CNPJA = {
    "taxId": CNPJ, "alias": "Aurora", "founded": "2010-05-01", "status": {"text": "Ativa"},
    "company": {"name": "AURORA CONSULTORIA LTDA", "size": {"acronym": "ME"}, "nature": {"text": "Sociedade Limitada"},
                "equity": 5000.5, "members": [{"since": "2011-01-02", "person": {"name": "Rafael", "taxId": "***1**",
                                                                                   "age": "31-40"},
                                               "role": {"text": "Sócio"}}]},
    "address": {"street": "Rua A", "number": "1", "details": None, "district": "Centro", "city": "Recife",
                "state": "PE", "zip": "50010000"},
    "phones": [{"area": "81", "number": "999998888"}], "emails": [{"address": "x@aurora.com"}],
    "mainActivity": {"id": 7020400, "text": "Consultoria"}, "sideActivities": [],
}


# ------------------------------------------------------------------------------------------------- CNPJ
def test_consulta_cnpj_brasilapi(gestor, rede):
    rede.rotas["brasilapi.com.br/api/cnpj/v1/" + CNPJ] = (200, BRASILAPI)
    r = gestor.get("/nucleo/consultas/cnpj/11.222.333.0001-81")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["documento"] == "11.222.333/0001-81" and d["nome"] == "AURORA CONSULTORIA LTDA"
    assert (d["porte"], d["situacao"], d["abertura"]) == ("EPP", "ATIVA", "2010-05-01")
    assert (d["telefone"], d["email_financeiro"]) == ("(11) 3333-4444", "financeiro@aurora.com.br")
    assert (d["cep"], d["logradouro"], d["cidade"], d["uf"]) == ("01310-100", "Avenida Paulista", "Sao Paulo", "SP")
    assert d["cnae_principal"] == "7020-4/00 · Atividades de consultoria em gestão empresarial"
    assert d["cnaes_secundarios"] == ["6201-5/01 · Desenvolvimento de programas de computador sob encomenda"]
    assert d["capital_social"] == "10000.00" and d["natureza_juridica"] == "Sociedade Empresária Limitada"
    assert d["socios"][0]["nome"] == "PAULA MENDES" and d["socios"][0]["documento"] == "***982247**"
    assert d["fonte"] == "BrasilAPI (Receita Federal)" and d["empresa_existente"] is None
    # cache de 24 h: a segunda consulta não chama o provedor
    gestor.get(f"/nucleo/consultas/cnpj/{CNPJ}")
    assert len(rede.chamadas) == 1


def test_consulta_cnpj_avisa_empresa_existente(gestor, rede):
    rede.rotas["brasilapi"] = (200, BRASILAPI)
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora", "documento": "11.222.333/0001-81"}).json()
    assert gestor.get(f"/nucleo/consultas/cnpj/{CNPJ}").json()["empresa_existente"] == {"id": e["id"], "nome": "Aurora"}


def test_consulta_cnpj_fallback_cnpja(gestor, rede):
    rede.rotas["brasilapi"] = (503, {})
    rede.rotas["open.cnpja.com/office/" + CNPJ] = (200, CNPJA)
    d = gestor.get(f"/nucleo/consultas/cnpj/{CNPJ}").json()
    assert d["fonte"] == "CNPJá (Receita Federal)" and d["porte"] == "ME" and d["situacao"] == "ATIVA"
    assert (d["telefone"], d["cep"], d["uf"]) == ("(81) 99999-8888", "50010-000", "PE")
    assert d["socios"] == [{"nome": "Rafael", "qualificacao": "Sócio", "documento": "***1**",
                            "data_entrada": "2011-01-02", "faixa_etaria": "31-40"}]
    assert d["capital_social"] == "5000.50"


def test_consulta_cnpj_invalido_404_502(gestor, rede):
    r = gestor.get("/nucleo/consultas/cnpj/12345678000190")
    assert r.status_code == 400 and r.json()["detail"] == "CNPJ inválido."
    assert rede.chamadas == []
    rede.rotas["brasilapi"] = (404, {"message": "não encontrado"})
    rede.rotas["cnpja"] = (404, {})
    r = gestor.get(f"/nucleo/consultas/cnpj/{CNPJ}")
    assert r.status_code == 404 and "não encontrado" in r.json()["detail"]
    consultas.limpar_cache()
    rede.rotas.clear()
    rede.rotas["brasilapi"] = httpx.ReadTimeout("lento")
    r = gestor.get(f"/nucleo/consultas/cnpj/{CNPJ}")
    assert r.status_code == 502 and "fora do ar" in r.json()["detail"]


def test_consultar_cnpj_funcao_estavel(rede):
    with pytest.raises(RegraViolada):
        consultas.consultar_cnpj("1")
    rede.rotas["cnpja"] = (404, {})
    rede.rotas["brasilapi"] = (404, {})
    with pytest.raises(LookupError):
        consultas.consultar_cnpj(CNPJ)
    rede.rotas["brasilapi"] = (500, {})
    rede.rotas["cnpja"] = (500, {})
    with pytest.raises(consultas.ConsultaIndisponivel):
        consultas.consultar_cnpj(CNPJ)


# ------------------------------------------------------------------------------------------------- CEP
def test_consulta_cep_viacep_e_fallback(gestor, rede):
    rede.rotas["viacep.com.br/ws/01310100"] = (200, {"cep": "01310-100", "logradouro": "Avenida Paulista",
                                                     "bairro": "Bela Vista", "localidade": "São Paulo", "uf": "SP"})
    d = gestor.get("/nucleo/consultas/cep/01310-100").json()
    assert d == {"cep": "01310-100", "logradouro": "Avenida Paulista", "bairro": "Bela Vista", "cidade": "São Paulo",
                 "uf": "SP", "fonte": "ViaCEP"}
    rede.rotas["viacep"] = httpx.ConnectError("fora")
    rede.rotas["brasilapi.com.br/api/cep/v2/20040020"] = (200, {"street": "Avenida Rio Branco", "neighborhood": "Centro",
                                                                "city": "Rio de Janeiro", "state": "RJ"})
    d = gestor.get("/nucleo/consultas/cep/20040020").json()
    assert d["cidade"] == "Rio de Janeiro" and d["fonte"] == "BrasilAPI (Correios)"


def test_consulta_cep_invalido_inexistente(gestor, rede):
    assert gestor.get("/nucleo/consultas/cep/123").json()["detail"] == "CEP inválido: informe os 8 dígitos."
    rede.rotas["viacep"] = (200, {"erro": True})
    rede.rotas["brasilapi"] = (404, {})
    assert gestor.get("/nucleo/consultas/cep/99999999").status_code == 404
    rede.rotas.clear()
    assert gestor.get("/nucleo/consultas/cep/99999998").status_code == 502


def test_consultas_permissao(sem_acesso, financeiro, rede):
    assert sem_acesso.get(f"/nucleo/consultas/cnpj/{CNPJ}").status_code == 403
    assert sem_acesso.get("/nucleo/consultas/cep/01310100").status_code == 403
    rede.rotas["viacep"] = (200, {"localidade": "X", "uf": "SP"})
    assert financeiro.get("/nucleo/consultas/cep/01310100").status_code == 200


# ------------------------------------------------------------------------------------------------- aplicar CNPJ
def test_aplicar_cnpj_preenche_vazios_socios_e_comprovante(gestor, rede, db):
    rede.rotas["brasilapi"] = (200, BRASILAPI)
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora", "documento": CNPJ, "segmento": "Consultoria"}).json()
    p = gestor.post("/nucleo/pessoas", {"nome": "Paula", "empresa_id": e["id"]}).json()
    db.add(EmpresaSocio(empresa_id=e["id"], nome="Sócio antigo"))
    db.commit()
    r = gestor.post(f"/nucleo/empresas/{e['id']}/cnpj/aplicar")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["segmento"] == "Consultoria"  # já preenchido: não muda
    assert d["nome"] == "Aurora" and d["documento"] == "11.222.333/0001-81"
    assert (d["nome_fantasia"], d["porte"], d["cep"], d["uf"]) == ("AURORA", "EPP", "01310-100", "SP")
    socios = gestor.get(f"/nucleo/empresas/{e['id']}/socios").json()
    assert [s["nome"] for s in socios] == ["PAULA MENDES"] and socios[0]["data_entrada"] == "2010-05-01"
    assert gestor.get(f"/nucleo/pessoas/{p['id']}").json()["cep"] == "01310-100"  # propagou
    anexos = gestor.get(f"/nucleo/empresas/{e['id']}/anexos").json()
    assert len(anexos) == 1 and anexos[0]["tipo"] == "cartao_cnpj" and anexos[0]["mime"] == "application/pdf"
    assert anexos[0]["nome"].startswith("Comprovante CNPJ ") and anexos[0]["enviado_por_nome"]
    pdf = gestor.get(anexos[0]["url"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    acoes = {a.acao for a in db.query(Auditoria).filter_by(entidade="empresa", entidade_id=str(e["id"]))}
    assert {"empresa.alterar", "empresa.socios", "empresa_anexo.criar"} <= acoes
    soc = db.query(Auditoria).filter_by(acao="empresa.socios").one()
    assert soc.antes_json["socios"][0]["nome"] == "Sócio antigo"


def test_aplicar_cnpj_validacoes(gestor, comercial, leitura, rede):
    e = gestor.post("/nucleo/empresas", {"nome": "Sem CNPJ"}).json()
    r = gestor.post(f"/nucleo/empresas/{e['id']}/cnpj/aplicar")
    assert r.status_code == 400 and "CNPJ válido" in r.json()["detail"]
    assert gestor.post("/nucleo/empresas/999/cnpj/aplicar").status_code == 404
    assert leitura.post(f"/nucleo/empresas/{e['id']}/cnpj/aplicar").status_code == 403
    com = gestor.post("/nucleo/empresas", {"nome": "Com CNPJ", "documento": CNPJ}).json()
    rede.rotas["brasilapi"] = (500, {})
    assert comercial.post(f"/nucleo/empresas/{com['id']}/cnpj/aplicar").status_code == 502


# ------------------------------------------------------------------------------------------------- anexos
PDF = b"%PDF-1.4\n%teste\n"


def test_anexo_enviar_baixar_arquivar(gestor, db):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    r = gestor.post(f"/nucleo/empresas/{e['id']}/anexos", files={"arquivo": ("contrato.pdf", PDF, "application/pdf")},
                    data={"tipo": "contrato"})
    assert r.status_code == 201, r.text
    a = r.json()
    assert (a["nome"], a["tipo"], a["tamanho"], a["ativo"]) == ("contrato.pdf", "contrato", len(PDF), True)
    baixado = gestor.get(a["url"])
    assert baixado.content == PDF and "attachment" in baixado.headers["content-disposition"]
    assert gestor.delete(f"/nucleo/empresas/{e['id']}/anexos/{a['id']}").json()["ativo"] is False
    assert gestor.get(f"/nucleo/empresas/{e['id']}/anexos").json() == []
    assert len(gestor.get(f"/nucleo/empresas/{e['id']}/anexos", params={"arquivados": True}).json()) == 1
    assert db.query(EmpresaAnexo).count() == 1  # nada apagado
    assert db.query(Auditoria).filter_by(acao="empresa_anexo.arquivar").count() == 1


def test_anexo_validacoes_404_403(gestor, leitura, sem_acesso):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora"}).json()
    url = f"/nucleo/empresas/{e['id']}/anexos"
    r = gestor.post(url, files={"arquivo": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400 and "Tipo de arquivo não permitido" in r.json()["detail"]
    r = gestor.post(url, files={"arquivo": ("falso.pdf", b"nao sou pdf", "application/pdf")})
    assert r.status_code == 400
    assert gestor.post(url, files={"arquivo": ("a.pdf", PDF)}, data={"tipo": "foto"}).status_code == 422
    assert gestor.post("/nucleo/empresas/999/anexos", files={"arquivo": ("a.pdf", PDF)}).status_code == 404
    assert gestor.get(f"{url}/999/arquivo").status_code == 404
    assert gestor.delete(f"{url}/999").status_code == 404
    assert leitura.post(url, files={"arquivo": ("a.pdf", PDF)}).status_code == 403
    a = gestor.post(url, files={"arquivo": ("a.pdf", PDF)}).json()
    assert leitura.get(a["url"]).status_code == 200
    assert sem_acesso.get(a["url"]).status_code == 403
    assert sem_acesso.get(f"/nucleo/empresas/{e['id']}/socios").status_code == 403
    assert gestor.get("/nucleo/empresas/999/socios").status_code == 404


def test_seed_pessoas_usam_endereco(db):
    from datetime import date

    from app import seed

    seed.semear(db, date(2026, 11, 10))
    paula = db.query(Pessoa).filter_by(nome="Paula Mendes").one()
    assert paula.usa_endereco_da_empresa and paula.cidade
