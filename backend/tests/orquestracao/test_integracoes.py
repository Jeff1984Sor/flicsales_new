"""Integrações: cards, segredo cifrado somente escrita, Testar conexão (sem chamada externa), revogar, permissões."""

from sqlalchemy import select

from app.core.models import Auditoria, ConfigEmail
from app.modules.orquestracao.models import Automacao, Integracao

URL = "/api/orquestracao/integracoes"
TOKEN = "EAAG-token-oficial-de-teste-1234ABCD"


def test_lista_os_quatro_cards_com_requisitos(client, comercial):
    r = client.get(URL, headers=comercial)
    assert r.status_code == 200
    cards = r.json()
    assert [c["nome"] for c in cards] == ["Google Calendar", "Microsoft Outlook", "E-mail", "WhatsApp"]
    assert all(c["situacao"] == "desconectado" and c["requisitos"] for c in cards)
    assert cards[3]["descricao"] == "API do WhatsApp no seu servidor (Evolution)"


def test_segredo_e_somente_escrita_e_auditado_sem_valor(client, gestor, db):
    r = client.put(f"{URL}/whatsapp", json={"conta": "+55 11 99999-0000", "escopos": ["Enviar mensagens com modelo aprovado"],
                                            "segredo": TOKEN}, headers=gestor)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["segredo_definido"] is True and d["segredo_final"] == "ABCD" and TOKEN not in r.text
    i = db.scalar(select(Integracao).where(Integracao.tipo == "whatsapp"))
    assert i.segredo_cifrado and TOKEN.encode() not in i.segredo_cifrado
    aud = db.scalar(select(Auditoria).where(Auditoria.acao == "integracao.configurar"))
    assert TOKEN not in str(aud.antes_json) + str(aud.depois_json) + str(aud.descricao)
    # em branco = mantém o segredo
    r = client.put(f"{URL}/whatsapp", json={"conta": "+55 11 98888-0000"}, headers=gestor)
    assert r.json()["segredo_final"] == "ABCD"


def test_testar_whatsapp_valida_formato_e_aguarda_conector(client, gestor):
    r = client.post(f"{URL}/whatsapp/testar", headers=gestor)
    assert r.status_code == 200 and r.json()["integracao"]["situacao"] == "erro"
    assert r.json()["integracao"]["ultimo_erro"].startswith("Informe o número")
    client.put(f"{URL}/whatsapp", json={"conta": "+55 11 99999-0000", "escopos": ["Receber respostas"], "segredo": "curto"},
               headers=gestor)
    r = client.post(f"{URL}/whatsapp/testar", headers=gestor)
    assert "incompleto" in r.json()["integracao"]["ultimo_erro"]
    client.put(f"{URL}/whatsapp", json={"segredo": TOKEN}, headers=gestor)
    r = client.post(f"{URL}/whatsapp/testar", headers=gestor).json()
    assert r["integracao"]["situacao"] == "aguardando_conector" and r["integracao"]["ultimo_erro"] is None
    assert "nenhuma chamada externa" in r["mensagem"]
    assert r["integracao"]["estado"] == "desconectado"  # ainda não ativa envios


def test_testar_google_exige_email(client, gestor):
    client.put(f"{URL}/google_calendar", json={"conta": "sem-arroba", "escopos": ["Ler eventos (calendar.readonly)"],
                                               "segredo": TOKEN}, headers=gestor)
    assert client.post(f"{URL}/google_calendar/testar", headers=gestor).json()["integracao"]["situacao"] == "erro"
    client.put(f"{URL}/google_calendar", json={"conta": "agenda@flicsales.demo"}, headers=gestor)
    assert client.post(f"{URL}/google_calendar/testar", headers=gestor).json()["integracao"]["situacao"] == \
        "aguardando_conector"


def test_email_usa_o_smtp_do_core(client, gestor, db, emails):
    r = client.post(f"{URL}/email/testar", headers=gestor).json()
    assert r["integracao"]["situacao"] == "erro" and "SMTP não configurado" in r["integracao"]["ultimo_erro"]
    cfg = db.get(ConfigEmail, 1)
    cfg.smtp_host, cfg.remetente_email = "smtp.flicsales.demo", "contato@flicsales.demo"
    db.commit()
    r = client.post(f"{URL}/email/testar", headers=gestor).json()
    assert r["integracao"]["situacao"] == "conectado" and r["integracao"]["conta"] == "contato@flicsales.demo"
    assert emails and emails[0][1] == "Teste da integração de e-mail"


def test_revogar_apaga_segredo_e_pausa_envios(client, gestor, db):
    client.put(f"{URL}/whatsapp", json={"conta": "+55 11 99999-0000", "escopos": ["Receber respostas"], "segredo": TOKEN},
               headers=gestor)
    i = db.scalar(select(Integracao).where(Integracao.tipo == "whatsapp"))
    i.estado = "conectado"
    a = Automacao(area="financeiro", nome="Cobrança", gatilho="titulo_vencido", acao="enviar_whatsapp",
                  destinatario="contato_principal", conteudo="Olá", estado="ativa")
    db.add(a)
    db.commit()
    assert "Cobrança (ativa)" in client.get(f"{URL}/whatsapp", headers=gestor).json()["fluxos_dependentes"]
    r = client.post(f"{URL}/whatsapp/revogar", headers=gestor)
    assert r.status_code == 200 and "pausadas" in r.json()["mensagem"]
    assert r.json()["integracao"]["segredo_definido"] is False and r.json()["integracao"]["situacao"] == "desconectado"
    db.refresh(a)
    assert a.estado == "pausada"
    assert db.scalar(select(Auditoria).where(Auditoria.acao == "integracao.revogar"))


def test_permissoes_e_404(client, comercial, financeiro, gestor):
    assert client.put(f"{URL}/whatsapp", json={"conta": "x"}, headers=comercial).status_code == 403
    assert client.post(f"{URL}/email/testar", headers=financeiro).status_code == 403
    assert client.post(f"{URL}/whatsapp/revogar", headers=comercial).status_code == 403
    assert client.get(f"{URL}/telegram", headers=gestor).status_code == 404
    assert client.put(f"{URL}/telegram", json={}, headers=gestor).status_code == 404
    assert client.post(f"{URL}/whatsapp/revogar", headers=gestor).status_code == 404  # nunca configurada
    r = client.put(f"{URL}/whatsapp", json={"escopos": ["Ler tudo"]}, headers=gestor)
    assert r.status_code == 400
