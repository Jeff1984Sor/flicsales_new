"""Funis, etapas e oportunidades: sucesso, validação (mensagens do protótipo), 403, 404 e "só meus registros"."""

from datetime import timedelta

from sqlalchemy import select

from app.core.db import hoje
from app.core.models import Auditoria
from app.modules.comercial.models import Etapa, Funil, OportunidadeEvento
from app.modules.nucleo.models import CampoCustom, Empresa
from tests.comercial.conftest import etapa, funil_demo, oportunidade, usuario

API = "/api/comercial"


# ------------------------------------------------------------------------------------------------ funis
def test_lista_funil_demo_com_etapas(client, gestor):
    r = client.get(f"{API}/funis", headers=gestor)
    assert r.status_code == 200
    [f] = r.json()
    assert [(e["nome"], e["probabilidade"], e["limite_dias"]) for e in f["etapas"]] == [
        ("Entrada", 10, 2), ("Discovery", 25, 7), ("Proposta", 50, 10), ("Negociação", 75, 14)]


def test_criar_funil_com_probabilidades_parametrizadas(client, gestor, demo):
    r = client.post(f"{API}/funis", headers=gestor,
                    json={"nome": "Novos negócios", "etapas": ["Entrada", "Qualificação", "Discovery", "Proposta",
                                                                "Negociação"]})
    assert r.status_code == 201, r.text
    assert [e["probabilidade"] for e in r.json()["etapas"]] == [16, 32, 48, 64, 80]
    assert demo.scalar(select(Auditoria).where(Auditoria.acao == "funil.criar")) is not None


def test_funil_recusa_etapas_invalidas(client, gestor):
    msg = "Defina pelo menos duas etapas únicas, sem Ganha ou Perdida"
    for etapas in (["Entrada"], ["Entrada", "entrada"], ["Entrada", "Ganha"], ["Proposta", "Perdida"]):
        r = client.post(f"{API}/funis", headers=gestor, json={"nome": "X", "etapas": etapas})
        assert r.status_code == 400 and r.json()["detail"] == msg


def test_funil_nome_duplicado(client, gestor):
    r = client.post(f"{API}/funis", headers=gestor, json={"nome": "serviços b2b", "etapas": ["A", "B"]})
    assert r.status_code == 400 and r.json()["detail"] == "Já existe um funil com este nome."


def test_configurar_etapas(client, gestor, demo):
    f = funil_demo(demo)
    etapas = client.get(f"{API}/funis", headers=gestor).json()[0]["etapas"]
    cfg = [{"id": e["id"], "nome": e["nome"], "probabilidade": e["probabilidade"], "limite_dias": e["limite_dias"],
            "criterios": e["criterios"]} for e in etapas]
    cfg[0]["probabilidade"] = 15
    cfg[0]["criterios"] = "Contato e interesse"
    r = client.put(f"{API}/funis/{f.id}/etapas", headers=gestor, json={"etapas": cfg})
    assert r.status_code == 200, r.text
    assert r.json()["etapas"][0]["probabilidade"] == 15

    cfg[0]["probabilidade"] = 120
    r = client.put(f"{API}/funis/{f.id}/etapas", headers=gestor, json={"etapas": cfg})
    assert r.status_code == 400 and r.json()["detail"] == "A probabilidade da etapa vai de 0 a 100%."

    # etapa com oportunidades não é removida
    r = client.put(f"{API}/funis/{f.id}/etapas", headers=gestor, json={"etapas": [
        {**cfg[0], "probabilidade": 10}, cfg[1]]})
    assert r.status_code == 400 and "Mova as oportunidades" in r.json()["detail"]


def test_funil_404(client, gestor):
    assert client.patch(f"{API}/funis/999", headers=gestor, json={"nome": "X"}).status_code == 404


# ------------------------------------------------------------------------------------------------ oportunidades
def test_kanban_por_funil(client, marina, demo):
    f = funil_demo(demo)
    r = client.get(f"{API}/oportunidades", headers=marina, params={"funil_id": f.id, "resultado": "aberta"})
    assert r.status_code == 200
    por_titulo = {o["titulo"]: o for o in r.json()}
    assert set(por_titulo) == {"Projeto de consultoria", "Expansão de operação", "Diagnóstico estratégico",
                               "Consultoria recorrente"}
    aurora = por_titulo["Projeto de consultoria"]
    assert aurora["etapa_nome"] == "Negociação" and aurora["interesse"] == "Alto"
    assert aurora["empresa_nome"] == "Aurora Consultoria" and aurora["responsavel_nome"] == "Marina Costa"
    # Horizonte está há 9 dias em Discovery (limite 7)
    assert por_titulo["Diagnóstico estratégico"]["alem_do_limite"] is True


def test_detalhe_traz_contexto_com_fonte(client, marina, demo):
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.get(f"{API}/oportunidades/{op.id}", headers=marina)
    assert r.status_code == 200
    d = r.json()
    assert "Discovery Aurora" in d["contexto"]["fonte"]
    assert d["comunicacoes"] == 1 and d["atividades_pendentes"] == 1


def test_criar_reaproveita_empresa_pelo_nome_normalizado(client, marina, demo):
    f = funil_demo(demo)
    antes = demo.scalar(select(Empresa.id).where(Empresa.nome == "Aurora Consultoria"))
    r = client.post(f"{API}/oportunidades", headers=marina, json={
        "titulo": "Fase 2", "funil_id": f.id, "empresa_nome": "  aurora   consultória "})
    assert r.status_code == 201, r.text
    assert r.json()["empresa_id"] == antes
    assert len(list(demo.scalars(select(Empresa).where(Empresa.nome_chave == "aurora consultoria")))) == 1


def test_criar_validacoes(client, marina, demo):
    f = funil_demo(demo)
    r = client.post(f"{API}/oportunidades", headers=marina, json={"titulo": "X", "funil_id": 999})
    assert r.status_code == 400 and r.json()["detail"] == "Funil não encontrado."
    r = client.post(f"{API}/oportunidades", headers=marina, json={"titulo": "X", "funil_id": f.id, "valor_unico": "-1"})
    assert r.status_code == 400 and r.json()["detail"] == "Valores da oportunidade não podem ser negativos."
    r = client.post(f"{API}/oportunidades", headers=marina, json={"funil_id": f.id})
    assert r.status_code == 422


def test_mover_etapa_grava_evento(client, marina, demo):
    op = oportunidade(demo, "Diagnóstico estratégico")
    r = client.post(f"{API}/oportunidades/{op.id}/mover", headers=marina, json={"etapa_id": etapa(demo, "Proposta").id})
    assert r.status_code == 200
    assert r.json()["etapa_nome"] == "Proposta" and r.json()["dias_na_etapa"] == 0
    ev = demo.scalar(select(OportunidadeEvento).where(OportunidadeEvento.oportunidade_id == op.id)
                     .order_by(OportunidadeEvento.id.desc()))
    assert ev.tipo == "etapa" and ev.texto == "Movida de Discovery para Proposta"


def test_mover_para_etapa_de_outro_funil(client, gestor, demo):
    client.post(f"{API}/funis", headers=gestor, json={"nome": "Outro", "etapas": ["A", "B"]})
    outro = demo.scalar(select(Funil).where(Funil.nome == "Outro"))
    etapa_a = demo.scalar(select(Etapa).where(Etapa.funil_id == outro.id).limit(1))
    op = oportunidade(demo, "Diagnóstico estratégico")
    r = client.post(f"{API}/oportunidades/{op.id}/mover", headers=gestor, json={"etapa_id": etapa_a.id})
    assert r.status_code == 400 and r.json()["detail"] == "A etapa não pertence ao funil da oportunidade."


def test_campo_exigido_na_etapa(client, marina, demo):
    demo.add(CampoCustom(nome="Orçamento confirmado", slug="orcamento_ok", tipo="sim_nao", objeto="oportunidade",
                         exigido_na_etapa_id=etapa(demo, "Proposta").id))
    demo.commit()
    op = oportunidade(demo, "Diagnóstico estratégico")
    r = client.post(f"{API}/oportunidades/{op.id}/mover", headers=marina, json={"etapa_id": etapa(demo, "Proposta").id})
    assert r.status_code == 400 and r.json()["detail"] == "Preencha Orçamento confirmado antes de mover para Proposta."


def test_editar_completo_e_proxima_acao(client, marina, demo):
    op = oportunidade(demo, "Consultoria recorrente")
    r = client.patch(f"{API}/oportunidades/{op.id}", headers=marina, json={
        "valor_recorrente_mensal": "900", "decisor": "Diego", "interesse": "Alto",
        "proxima_acao": "Ligar para Diego", "proxima_acao_prazo": (hoje() + timedelta(days=1)).isoformat()})
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["valor_recorrente_mensal"] == "900.00" and o["interesse"] == "Alto" and o["decisor"] == "Diego"
    tipos = [e["tipo"] for e in client.get(f"{API}/oportunidades/{op.id}/historico", headers=marina).json()]
    assert tipos[0] == "proxima_acao"


def test_perder_exige_motivo_e_reabrir(client, marina, demo):
    op = oportunidade(demo, "Diagnóstico estratégico")
    r = client.post(f"{API}/oportunidades/{op.id}/perder", headers=marina, json={"motivo": "  "})
    assert r.status_code == 400 and r.json()["detail"] == "Informe o motivo da perda"

    retomada = (hoje() + timedelta(days=90)).isoformat()
    r = client.post(f"{API}/oportunidades/{op.id}/perder", headers=marina,
                    json={"motivo": "Sem orçamento", "concorrente": "Concorrente X", "data_retomada": retomada})
    assert r.status_code == 200
    assert r.json()["resultado"] == "perdida" and r.json()["data_retomada"] == retomada

    r = client.post(f"{API}/oportunidades/{op.id}/mover", headers=marina, json={"etapa_id": etapa(demo, "Proposta").id})
    assert r.status_code == 400 and r.json()["detail"] == "Reabra a oportunidade antes de mudar de etapa."
    r = client.post(f"{API}/oportunidades/{op.id}/ganhar", headers=marina, json={"valor": "1000"})
    assert r.status_code == 400 and r.json()["detail"] == "Oportunidade perdida não pode ser ganha. Reabra antes."

    r = client.post(f"{API}/oportunidades/{op.id}/reabrir", headers=marina)
    assert r.status_code == 200 and r.json()["resultado"] == "aberta"
    tipos = [e["tipo"] for e in client.get(f"{API}/oportunidades/{op.id}/historico", headers=marina).json()]
    assert tipos[:2] == ["reaberta", "perdida"]


def test_ganha_nao_muda_valor_nem_reabre(client, marina, demo):
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/oportunidades/{op.id}/ganhar", headers=marina, json={
        "valor": "24000", "condicao": "Parcela única", "primeiro_vencimento": (hoje() + timedelta(days=5)).isoformat()})
    assert r.status_code == 200, r.text
    r = client.patch(f"{API}/oportunidades/{op.id}", headers=marina, json={"valor_unico": "30000"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Venda ganha: ajuste valores por revisão financeira, preservando títulos de origem"
    r = client.post(f"{API}/oportunidades/{op.id}/reabrir", headers=marina)
    assert r.status_code == 400


def test_ganhar_validacoes(client, marina, demo):
    f = funil_demo(demo)
    sem_empresa = client.post(f"{API}/oportunidades", headers=marina, json={"titulo": "Sem empresa",
                                                                          "funil_id": f.id}).json()
    venc = (hoje() + timedelta(days=5)).isoformat()
    r = client.post(f"{API}/oportunidades/{sem_empresa['id']}/ganhar", headers=marina,
                    json={"valor": "1000", "primeiro_vencimento": venc})
    assert r.status_code == 400 and r.json()["detail"] == "Informe a empresa para preparar os recebíveis."
    r = client.post(f"{API}/oportunidades/{sem_empresa['id']}/ganhar", headers=marina,
                    json={"valor": "0", "empresa_nome": "Nova SA", "primeiro_vencimento": venc})
    assert r.status_code == 400 and r.json()["detail"] == "Informe o valor acordado."
    r = client.post(f"{API}/oportunidades/{sem_empresa['id']}/ganhar", headers=marina,
                    json={"valor": "1000", "empresa_nome": "Nova SA"})
    assert r.status_code == 400 and r.json()["detail"] == "Informe o primeiro vencimento."
    # nada ficou pela metade: continua aberta
    assert client.get(f"{API}/oportunidades/{sem_empresa['id']}", headers=marina).json()["resultado"] == "aberta"


def test_nota_no_historico(client, marina, demo):
    op = oportunidade(demo, "Projeto de consultoria")
    r = client.post(f"{API}/oportunidades/{op.id}/notas", headers=marina, json={"texto": "Cliente pediu desconto"})
    assert r.status_code == 201 and r.json()["tipo"] == "nota"


def test_404(client, marina):
    assert client.get(f"{API}/oportunidades/9999", headers=marina).status_code == 404
    assert client.post(f"{API}/oportunidades/9999/ganhar", headers=marina, json={"valor": "1"}).status_code == 404


def test_permissoes(client, financeiro, leitura, demo):
    f = funil_demo(demo)
    # Financeiro lê a origem comercial, mas não cria nem ganha
    assert client.get(f"{API}/oportunidades", headers=financeiro).status_code == 200
    r = client.post(f"{API}/oportunidades", headers=financeiro, json={"titulo": "X", "funil_id": f.id})
    assert r.status_code == 403
    op = oportunidade(demo, "Projeto de consultoria")
    assert client.post(f"{API}/oportunidades/{op.id}/ganhar", headers=financeiro, json={"valor": "1"}).status_code == 403
    # Somente leitura
    assert client.get(f"{API}/funis", headers=leitura).status_code == 200
    assert client.post(f"{API}/funis", headers=leitura, json={"nome": "X", "etapas": ["A", "B"]}).status_code == 403
    assert client.post(f"{API}/oportunidades/{op.id}/perder", headers=leitura, json={"motivo": "x"}).status_code == 403


def test_so_meus_registros(client, demo, so_meus, marina):
    marina_u, lucas = usuario(demo, "marina"), usuario(demo, "lucas")
    r = client.get(f"{API}/oportunidades", headers=marina)
    assert {o["titulo"] for o in r.json()} == {"Projeto de consultoria", "Diagnóstico estratégico"}
    da_lucas = oportunidade(demo, "Expansão de operação")
    assert client.get(f"{API}/oportunidades/{da_lucas.id}", headers=marina).status_code == 404
    assert client.post(f"{API}/oportunidades/{da_lucas.id}/perder", headers=marina,
                       json={"motivo": "x"}).status_code == 404
    # cria sempre para si mesma
    r = client.post(f"{API}/oportunidades", headers=marina, json={
        "titulo": "Minha", "funil_id": funil_demo(demo).id, "responsavel_id": lucas.id})
    assert r.status_code == 201 and r.json()["responsavel_id"] == marina_u.id
    # o Hoje também respeita o escopo
    hoje_r = client.get(f"{API}/hoje", headers=marina).json()
    assert hoje_r["oportunidades_ativas"] == 3
