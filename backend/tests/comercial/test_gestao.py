"""Propostas, metas e forecast, desempenho, dashboards/indicadores, playbooks e modelos."""

from datetime import timedelta

from sqlalchemy import select

from app.core.db import hoje
from app.modules.nucleo.models import CampoCustom
from tests.comercial.conftest import funil_demo, oportunidade, usuario

API = "/api/comercial"


def _ganhar(client, cab, op_id, valor="24000"):
    r = client.post(f"{API}/oportunidades/{op_id}/ganhar", headers=cab, json={
        "valor": valor, "condicao": "Parcela única", "primeiro_vencimento": (hoje() + timedelta(days=5)).isoformat()})
    assert r.status_code == 200, r.text


# ================================================================================================ propostas
def _proposta(op_id, **kw):
    base = {"titulo": "Proposta consultoria", "oportunidade_id": op_id, "escopo": "Diagnóstico e plano",
            "quantidade": "2", "preco_unitario": "12000", "desconto_pct": "0",
            "validade": (hoje() + timedelta(days=15)).isoformat(), "condicao": "2 parcelas"}
    return {**base, **kw}


def test_proposta_total_versao_e_aceite(client, marina, demo):
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(op.id, mensalidade_adicional="500"))
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["total"] == "24000.00" and p["versao"] == 1 and p["empresa_nome"] == "Aurora Consultoria"

    r = client.post(f"{API}/propostas/{p['id']}/duplicar", headers=marina)
    assert r.status_code == 201 and r.json()["versao"] == 2 and r.json()["status"] == "rascunho"

    r = client.patch(f"{API}/propostas/{p['id']}", headers=marina, json={"status": "aceita"})
    assert r.status_code == 200 and r.json()["status"] == "aceita"
    # "Aceita" não fecha a oportunidade
    assert client.get(f"{API}/oportunidades/{op.id}", headers=marina).json()["resultado"] == "aberta"
    hist = client.get(f"{API}/oportunidades/{op.id}/historico", headers=marina).json()
    assert hist[0]["tipo"] == "proposta" and "Aceita" in hist[0]["texto"]


def test_proposta_validacoes(client, marina, demo):
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(op.id, quantidade="0"))
    assert r.status_code == 400 and r.json()["detail"] == "Quantidade deve ser positiva e desconto entre 0 e 100%"
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(op.id, desconto_pct="101"))
    assert r.status_code == 400 and r.json()["detail"] == "Quantidade deve ser positiva e desconto entre 0 e 100%"
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(op.id, desconto_pct="10"))
    assert r.status_code == 400 and r.json()["detail"] == "Registre a justificativa do desconto"
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(999))
    assert r.status_code == 400 and r.json()["detail"] == "Oportunidade não encontrada."
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(op.id, versao=1))
    assert r.status_code == 201
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(op.id, versao=1))
    assert r.status_code == 400 and "Duplicar" in r.json()["detail"]


def test_proposta_com_desconto_precisa_de_aprovacao(client, marina, gestor, demo):
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(
        op.id, desconto_pct="10", justificativa_desconto="Contrato de 12 meses"))
    assert r.status_code == 201
    p = r.json()
    assert p["total"] == "21600.00"
    r = client.patch(f"{API}/propostas/{p['id']}", headers=marina, json={"status": "enviada"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Proposta com desconto precisa de aprovação interna antes do envio."
    # Comercial não aprova (alçada do Gestor)
    r = client.patch(f"{API}/propostas/{p['id']}", headers=marina, json={"status": "aprovada_internamente"})
    assert r.status_code == 403
    r = client.patch(f"{API}/propostas/{p['id']}", headers=gestor, json={"status": "aprovada_internamente"})
    assert r.status_code == 200
    r = client.patch(f"{API}/propostas/{p['id']}", headers=marina, json={"status": "enviada"})
    assert r.status_code == 200


def test_proposta_404_403_so_meus(client, marina, financeiro, demo, so_meus):
    assert client.get(f"{API}/propostas/999", headers=marina).status_code == 404
    op = oportunidade(demo, "Projeto de consultoria")
    assert client.post(f"{API}/propostas", headers=financeiro, json=_proposta(op.id)).status_code == 403
    da_lucas = oportunidade(demo, "Expansão de operação")
    r = client.post(f"{API}/propostas", headers=marina, json=_proposta(da_lucas.id))
    assert r.status_code == 400 and r.json()["detail"] == "Oportunidade não encontrada."


# ================================================================================================ metas e forecast
def test_meta_apuracao(client, gestor, demo):
    marina = usuario(demo, "marina")
    inicio, fim = hoje().replace(day=1), hoje() + timedelta(days=30)
    r = client.post(f"{API}/metas", headers=gestor, json={
        "nome": "Receita do mês", "responsavel_tipo": "pessoa", "responsavel_id": marina.id,
        "inicio": inicio.isoformat(), "fim": fim.isoformat(), "indicador": "receita_unica_ganha", "alvo": "48000"})
    assert r.status_code == 201, r.text
    meta = r.json()
    assert meta["realizado"] == "0" or meta["realizado"].startswith("0")
    _ganhar(client, gestor, oportunidade(demo, "Projeto de consultoria").id)
    m = client.get(f"{API}/metas/{meta['id']}", headers=gestor).json()
    assert m["realizado"] == "24000.00" and m["percentual"] == "50.0" and "÷ meta" in m["formula"]


def test_meta_validacoes(client, gestor):
    base = {"nome": "Meta", "responsavel_tipo": "equipe", "equipe": "Comercial", "indicador": "vendas_ganhas",
            "alvo": "5", "inicio": hoje().isoformat(), "fim": (hoje() - timedelta(days=1)).isoformat()}
    r = client.post(f"{API}/metas", headers=gestor, json=base)
    assert r.status_code == 400 and r.json()["detail"] == "A data final deve ser igual ou posterior ao início"
    r = client.post(f"{API}/metas", headers=gestor, json={**base, "fim": hoje().isoformat(), "alvo": "0"})
    assert r.status_code == 400 and r.json()["detail"] == "A meta numérica deve ser positiva."
    r = client.post(f"{API}/metas", headers=gestor, json={**base, "fim": hoje().isoformat(),
                                                          "responsavel_tipo": "pessoa"})
    assert r.status_code == 400 and r.json()["detail"] == "Escolha a pessoa responsável pela meta."
    assert client.patch(f"{API}/metas/999", headers=gestor, json={"nome": "x"}).status_code == 404


def test_forecast_ponderado(client, gestor, leitura, demo):
    r = client.get(f"{API}/forecast", headers=gestor, params={"funil_id": funil_demo(demo).id})
    assert r.status_code == 200
    f = r.json()
    # 24.000×75% + 18.000×50% + 12.000×25% + 9.600×10%
    assert f["pipeline_aberto"] == "63600.00" and f["ponderado"] == "30960.00"
    assert f["mrr_potencial"] == "800.00" and f["sem_previsao"] == 2
    assert "probabilidade" in f["formulas"]["ponderado"]
    assert client.post(f"{API}/metas", headers=leitura, json={}).status_code == 403


# ================================================================================================ desempenho
def test_desempenho_com_formulas_e_evidencias(client, gestor, demo):
    _ganhar(client, gestor, oportunidade(demo, "Projeto de consultoria").id)
    op = oportunidade(demo, "Expansão de operação")
    client.post(f"{API}/oportunidades/{op.id}/perder", headers=gestor, json={"motivo": "Preço"})
    r = client.get(f"{API}/desempenho", headers=gestor)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["conversao"]["valor"] == "50.0" and d["conversao"]["detalhe"] == "1 ganhas / 2 encerradas"
    assert d["receita_ganha"]["valor"] == "24000.00" and d["ticket_medio"]["valor"] == "24000.00"
    assert "÷" in d["conversao"]["formula"]
    assert [v["nome"] for v in d["vendedores"]] == ["Lucas Ribeiro", "Marina Costa"]  # alfabética, sem ranking

    lucas = usuario(demo, "lucas")
    ev = client.get(f"{API}/desempenho/evidencias", headers=gestor, params={"usuario_id": lucas.id}).json()
    assert [o["titulo"] for o in ev["perdidas"]] == ["Expansão de operação"]
    assert [o["titulo"] for o in ev["sem_proxima_acao"]] == ["Consultoria recorrente"]
    assert "lacuna" in ev["gargalo"] and ev["limites"]


def test_desempenho_periodo_invalido_e_so_meus(client, marina, demo, so_meus):
    r = client.get(f"{API}/desempenho", headers=marina, params={"inicio": "2026-12-01", "fim": "2026-11-01"})
    assert r.status_code == 400
    d = client.get(f"{API}/desempenho", headers=marina).json()
    assert [v["nome"] for v in d["vendedores"]] == ["Marina Costa"]
    lucas = usuario(demo, "lucas")
    assert client.get(f"{API}/desempenho/evidencias", headers=marina,
                      params={"usuario_id": lucas.id}).status_code == 404


# ================================================================================================ dashboards
def test_dashboard_e_indicador_configuravel(client, gestor, leitura, demo):
    d = client.get(f"{API}/dashboards", headers=gestor).json()
    assert d["pipeline_alto_interesse"] == "42000.00" and d["oportunidades"] == 4 and d["proximas_acoes"] == 3
    assert [e["etapa"] for e in d["pipeline_por_etapa"]] == ["Entrada", "Discovery", "Proposta", "Negociação"]

    campo = demo.scalar(select(CampoCustom).where(CampoCustom.slug == "interesse"))
    previa = {"metrica": "soma_valor_unico", "filtro_campo_id": campo.id, "filtro_valor": "Médio"}
    r = client.post(f"{API}/indicadores/previa", headers=leitura, json=previa)  # prévia só exige "ver"
    assert r.status_code == 200 and r.json()["valor"] == "21600.00" and r.json()["quantidade"] == 2
    r = client.post(f"{API}/indicadores/previa", headers=gestor, json={**previa, "filtro_valor": ""})
    assert r.status_code == 400

    r = client.post(f"{API}/indicadores", headers=gestor, json={"nome": "Pipeline médio interesse", **previa})
    assert r.status_code == 201 and r.json()["resultado"]["valor"] == "21600.00"
    assert client.post(f"{API}/indicadores", headers=leitura, json={"nome": "x", **previa}).status_code == 403
    d = client.get(f"{API}/dashboards", headers=gestor).json()
    assert d["indicadores"][0]["filtro_campo_nome"] == "Interesse"
    r = client.patch(f"{API}/indicadores/{d['indicadores'][0]['id']}", headers=gestor, json={"ativo": False})
    assert r.status_code == 200 and not r.json()["ativo"]
    assert client.patch(f"{API}/indicadores/999", headers=gestor, json={"nome": "x"}).status_code == 404


# ================================================================================================ playbooks e modelos
def test_playbook_crud(client, gestor, leitura, demo):
    f = funil_demo(demo)
    r = client.post(f"{API}/playbooks", headers=gestor, json={"nome": "Discovery B2B", "funil_id": f.id,
                                                              "objetivo": "Mapear dor", "criterios_avanco": "  "})
    assert r.status_code == 400 and r.json()["detail"] == "Informe os critérios para avançar."
    r = client.post(f"{API}/playbooks", headers=gestor, json={
        "nome": "Discovery B2B", "funil_id": f.id, "objetivo": "Mapear dor e decisor",
        "criterios_avanco": "Necessidade e decisor confirmados", "perguntas_discovery": "Qual o impacto?"})
    assert r.status_code == 201, r.text
    p = r.json()
    r = client.patch(f"{API}/playbooks/{p['id']}", headers=gestor, json={"ativo": False})
    assert r.status_code == 200 and r.json()["ativo"] is False
    assert client.get(f"{API}/playbooks", headers=gestor).json() == []
    assert client.post(f"{API}/playbooks", headers=leitura, json={}).status_code == 403
    assert client.get(f"{API}/playbooks/999", headers=gestor).status_code == 404


def test_modelo_com_variaveis_e_previa(client, gestor, demo):
    r = client.post(f"{API}/modelos", headers=gestor, json={
        "nome": "Follow-up de proposta", "canal": "email", "finalidade": "follow_up",
        "assunto": "Proposta para {{empresa.nome}}",
        "conteudo": "Olá, {{contato.nome}}! Sobre {{oportunidade.titulo}}, {{titulo.vencimento}}.", "status": "revisado"})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["variaveis"] == ["empresa.nome", "contato.nome", "oportunidade.titulo", "titulo.vencimento"]
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/modelos/{m['id']}/previa", headers=gestor, json={"oportunidade_id": op.id})
    assert r.status_code == 200
    pv = r.json()
    assert pv["assunto"] == "Proposta para Aurora Consultoria"
    assert pv["conteudo"].startswith("Olá, Paula Mendes! Sobre Projeto de consultoria")
    assert pv["faltando"] == ["titulo.vencimento"]

    r = client.post(f"{API}/modelos", headers=gestor, json={"nome": "X", "canal": "fax", "finalidade": "follow_up",
                                                            "conteudo": "x"})
    assert r.status_code == 422
    r = client.patch(f"{API}/modelos/{m['id']}", headers=gestor, json={"status": "rascunho"})
    assert r.status_code == 200 and r.json()["status"] == "rascunho"
    assert client.patch(f"{API}/modelos/999", headers=gestor, json={"nome": "x"}).status_code == 404


def test_opcoes_para_formularios(client, marina):
    r = client.get(f"{API}/oportunidades/opcoes", headers=marina)
    assert r.status_code == 200
    o = r.json()
    assert "Aurora Consultoria" in [e["nome"] for e in o["empresas"]]
    assert o["interesse"] == ["Baixo", "Médio", "Alto"] and "2 parcelas iguais" in o["condicoes_ganho"]
    assert o["funis"][0]["etapas"]
