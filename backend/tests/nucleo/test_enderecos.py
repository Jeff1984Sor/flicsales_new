"""Endereço estruturado em empresa/pessoa e a marca "usar endereço da empresa" (propagação auditada)."""

from app.core.models import Auditoria
from app.modules.nucleo.models import Pessoa

ENDERECO = {"cep": "01310100", "logradouro": "Avenida Paulista", "numero": "1000", "bairro": "Bela Vista",
            "cidade": "São Paulo", "uf": "sp"}


def _empresa(api, **kw):
    r = api.post("/nucleo/empresas", {"nome": "Aurora Consultoria", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_empresa_grava_endereco_normalizado(gestor):
    e = _empresa(gestor, **ENDERECO)
    assert (e["cep"], e["uf"], e["cidade"], e["complemento"]) == ("01310-100", "SP", "São Paulo", None)
    lista = gestor.get("/nucleo/empresas").json()["itens"][0]
    assert lista["logradouro"] == "Avenida Paulista"


def test_endereco_invalido_400(gestor):
    r = gestor.post("/nucleo/empresas", {"nome": "X", "cep": "123"})
    assert r.status_code == 400 and r.json()["detail"] == "CEP inválido: informe os 8 dígitos."
    r = gestor.post("/nucleo/empresas", {"nome": "X", "uf": "ZZ"})
    assert r.status_code == 400 and "UF inválida" in r.json()["detail"]
    assert gestor.post("/nucleo/empresas", {"nome": "X", "uf": "SPX"}).status_code == 422


def test_pessoa_nasce_com_endereco_da_empresa(gestor):
    e = _empresa(gestor, **ENDERECO)
    p = gestor.post("/nucleo/pessoas", {"nome": "Paula", "empresa_id": e["id"]}).json()
    assert p["usa_endereco_da_empresa"] is True and p["cep"] == "01310-100" and p["numero"] == "1000"
    sem = gestor.post("/nucleo/pessoas", {"nome": "Avulsa", "cidade": "Recife"}).json()
    assert sem["cidade"] == "Recife" and sem["usa_endereco_da_empresa"] is False  # editou à mão


def test_mudar_endereco_da_empresa_propaga_so_para_quem_tem_a_marca(gestor, db):
    e = _empresa(gestor, **ENDERECO)
    junto = gestor.post("/nucleo/pessoas", {"nome": "Paula", "empresa_id": e["id"]}).json()
    proprio = gestor.post("/nucleo/pessoas", {"nome": "Rafael", "empresa_id": e["id"], "cidade": "Campinas"}).json()
    assert proprio["usa_endereco_da_empresa"] is False
    r = gestor.patch(f"/nucleo/empresas/{e['id']}", {"cep": "20040-020", "logradouro": "Avenida Rio Branco",
                                                      "numero": "1", "bairro": "Centro", "cidade": "Rio de Janeiro",
                                                      "uf": "RJ"})
    assert r.status_code == 200
    p = gestor.get(f"/nucleo/pessoas/{junto['id']}").json()
    assert (p["cep"], p["cidade"], p["uf"]) == ("20040-020", "Rio de Janeiro", "RJ")
    outro = gestor.get(f"/nucleo/pessoas/{proprio['id']}").json()
    assert outro["cidade"] == "Campinas" and outro["logradouro"] is None
    aud = db.query(Auditoria).filter_by(acao="pessoa.endereco_da_empresa").all()
    assert [a.entidade_id for a in aud] == [str(junto["id"])]
    # mudar outro campo da empresa não propaga de novo
    gestor.patch(f"/nucleo/empresas/{e['id']}", {"segmento": "Consultoria"})
    assert db.query(Auditoria).filter_by(acao="pessoa.endereco_da_empresa").count() == 1


def test_editar_endereco_da_pessoa_desliga_e_religar_copia(gestor, db):
    e = _empresa(gestor, **ENDERECO)
    p = gestor.post("/nucleo/pessoas", {"nome": "Paula", "empresa_id": e["id"]}).json()
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"numero": "55"}).json()
    assert r["usa_endereco_da_empresa"] is False and r["numero"] == "55"
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"usa_endereco_da_empresa": True}).json()
    assert r["usa_endereco_da_empresa"] is True and r["numero"] == "1000"
    # formulário inteiro reenviado com a marca ligada não desliga
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"nome": "Paula M.", **ENDERECO, "usa_endereco_da_empresa": True})
    assert r.json()["usa_endereco_da_empresa"] is True


def test_trocar_de_empresa_copia_o_endereco_da_nova(gestor):
    a = _empresa(gestor, **ENDERECO)
    b = gestor.post("/nucleo/empresas", {"nome": "Vértice", "cidade": "Curitiba", "uf": "PR"}).json()
    p = gestor.post("/nucleo/pessoas", {"nome": "Paula", "empresa_id": a["id"]}).json()
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"empresa_id": b["id"]}).json()
    assert (r["cidade"], r["uf"], r["logradouro"]) == ("Curitiba", "PR", None)


def test_fornecedor_tem_endereco_e_propaga(financeiro, db):
    f = financeiro.post("/nucleo/fornecedores", {"nome": "Nuvem Digital", "contato": "Joana", **ENDERECO}).json()
    assert f["cep"] == "01310-100"
    contato = db.query(Pessoa).filter_by(nome="Joana").one()
    assert contato.usa_endereco_da_empresa and contato.cidade == "São Paulo"
    r = financeiro.patch(f"/nucleo/fornecedores/{f['id']}", {"cidade": "Santos"})
    assert r.status_code == 200 and r.json()["cidade"] == "Santos"
    db.expire_all()
    assert db.get(Pessoa, contato.id).cidade == "Santos"


def test_pessoa_404_e_permissao(gestor, leitura):
    assert gestor.patch("/nucleo/pessoas/999", {"cidade": "X"}).status_code == 404
    e = _empresa(gestor)
    assert leitura.patch(f"/nucleo/empresas/{e['id']}", {"cidade": "X"}).status_code == 403
