"""Cobranças: modelos do Financeiro, prévia e ✉ Enviar e-mail (contrato de envio 11/2026). Nada sai da máquina:
a fixture `emails` captura o envio do core."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.models import Auditoria
from app.modules.comercial.models import ModeloComunicacao
from app.modules.financeiro.models import Cobranca
from app.modules.nucleo.models import Pessoa
from tests.financeiro.conftest import novo_titulo

C = "/api/financeiro/cobrancas"
EMAIL = {"para": ["financeiro@pontonorte.demo"], "assunto": "Título em aberto",
         "corpo": "Olá! O título segue em aberto."}


def _modelos(db):
    ms = {c: ModeloComunicacao(nome=f"Modelo {c}", canal="email", finalidade="cobranca", classificacao=c,
                               assunto="{{empresa.nome}}: {{titulo.descricao}}",
                               conteudo="Olá, {{contato.nome}}. Saldo {{titulo.valor}} vence {{titulo.vencimento}}. "
                                        "{{oportunidade.titulo}}")
          for c in ("comercial", "financeiro", "geral")}
    ms["inativo"] = ModeloComunicacao(nome="A inativo", canal="email", finalidade="cobranca", classificacao="geral",
                                      conteudo="x", ativo=False)
    ms["zap"] = ModeloComunicacao(nome="B WhatsApp", canal="whatsapp", finalidade="cobranca",
                                  classificacao="financeiro", conteudo="Oi")
    db.add_all(ms.values())
    db.commit()
    return ms


def _cobranca(client, cen):
    t = novo_titulo(client, cen, valor="6000", vencimento=cen.hoje - timedelta(days=7), descricao="Consultoria 1/2")
    r = client.post(C, headers=cen.h_fin, json={"assunto": "Lembrete", "titulo_id": t["id"],
                                                "responsavel_id": cen.fin_id, "canal": "email",
                                                "historico": "Cliente pediu boleto atualizado."})
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------------------------------- modelos
def test_financeiro_lista_modelos_financeiro_e_geral(client, db, cen):
    _modelos(db)
    r = client.get(f"{C}/modelos", headers=cen.h_fin)
    assert r.status_code == 200
    assert [m["nome"] for m in r.json()] == ["B WhatsApp", "Modelo financeiro", "Modelo geral"]
    assert r.json()[1]["variaveis"] and r.json()[1]["classificacao"] == "financeiro"
    r = client.get(f"{C}/modelos", params={"canal": "email"}, headers=cen.h_fin)
    assert [m["nome"] for m in r.json()] == ["Modelo financeiro", "Modelo geral"]
    assert client.get(f"{C}/modelos", params={"canal": "fax"}, headers=cen.h_fin).status_code == 422
    assert client.get(f"{C}/modelos", headers=cen.h_leitura).status_code == 200
    # o motivo da rota nova: o perfil Financeiro não lê os modelos do Comercial
    assert client.get("/api/comercial/modelos", headers=cen.h_fin).status_code == 403


def test_previa_preenche_com_os_dados_da_cobranca(client, db, cen):
    ms = _modelos(db)
    db.add(Pessoa(nome="Joana Lima", empresa_id=cen.cliente.id))
    db.commit()
    cob = _cobranca(client, cen)
    r = client.post(f"{C}/{cob['id']}/modelos/{ms['financeiro'].id}/previa", headers=cen.h_fin)
    assert r.status_code == 200, r.text
    p = r.json()
    venc = (cen.hoje - timedelta(days=7)).strftime("%d/%m/%Y")
    assert p["assunto"] == "Ponto Norte: Consultoria 1/2"
    assert p["conteudo"] == f"Olá, Joana Lima. Saldo R$ 6.000,00 vence {venc}. {{{{oportunidade.titulo}}}}"
    assert p["faltando"] == ["oportunidade.titulo"]
    # leitura pode ver a prévia (não grava nada)
    assert client.post(f"{C}/{cob['id']}/modelos/{ms['geral'].id}/previa", headers=cen.h_leitura).status_code == 200


def test_previa_404(client, db, cen):
    ms = _modelos(db)
    cob = _cobranca(client, cen)
    r = client.post(f"{C}/{cob['id']}/modelos/{ms['comercial'].id}/previa", headers=cen.h_fin)
    assert r.status_code == 404 and r.json()["detail"] == "Modelo não encontrado."
    assert client.post(f"{C}/{cob['id']}/modelos/9999/previa", headers=cen.h_fin).status_code == 404
    r = client.post(f"{C}/9999/modelos/{ms['financeiro'].id}/previa", headers=cen.h_fin)
    assert r.status_code == 404 and r.json()["detail"] == "Cobrança não encontrada."


# ------------------------------------------------------------------------------------------- enviar e-mail
def test_enviar_email_acrescenta_historico_e_audita(client, db, cen, emails):
    ms = _modelos(db)
    cob = _cobranca(client, cen)
    r = client.post(f"{C}/{cob['id']}/enviar-email", headers=cen.h_fin,
                    json={**EMAIL, "modelo_id": ms["financeiro"].id})
    assert r.status_code == 200, r.text
    linha = f"{cen.hoje:%d/%m/%Y} — E-mail enviado para financeiro@pontonorte.demo por Usuário Financeiro: Título em aberto"
    assert r.json() == {"ok": True, "enviado_para": ["financeiro@pontonorte.demo"],
                        "registro": f"Histórico da cobrança atualizado: {linha}"}
    assert emails == [(["financeiro@pontonorte.demo"], "Título em aberto", EMAIL["corpo"])]
    db.expire_all()
    assert db.get(Cobranca, cob["id"]).historico == f"Cliente pediu boleto atualizado.\n{linha}"
    a = db.scalar(select(Auditoria).where(Auditoria.acao == "cobranca.enviar_email"))
    assert a.antes_json == {"historico": "Cliente pediu boleto atualizado."} and a.depois_json["modelo_id"] == ms[
        "financeiro"].id
    assert client.get(f"{C}/{cob['id']}", headers=cen.h_fin).json()["historico"].endswith(linha)


def test_enviar_email_validacao_permissao_404_e_modelo_comercial(client, db, cen, emails):
    ms = _modelos(db)
    cob = _cobranca(client, cen)
    url = f"{C}/{cob['id']}/enviar-email"
    assert client.post(url, headers=cen.h_leitura, json=EMAIL).status_code == 403
    assert client.post(f"{C}/9999/enviar-email", headers=cen.h_fin, json=EMAIL).status_code == 404
    r = client.post(url, headers=cen.h_fin, json={**EMAIL, "corpo": "  "})
    assert r.status_code == 400 and "mensagem" in r.json()["detail"]
    r = client.post(url, headers=cen.h_fin, json={**EMAIL, "modelo_id": ms["comercial"].id})
    assert r.status_code == 404
    assert emails == []


def test_enviar_email_opt_out_e_sem_smtp(client, db, cen, emails, monkeypatch):
    db.add(Pessoa(nome="Joana Lima", empresa_id=cen.cliente.id, email="financeiro@pontonorte.demo",
                  permissoes_comunicacao=["opt_out"]))
    db.commit()
    cob = _cobranca(client, cen)
    url = f"{C}/{cob['id']}/enviar-email"
    r = client.post(url, headers=cen.h_fin, json=EMAIL)
    assert r.status_code == 400 and r.json()["detail"].startswith(
        "Joana Lima pediu para não receber comunicações (opt-out).")
    monkeypatch.setattr(settings, "ambiente", "prod")
    monkeypatch.setattr(settings, "smtp_host", None)
    r = client.post(url, headers=cen.h_fin, json={**EMAIL, "para": ["outra@pontonorte.demo"]})
    assert r.status_code == 400 and r.json()["detail"].startswith("Configure o e-mail de envio")
    db.expire_all()
    assert db.get(Cobranca, cob["id"]).historico == "Cliente pediu boleto atualizado." and emails == []
    assert Decimal(cob["titulo_saldo"]) == Decimal("6000")
