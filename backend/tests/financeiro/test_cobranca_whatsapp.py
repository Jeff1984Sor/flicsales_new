"""Cobranças: WhatsApp pela Evolution (contrato proposta + WhatsApp 11/2026, parte B3). A Evolution é FALSA
(tests/evolution_falsa.py): nada sai da máquina."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.models import Auditoria
from app.modules.comercial.models import ModeloComunicacao
from app.modules.financeiro.models import Cobranca
from app.modules.nucleo.models import Pessoa
from tests import evolution_falsa as ef
from tests.financeiro.conftest import novo_titulo

C = "/api/financeiro/cobrancas"
ZAP = {"para": ["(11) 98888-1234"], "texto": "Olá! O título segue em aberto."}


@pytest.fixture
def evo():
    with ef.instalada() as f:
        yield f


def _cobranca(client, cen):
    t = novo_titulo(client, cen, valor="6000", vencimento=cen.hoje - timedelta(days=7), descricao="Consultoria 1/2")
    r = client.post(C, headers=cen.h_fin, json={"assunto": "Lembrete", "titulo_id": t["id"],
                                                "responsavel_id": cen.fin_id, "canal": "whatsapp",
                                                "historico": "Cliente pediu boleto atualizado."})
    assert r.status_code == 201, r.text
    return r.json()


def test_enviar_whatsapp_acrescenta_historico_e_audita(client, db, cen, evo):
    ef.conectar(db)
    modelo = ModeloComunicacao(nome="Zap", canal="whatsapp", finalidade="cobranca", classificacao="financeiro",
                               conteudo="Oi")
    db.add(modelo)
    db.commit()
    cob = _cobranca(client, cen)
    r = client.post(f"{C}/{cob['id']}/enviar-whatsapp", headers=cen.h_fin, json={**ZAP, "modelo_id": modelo.id})
    assert r.status_code == 200, r.text
    linha = f"{cen.hoje:%d/%m/%Y} — WhatsApp enviado para +55 (11) 98888-1234 por Usuário Financeiro"
    assert r.json() == {"ok": True, "enviado_para": ["5511988881234"],
                        "registro": f"Histórico da cobrança atualizado: {linha}"}
    assert evo.enviados == [{"number": "5511988881234", "text": f"{ZAP['texto']}\n\n— Usuário Financeiro"}]
    db.expire_all()
    assert db.get(Cobranca, cob["id"]).historico == f"Cliente pediu boleto atualizado.\n{linha}"
    a = db.scalar(select(Auditoria).where(Auditoria.acao == "cobranca.enviar_whatsapp"))
    assert a.antes_json == {"historico": "Cliente pediu boleto atualizado."} and a.depois_json["modelo_id"] == modelo.id
    assert ef.CHAVE not in str(a.depois_json) + str(a.descricao)


def test_validacao_permissao_404_opt_out_e_sem_whatsapp(client, db, cen, evo):
    cob = _cobranca(client, cen)
    url = f"{C}/{cob['id']}/enviar-whatsapp"
    r = client.post(url, headers=cen.h_fin, json=ZAP)
    assert r.status_code == 400 and r.json()["detail"] == "Configure o WhatsApp em Núcleo › Integrações."
    ef.conectar(db)
    assert client.post(url, headers=cen.h_leitura, json=ZAP).status_code == 403
    assert client.post(f"{C}/9999/enviar-whatsapp", headers=cen.h_fin, json=ZAP).status_code == 404
    r = client.post(url, headers=cen.h_fin, json={**ZAP, "texto": "  "})
    assert r.status_code == 400 and "Escreva a mensagem" in r.json()["detail"]
    r = client.post(url, headers=cen.h_fin, json={**ZAP, "para": ["abc"]})
    assert r.status_code == 400 and "Telefone inválido" in r.json()["detail"]
    db.add(Pessoa(nome="Joana Lima", empresa_id=cen.cliente.id, telefone="11 98888-1234",
                  permissoes_comunicacao=["opt_out"]))
    db.commit()
    r = client.post(url, headers=cen.h_fin, json=ZAP)
    assert r.status_code == 400 and r.json()["detail"].startswith(
        "Joana Lima pediu para não receber comunicações (opt-out).")
    db.expire_all()
    assert db.get(Cobranca, cob["id"]).historico == "Cliente pediu boleto atualizado." and evo.enviados == []
