"""Ajustes do Núcleo (contrato 11/2026): empresa nova pelo CNPJ (B.1), origem livre (B.2), LGPD da pessoa (C),
campos "multipla"/"link" e funil da etapa exigida (D)."""

from app.core.models import Auditoria
from app.modules.comercial.models import Etapa, Funil, Oportunidade
from app.modules.nucleo.models import Pessoa
from tests.nucleo.test_consultas_socios_anexos import BRASILAPI, CNPJ
from tests.nucleo.test_planilhas import _csv, _importar


# ------------------------------------------------------------------------------------------------- B.1 / B.2
def test_empresa_nova_pelo_cnpj_consulta_salva_e_aplica(gestor, rede, db):
    """Fluxo da tela: consulta o CNPJ ao digitar → salva com o que veio → aplica (sócios, Receita, comprovante)."""
    rede.rotas["brasilapi"] = (200, BRASILAPI)
    c = gestor.get(f"/nucleo/consultas/cnpj/{CNPJ}").json()
    corpo = {k: c[k] for k in ("documento", "nome_fantasia", "segmento", "porte", "telefone", "email_financeiro",
                               "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")}
    r = gestor.post("/nucleo/empresas", {"nome": c["nome"], **corpo, "origem": "Prospecção ativa"})
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["documento"] == "11.222.333/0001-81" and e["porte"] == "EPP" and e["cep"] == "01310-100"
    d = gestor.post(f"/nucleo/empresas/{e['id']}/cnpj/aplicar")
    assert d.status_code == 200, d.text
    d = d.json()
    assert d["cnae_principal"].startswith("7020-4/00") and d["situacao_cadastral"] == "ATIVA"
    assert d["capital_social"] == "10000.00" and d["data_abertura"] == "2010-05-01"
    assert [s["nome"] for s in gestor.get(f"/nucleo/empresas/{e['id']}/socios").json()] == ["PAULA MENDES"]
    anexos = gestor.get(f"/nucleo/empresas/{e['id']}/anexos").json()
    assert [a["tipo"] for a in anexos] == ["cartao_cnpj"]
    assert gestor.get(anexos[0]["url"]).content.startswith(b"%PDF-")


def test_origem_aceita_qualquer_texto(gestor):
    for origem in ("Site / formulário", "Feira do setor 2019 (planilha antiga)"):
        r = gestor.post("/nucleo/empresas", {"nome": f"Empresa {origem[:4]}", "origem": origem})
        assert r.status_code == 201 and r.json()["origem"] == origem
    assert gestor.post("/nucleo/empresas", {"nome": "Longa", "origem": "x" * 101}).status_code == 422


# ------------------------------------------------------------------------------------------------- C. LGPD
def test_pessoa_base_legal_e_permissoes(gestor, db):
    r = gestor.post("/nucleo/pessoas", {"nome": "Paula", "base_legal": "consentimento",
                                        "permissoes_comunicacao": ["email_marketing", "whatsapp_telefone"]})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["base_legal"] == "consentimento"
    assert p["permissoes_comunicacao"] == ["whatsapp_telefone", "email_marketing"]
    sem = gestor.post("/nucleo/pessoas", {"nome": "Rafael"}).json()
    assert sem["base_legal"] is None and sem["permissoes_comunicacao"] == []
    # PATCH grava só o enviado
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"permissoes_comunicacao": ["opt_out"]})
    assert r.status_code == 200 and r.json()["permissoes_comunicacao"] == ["opt_out"]
    assert r.json()["base_legal"] == "consentimento"
    alt = db.query(Auditoria).filter_by(acao="pessoa.alterar", entidade_id=str(p["id"])).one()
    assert alt.antes_json["permissoes_comunicacao"] == ["whatsapp_telefone", "email_marketing"]
    assert alt.depois_json["permissoes_comunicacao"] == ["opt_out"]
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"base_legal": ""})
    assert r.json()["base_legal"] is None
    # filtro
    gestor.patch(f"/nucleo/pessoas/{sem['id']}", {"base_legal": "contrato"})
    assert [x["nome"] for x in gestor.get("/nucleo/pessoas", params={"base_legal": "contrato"}).json()["itens"]] == [
        "Rafael"]
    assert [x["nome"] for x in gestor.get("/nucleo/pessoas", params={"base_legal": "sem"}).json()["itens"]] == ["Paula"]


def test_pessoa_lgpd_validacoes_403_404(gestor, leitura):
    r = gestor.post("/nucleo/pessoas", {"nome": "X", "permissoes_comunicacao": ["opt_out", "email_marketing"]})
    assert r.status_code == 400 and r.json()["detail"] == "Opt-out não combina com outras permissões de comunicação."
    r = gestor.post("/nucleo/pessoas", {"nome": "X", "permissoes_comunicacao": ["sms"]})
    assert r.status_code == 400 and "desconhecida: sms" in r.json()["detail"]
    r = gestor.post("/nucleo/pessoas", {"nome": "X", "base_legal": "vontade"})
    assert r.status_code == 400 and r.json()["detail"].startswith("Base legal inválida")
    assert gestor.get("/nucleo/pessoas", params={"base_legal": "vontade"}).status_code == 400
    assert gestor.post("/nucleo/pessoas", {"nome": "X", "permissoes_comunicacao": "opt_out"}).status_code == 422
    assert gestor.patch("/nucleo/pessoas/999", {"base_legal": "contrato"}).status_code == 404
    p = gestor.post("/nucleo/pessoas", {"nome": "Y"}).json()
    assert leitura.patch(f"/nucleo/pessoas/{p['id']}", {"base_legal": "contrato"}).status_code == 403
    assert leitura.get(f"/nucleo/pessoas/{p['id']}").json()["permissoes_comunicacao"] == []


def test_planilha_de_pessoas_com_base_legal_e_permissoes(gestor, db):
    # a célula com ";" precisa ir entre aspas no CSV separado por ";"
    arq = _csv("Nome;E-mail;Base legal;Permissão de comunicação",
               'Paula;paula@aurora.com;Consentimento;"Aceita contato via WhatsApp / Telefone; email_marketing"',
               'Rafael;rafael@x.com;legitimo interesse;"Opt-out / Não deseja receber comunicações; comercial_pontual"',
               "Camila;camila@x.com;Talvez;")
    d = _importar(gestor, "pessoas", arq).json()
    assert {(e["linha"], e["coluna"]) for e in d["erros"]} == {(3, "Permissão de comunicação"), (4, "Base legal")}
    assert any("Opt-out não combina" in e["mensagem"] for e in d["erros"])
    arq = _csv("Nome;E-mail;Base legal;Permissão de comunicação",
               'Paula;paula@aurora.com;Consentimento;"Aceita contato via WhatsApp / Telefone; email_marketing"',
               "Rafael;rafael@x.com;Execução de contrato / Pré-contrato;opt-out / não deseja receber comunicações")
    assert _importar(gestor, "pessoas", arq, simular=False).status_code == 200
    db.expire_all()
    paula = db.query(Pessoa).filter_by(nome="Paula").one()
    assert (paula.base_legal, paula.permissoes_comunicacao) == ("consentimento", ["whatsapp_telefone", "email_marketing"])
    rafael = db.query(Pessoa).filter_by(nome="Rafael").one()
    assert (rafael.base_legal, rafael.permissoes_comunicacao) == ("contrato", ["opt_out"])
    # modelo traz as duas colunas
    from io import BytesIO

    from openpyxl import load_workbook

    ws = load_workbook(BytesIO(gestor.get("/nucleo/planilhas/pessoas/modelo").content))["Dados"]
    cab = [c.value for c in ws[1]]
    assert "Base legal" in cab and "Permissão de comunicação" in cab


# ------------------------------------------------------------------------------------------------- D. campos
def test_campo_multipla_e_link_na_empresa(gestor, db):
    m = gestor.post("/nucleo/campos", {"nome": "Canais", "tipo": "multipla", "objeto": "empresa",
                                       "opcoes": ["E-mail", "Telefone", "Visita"]})
    assert m.status_code == 201 and m.json()["tipo_rotulo"] == "Seleção múltipla"
    link = gestor.post("/nucleo/campos", {"nome": "Portal", "tipo": "link", "objeto": "empresa"})
    assert link.status_code == 201 and link.json()["opcoes"] == []
    r = gestor.post("/nucleo/campos", {"nome": "Vazia", "tipo": "multipla", "objeto": "empresa"})
    assert r.status_code == 400 and r.json()["detail"] == "Campo de seleção múltipla precisa de ao menos uma opção."
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora", "campos_custom": {
        "canais": ["Visita", "E-mail"], "portal": "portal.aurora.com.br"}})
    assert e.status_code == 201, e.text
    assert e.json()["campos_custom"] == {"canais": ["E-mail", "Visita"], "portal": "https://portal.aurora.com.br"}
    r = gestor.patch(f"/nucleo/empresas/{e.json()['id']}", {"campos_custom": {"canais": ["Fax"]}})
    assert r.status_code == 400 and "“Fax” não é uma das opções" in r.json()["detail"]
    r = gestor.patch(f"/nucleo/empresas/{e.json()['id']}", {"campos_custom": {"portal": "javascript:alert(1)"}})
    assert r.status_code == 400 and "http:// ou https://" in r.json()["detail"]
    # opção marcada não sai da lista; contagem de preenchidos
    r = gestor.patch(f"/nucleo/campos/{m.json()['id']}", {"opcoes": ["E-mail", "Telefone"]})
    assert r.status_code == 400 and "“Visita” está em uso em 1 registro(s)" in r.json()["detail"]
    assert gestor.get(f"/nucleo/campos/{m.json()['id']}").json()["registros_preenchidos"] == 1
    # planilha: várias opções separadas por ";"
    arq = _csv("Nome;Canais;Portal", 'Vértice;"telefone; e-mail";https://vertice.com.br')
    assert _importar(gestor, "empresas", arq, simular=False).status_code == 200
    v = gestor.get("/nucleo/empresas", params={"q": "Vértice"}).json()["itens"][0]
    assert v["campos_custom"] == {"canais": ["E-mail", "Telefone"], "portal": "https://vertice.com.br"}
    d = _importar(gestor, "empresas", _csv("Nome;Canais", "Outra;Fax")).json()
    assert d["erros"][0]["coluna"] == "Canais"


def test_exigido_na_etapa_devolve_funil_e_valida(gestor, db):
    funil = Funil(nome="Serviços B2B")
    inativo = Funil(nome="Antigo", ativo=False)
    db.add_all([funil, inativo])
    db.flush()
    etapa = Etapa(funil_id=funil.id, nome="Proposta", ordem=1, probabilidade=50)
    velha = Etapa(funil_id=inativo.id, nome="Velha", ordem=1, probabilidade=10)
    db.add_all([etapa, velha])
    db.commit()
    c = gestor.post("/nucleo/campos", {"nome": "Escopo", "tipo": "texto", "objeto": "oportunidade",
                                       "exigido_na_etapa_id": etapa.id})
    assert c.status_code == 201
    assert (c.json()["funil_id"], c.json()["funil_nome"], c.json()["etapa_nome"]) == (funil.id, "Serviços B2B",
                                                                                     "Proposta")
    lista = gestor.get("/nucleo/campos", params={"objeto": "oportunidade"}).json()
    assert lista[0]["funil_nome"] == "Serviços B2B"
    r = gestor.patch(f"/nucleo/campos/{c.json()['id']}", {"exigido_na_etapa_id": velha.id})
    assert r.status_code == 400 and "funil desta etapa está inativo" in r.json()["detail"]
    r = gestor.patch(f"/nucleo/campos/{c.json()['id']}", {"exigido_na_etapa_id": None})
    assert r.status_code == 200 and r.json()["funil_id"] is None and r.json()["funil_nome"] is None


def test_oportunidade_com_campo_multipla(gestor, db):
    gestor.post("/nucleo/campos", {"nome": "Produtos de interesse", "tipo": "multipla", "objeto": "oportunidade",
                                   "opcoes": ["CRM", "ERP"]})
    from app.modules.nucleo import servico

    funil = Funil(nome="F")
    db.add(funil)
    db.flush()
    db.add(Oportunidade(titulo="O", funil_id=funil.id, responsavel_id=gestor.usuario.id,
                        campos_custom={"produtos_de_interesse": ["CRM", "ERP"]}))
    db.commit()
    assert servico.valores_em_uso(db, "oportunidade", "produtos_de_interesse") == {"CRM": 1, "ERP": 1}
