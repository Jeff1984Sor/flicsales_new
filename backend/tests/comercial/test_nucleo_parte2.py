"""Comercial no pacote "Núcleo parte 2": classificação dos modelos de comunicação, campos padrões obrigatórios da
oportunidade e "exibir na etapa" nas opções do formulário."""

from sqlalchemy import select

from app.modules.comercial.models import Etapa, Funil


def _modelo(client, h, nome, classificacao=None):
    corpo = {"nome": nome, "canal": "email", "finalidade": "follow_up", "conteudo": "Olá {{contato.nome}}"}
    if classificacao:
        corpo["classificacao"] = classificacao
    return client.post("/api/comercial/modelos", json=corpo, headers=h)


def test_modelos_classificacao_e_filtros(client, gestor, marina, leitura):
    r = _modelo(client, gestor, "Comercial padrão")
    assert r.status_code == 201 and r.json()["classificacao"] == "comercial"
    assert _modelo(client, gestor, "Cobrança", "financeiro").status_code == 201
    geral = _modelo(client, gestor, "Boas-vindas", "geral").json()
    assert _modelo(client, gestor, "Ruim", "vendas").status_code == 422

    def nomes(params):
        r = client.get("/api/comercial/modelos", params=params, headers=gestor)
        assert r.status_code == 200, r.text
        return sorted(m["nome"] for m in r.json())

    todos = nomes({})
    assert {"Comercial padrão", "Cobrança", "Boas-vindas"} <= set(todos)
    assert "Cobrança" not in nomes({"contexto": "comercial"}) and "Boas-vindas" in nomes({"contexto": "comercial"})
    assert nomes({"contexto": "financeiro"}) == ["Boas-vindas", "Cobrança"]
    assert nomes({"classificacao": "financeiro,geral"}) == ["Boas-vindas", "Cobrança"]
    assert nomes({"contexto": "automacoes"}) == todos
    r = client.get("/api/comercial/modelos", params={"classificacao": "rh"}, headers=gestor)
    assert r.status_code == 400 and "Classificação inválida" in r.json()["detail"]
    r = client.patch(f"/api/comercial/modelos/{geral['id']}", json={"classificacao": "financeiro"}, headers=gestor)
    assert r.status_code == 200 and r.json()["classificacao"] == "financeiro"
    assert client.patch(f"/api/comercial/modelos/{geral['id']}", json={"classificacao": "geral"},
                        headers=leitura).status_code == 403
    assert client.patch("/api/comercial/modelos/9999", json={"classificacao": "geral"}, headers=gestor).status_code == 404


def test_oportunidade_respeita_campo_padrao_obrigatorio(client, gestor, marina, demo):
    funil = demo.scalar(select(Funil).limit(1))
    assert client.patch("/api/nucleo/campos/padroes/oportunidade/origem", json={"obrigatorio": True},
                        headers=gestor).status_code == 200
    r = client.post("/api/comercial/oportunidades", json={"titulo": "Sem origem", "funil_id": funil.id}, headers=marina)
    assert r.status_code == 400 and "Origem" in r.json()["detail"]
    r = client.post("/api/comercial/oportunidades", json={"titulo": "Com origem", "funil_id": funil.id,
                                                          "origem": "Site"}, headers=marina)
    assert r.status_code == 201, r.text
    op = r.json()["id"]
    assert client.patch(f"/api/comercial/oportunidades/{op}", json={"titulo": "Novo título"},
                        headers=marina).status_code == 200
    r = client.patch(f"/api/comercial/oportunidades/{op}", json={"origem": None}, headers=marina)
    assert r.status_code == 400 and "Origem" in r.json()["detail"]


def test_opcoes_trazem_exibir_na_etapa(client, gestor, demo):
    funil = demo.scalar(select(Funil).limit(1))
    etapa = demo.scalar(select(Etapa).where(Etapa.funil_id == funil.id, Etapa.ordem == 2))
    r = client.post("/api/nucleo/campos", json={"nome": "Decisão", "tipo": "data", "objeto": "oportunidade",
                                                 "exibir_etapa_id": etapa.id}, headers=gestor)
    assert r.status_code == 201, r.text
    campos = client.get("/api/comercial/oportunidades/opcoes", headers=gestor).json()["campos"]
    c = next(c for c in campos if c["slug"] == "decisao")
    assert (c["exibir_funil_id"], c["exibir_etapa_id"], c["exibir_etapa_ordem"]) == (funil.id, etapa.id, 2)
