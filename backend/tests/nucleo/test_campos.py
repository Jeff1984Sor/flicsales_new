"""Campos personalizados: catálogo, dependências (dashboards, automações, etapas) e arquivamento revisado."""

from app.core.models import Auditoria
from app.modules.comercial.models import Etapa, Funil, IndicadorConfig, Oportunidade
from app.modules.nucleo.models import CampoCustom
from app.modules.orquestracao.models import Automacao


def _interesse(gestor):
    r = gestor.post("/nucleo/campos", {"nome": "Interesse", "tipo": "lista", "objeto": "oportunidade",
                                       "opcoes": ["Baixo", "Médio", "Alto"]})
    assert r.status_code == 201, r.text
    return r.json()


def test_criar_listar_editar(gestor, db):
    c = _interesse(gestor)
    assert c["slug"] == "interesse" and c["opcoes"] == ["Baixo", "Médio", "Alto"] and c["arquivado"] is False
    gestor.post("/nucleo/campos", {"nome": "Origem", "tipo": "texto", "objeto": "empresa", "obrigatorio": True})
    assert len(gestor.get("/nucleo/campos").json()) == 2
    assert [x["nome"] for x in gestor.get("/nucleo/campos", params={"objeto": "empresa"}).json()] == ["Origem"]
    r = gestor.patch(f"/nucleo/campos/{c['id']}", {"nome": "Nível de interesse", "opcoes": ["Baixo", "Médio", "Alto",
                                                                                           "Urgente"]})
    assert r.status_code == 200 and r.json()["slug"] == "interesse" and len(r.json()["opcoes"]) == 4
    assert gestor.get(f"/nucleo/campos/{c['id']}").json()["nome"] == "Nível de interesse"
    assert db.query(Auditoria).filter_by(entidade="campo_custom").count() == 3


def test_validacoes(gestor):
    _interesse(gestor)
    assert gestor.post("/nucleo/campos", {"nome": "interesse", "tipo": "texto", "objeto": "oportunidade"}) \
        .json()["detail"] == "Já existe campo com este nome neste objeto."
    # mesmo nome em outro objeto é permitido
    assert gestor.post("/nucleo/campos", {"nome": "Interesse", "tipo": "texto", "objeto": "pessoa"}).status_code == 201
    assert gestor.post("/nucleo/campos", {"nome": "L", "tipo": "lista", "objeto": "empresa"}).json()["detail"] == \
        "Campo de seleção única precisa de ao menos uma opção."
    assert gestor.post("/nucleo/campos", {"nome": "L", "tipo": "cor", "objeto": "empresa"}).status_code == 422
    assert gestor.post("/nucleo/campos", {"nome": "L", "tipo": "texto", "objeto": "titulo"}).status_code == 422
    assert gestor.post("/nucleo/campos", {"nome": "L", "tipo": "texto", "objeto": "empresa",
                                          "exigido_na_etapa_id": 1}).json()["detail"] == \
        "Só campos de oportunidade podem ser exigidos por etapa."
    assert gestor.post("/nucleo/campos", {"nome": "L", "tipo": "texto", "objeto": "oportunidade",
                                          "exigido_na_etapa_id": 99}).json()["detail"] == (
        "Etapa não encontrada. Escolha o funil e depois uma etapa dele.")
    # tipo e objeto não mudam
    assert gestor.patch("/nucleo/campos/1", {"tipo": "texto"}).status_code == 422


def test_opcao_em_uso_nao_sai_da_lista(gestor, db):
    c = _interesse(gestor)
    funil = Funil(nome="F")
    db.add(funil)
    db.flush()
    db.add(Oportunidade(titulo="O", funil_id=funil.id, responsavel_id=gestor.usuario.id,
                        campos_custom={"interesse": "Alto"}))
    db.commit()
    r = gestor.patch(f"/nucleo/campos/{c['id']}", {"opcoes": ["Baixo", "Médio"]})
    assert r.status_code == 400 and r.json()["detail"].startswith("A opção “Alto” está em uso em 1 registro(s)")
    assert gestor.get(f"/nucleo/campos/{c['id']}").json()["registros_preenchidos"] == 1


def test_dependencias_e_arquivar(gestor, db):
    c = _interesse(gestor)
    funil = Funil(nome="Serviços B2B")
    db.add(funil)
    db.flush()
    etapa = Etapa(funil_id=funil.id, nome="Proposta", ordem=1, probabilidade=50)
    db.add(etapa)
    db.flush()
    db.add_all([
        IndicadorConfig(nome="Pipeline de alto interesse", metrica="soma_valor_unico", filtro_campo_id=c["id"],
                        filtro_valor="Alto"),
        Automacao(area="comercial", nome="Próxima ação prioritária", gatilho="campo_alterado", campo="interesse",
                  operador="igual", valor_esperado="Alto", acao="criar_atividade", conteudo="Ligar", estado="ativa"),
        Automacao(area="comercial", nome="Nutrição", gatilho="oportunidade_criada", acao="enviar_email",
                  conteudo="Seu interesse: {{ oportunidade.interesse }}", estado="rascunho"),
        Automacao(area="comercial", nome="Sem relação", gatilho="oportunidade_criada", acao="enviar_email",
                  conteudo="Olá {{contato.nome}}", estado="ativa"),
    ])
    db.commit()
    gestor.patch(f"/nucleo/campos/{c['id']}", {"exigido_na_etapa_id": etapa.id})

    r = gestor.get(f"/nucleo/campos/{c['id']}/dependencias")
    assert r.status_code == 200, r.text
    deps = r.json()
    assert deps["pode_arquivar"] is False
    assert {(d["tipo"], d["nome"], d["ativa"]) for d in deps["dependencias"]} == {
        ("dashboard", "Pipeline de alto interesse", True),
        ("automacao", "Próxima ação prioritária", True),
        ("automacao", "Nutrição", False),
        ("etapa", "Serviços B2B · Proposta", True),
    }
    assert gestor.get("/nucleo/campos").json()[0]["dependencias_ativas"] == 3

    r = gestor.post(f"/nucleo/campos/{c['id']}/arquivar", {})
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Campo em uso: Dashboard “Pipeline de alto interesse”; Automação")
    assert db.get(CampoCustom, c["id"]).arquivado is False

    r = gestor.post(f"/nucleo/campos/{c['id']}/arquivar", {"confirmar": True})
    assert r.status_code == 200 and r.json()["arquivado"] is True
    aud = db.query(Auditoria).filter_by(acao="campo_custom.arquivar").one()
    assert "confirmado com dependências" in aud.descricao
    assert gestor.get("/nucleo/campos").json() == []
    assert len(gestor.get("/nucleo/campos", params={"arquivados": True}).json()) == 1
    assert gestor.post(f"/nucleo/campos/{c['id']}/arquivar", {"confirmar": True}).json()["detail"] == \
        "Este campo já está arquivado."
    assert gestor.post(f"/nucleo/campos/{c['id']}/restaurar").json()["arquivado"] is False


def test_arquivar_sem_dependencia(gestor):
    c = gestor.post("/nucleo/campos", {"nome": "Apelido", "tipo": "texto", "objeto": "pessoa"}).json()
    deps = gestor.get(f"/nucleo/campos/{c['id']}/dependencias").json()
    assert deps["pode_arquivar"] is True and deps["dependencias"] == []
    assert gestor.post(f"/nucleo/campos/{c['id']}/arquivar", {}).json()["arquivado"] is True
    # campo arquivado não aceita valor novo
    r = gestor.post("/nucleo/pessoas", {"nome": "P", "campos_custom": {"apelido": "x"}})
    assert r.status_code == 400 and "desconhecido" in r.json()["detail"]


def test_etapas_para_campos(gestor, db):
    funil = Funil(nome="Serviços B2B")
    db.add(funil)
    db.flush()
    db.add(Etapa(funil_id=funil.id, nome="Entrada", ordem=1, probabilidade=10))
    db.commit()
    assert gestor.get("/nucleo/campos/etapas").json() == [{"id": 1, "nome": "Entrada", "funil_id": funil.id,
                                                          "funil_nome": "Serviços B2B", "ordem": 1}]


def test_404_e_403(gestor, leitura, comercial, financeiro):
    assert gestor.get("/nucleo/campos/9").status_code == 404
    assert gestor.get("/nucleo/campos/9/dependencias").status_code == 404
    assert gestor.post("/nucleo/campos/9/arquivar", {}).status_code == 404
    assert gestor.patch("/nucleo/campos/9", {"nome": "x"}).status_code == 404
    assert leitura.get("/nucleo/campos").status_code == 200
    novo = {"nome": "X", "tipo": "texto", "objeto": "empresa"}
    assert leitura.post("/nucleo/campos", novo).status_code == 403
    assert comercial.post("/nucleo/campos", novo).status_code == 403  # Comercial e Financeiro só veem o catálogo
    assert financeiro.post("/nucleo/campos", novo).status_code == 403
    c = gestor.post("/nucleo/campos", novo).json()
    assert leitura.post(f"/nucleo/campos/{c['id']}/arquivar", {}).status_code == 403
