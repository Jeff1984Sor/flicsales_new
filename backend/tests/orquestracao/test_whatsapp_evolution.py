"""WhatsApp pela Evolution API (contrato proposta + WhatsApp 11/2026, parte B1): configuração somente escrita,
instâncias, testar, QR code, notificador do core (código de senha), /auth/me/envio e automações. A Evolution é FALSA
(httpx.MockTransport em tests/evolution_falsa.py): nenhum teste chama a rede."""

import logging
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core import notificador
from app.core.db import hoje
from app.core.models import Auditoria
from app.modules.comercial.models import Comunicacao
from app.modules.nucleo.models import Pessoa
from app.modules.orquestracao import evolution, motor
from app.modules.orquestracao.models import Automacao, AutomacaoExecucao, Integracao
from tests import evolution_falsa as ef
from tests.conftest import criar_usuario

URL = "/api/orquestracao/integracoes/whatsapp/evolution"


@pytest.fixture
def evo():
    with ef.instalada() as f:
        yield f


def _salvar(client, cab, **kw):
    return client.put(URL, headers=cab, json={"url": ef.URL + "/", "apikey": ef.CHAVE, "instancia": ef.INSTANCIA,
                                              **kw})


def _sem_chave(*textos) -> bool:
    return all(ef.CHAVE not in str(t) for t in textos)


# ------------------------------------------------------------------------------------------------ cliente
def test_cliente_manda_apikey_e_formatos_da_v2(evo):
    c = evolution.Cliente(ef.URL, ef.CHAVE)
    assert c.instancias() == [{"nome": "flic", "estado": "conectado", "numero": ef.NUMERO},
                              {"nome": "outra", "estado": "desconectado", "numero": None}]
    assert c.estado("flic") == "open"
    c.enviar_texto("flic", "5511999990000", "Oi")
    c.enviar_documento("flic", "5511999990000", "Segue", "p.pdf", b"%PDF-1", "application/pdf")
    assert all(k == ef.CHAVE for _m, _p, k, _c in evo.pedidos)
    assert evo.enviados == [
        {"number": "5511999990000", "text": "Oi"},
        {"number": "5511999990000", "mediatype": "document", "mimetype": "application/pdf", "media": "JVBERi0x",
         "fileName": "p.pdf", "caption": "Segue"}]


def test_cliente_aceita_formato_v1_das_instancias():
    def v1(req):
        return httpx.Response(200, json=[{"instance": {"instanceName": "antiga", "status": "open",
                                                       "owner": "5521988887777@s.whatsapp.net"}}])
    evolution.definir_transporte(httpx.MockTransport(v1))
    try:
        assert evolution.Cliente(ef.URL, ef.CHAVE).instancias() == [
            {"nome": "antiga", "estado": "conectado", "numero": "5521988887777"}]
    finally:
        evolution.definir_transporte(None)


def test_erros_do_cliente_sao_curtos_e_sem_chave(evo):
    c = evolution.Cliente(ef.URL, "chave-errada-123")
    with pytest.raises(evolution.ErroEvolution) as e:
        c.estado("flic")
    assert e.value.mensagem == "a API key foi recusada pela Evolution" and "chave-errada" not in e.value.mensagem
    evo.status_tudo = 500
    with pytest.raises(evolution.ErroEvolution) as e:
        evolution.Cliente(ef.URL, ef.CHAVE).estado("flic")
    assert e.value.mensagem.startswith("a Evolution respondeu HTTP 500") and _sem_chave(e.value.mensagem)
    assert "••••" in e.value.mensagem  # a chave ecoada pelo servidor é mascarada
    evo.status_tudo, evo.erro_rede = None, httpx.ConnectTimeout
    with pytest.raises(evolution.ErroEvolution, match="não respondeu a tempo"):
        evolution.Cliente(ef.URL, ef.CHAVE).estado("flic")
    evo.erro_rede = httpx.ConnectError
    with pytest.raises(evolution.ErroEvolution, match="não foi possível conectar"):
        evolution.Cliente(ef.URL, ef.CHAVE).estado("flic")


# ------------------------------------------------------------------------------------------------ configuração
def test_get_sem_configuracao(client, gestor, comercial):
    r = client.get(URL, headers=comercial)  # ver: quem vê integrações
    assert r.status_code == 200
    assert r.json() == {"configurado": False, "provedor": None, "url": None, "instancia": None, "chave_final": None,
                        "estado": "desconectado", "numero": None, "testado_em": None, "ultimo_erro": None}


def test_salvar_chave_somente_escrita_e_auditoria_sem_chave(client, gestor, db, evo):
    r = _salvar(client, gestor)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["configurado"] is True and d["url"] == ef.URL and d["instancia"] == "flic" and d["provedor"] == "evolution"
    assert d["chave_final"] == "••••••XYZ9" and _sem_chave(r.text) and d["estado"] == "desconectado"
    i = db.scalar(select(Integracao).where(Integracao.tipo == "whatsapp"))
    assert ef.CHAVE.encode() not in i.segredo_cifrado
    aud = db.scalar(select(Auditoria).where(Auditoria.acao == "integracao.configurar"))
    assert _sem_chave(aud.antes_json, aud.depois_json, aud.descricao) and "API key alterada" in aud.descricao
    # apikey vazia/ausente = mantém
    r = client.put(URL, headers=gestor, json={"url": ef.URL, "apikey": ""})
    assert r.json()["chave_final"] == "••••••XYZ9" and r.json()["instancia"] == "flic"
    assert client.get(URL, headers=gestor).json()["configurado"] is True
    # a lista geral também mostra o card como Evolution
    card = next(c for c in client.get("/api/orquestracao/integracoes", headers=gestor).json() if c["tipo"] == "whatsapp")
    assert card["descricao"] == "API do WhatsApp no seu servidor (Evolution)" and _sem_chave(card)


def test_salvar_valida_url_instancia_e_chave(client, gestor):
    r = _salvar(client, gestor, url="evo.exemplo.test")
    assert r.status_code == 400 and "http:// ou https://" in r.json()["detail"]
    r = _salvar(client, gestor, instancia="nome/errado")
    assert r.status_code == 400 and "instância inválido" in r.json()["detail"]
    r = _salvar(client, gestor, apikey="curta")
    assert r.status_code == 400 and "incompleta" in r.json()["detail"]
    assert client.put(URL, headers=gestor, json={"apikey": ef.CHAVE}).status_code == 422  # url obrigatória


def test_buscar_instancias_com_formulario_ou_salvo(client, gestor, evo):
    r = client.post(f"{URL}/instancias", headers=gestor, json={"url": ef.URL, "apikey": ef.CHAVE})
    assert r.status_code == 200 and [x["nome"] for x in r.json()] == ["flic", "outra"]
    r = client.post(f"{URL}/instancias", headers=gestor)
    assert r.status_code == 400 and "Informe a URL e a API key" in r.json()["detail"]
    _salvar(client, gestor)
    assert client.post(f"{URL}/instancias", headers=gestor).json()[0]["numero"] == ef.NUMERO
    r = client.post(f"{URL}/instancias", headers=gestor, json={"apikey": "outra-chave-errada"})
    assert r.status_code == 400 and r.json()["detail"] == (
        "Não foi possível buscar as instâncias: a API key foi recusada pela Evolution.")


def test_testar_conectado_desconectado_e_erro_sem_chave(client, gestor, db, evo):
    r = client.post(f"{URL}/testar", headers=gestor)
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["estado"] == "erro"
    _salvar(client, gestor)
    r = client.post(f"{URL}/testar", headers=gestor)
    assert r.json() == {"ok": True, "estado": "conectado", "mensagem": f"WhatsApp conectado pelo número {ef.NUMERO}."}
    g = client.get(URL, headers=gestor).json()
    assert g["estado"] == "conectado" and g["numero"] == ef.NUMERO and g["testado_em"]
    evo.estado = "close"
    r = client.post(f"{URL}/testar", headers=gestor).json()
    assert r["ok"] is False and r["estado"] == "desconectado" and "QR code" in r["mensagem"]
    evo.status_tudo = 500
    r = client.post(f"{URL}/testar", headers=gestor)
    assert r.json()["estado"] == "erro" and _sem_chave(r.text)
    assert client.get(URL, headers=gestor).json()["ultimo_erro"].startswith("Não foi possível consultar a instância")
    auds = db.scalars(select(Auditoria).where(Auditoria.acao == "integracao.testar")).all()
    assert len(auds) == 4 and all(_sem_chave(a.antes_json, a.depois_json, a.descricao) for a in auds)
    # o "Testar conexão" genérico do card também usa a Evolution
    evo.status_tudo, evo.estado = None, "open"
    r = client.post("/api/orquestracao/integracoes/whatsapp/testar", headers=gestor).json()
    assert r["integracao"]["situacao"] == "conectado" and "WhatsApp conectado" in r["mensagem"]


def test_qrcode_conecta_e_cria_instancia_se_nao_existir(client, gestor, evo):
    r = client.post(f"{URL}/qrcode", headers=gestor)
    assert r.status_code == 400 and "Salve a URL e a API key" in r.json()["detail"]
    _salvar(client, gestor)
    r = client.post(f"{URL}/qrcode", headers=gestor)
    assert r.status_code == 200, r.text
    assert r.json()["base64"].startswith("data:image/png;base64,") and r.json()["codigo_pareamento"] == "WZYEH1YY"
    evo.instancia_existe = False
    r = client.post(f"{URL}/qrcode", headers=gestor)
    assert r.json()["codigo_pareamento"] == "NOVO1234"
    criar = next(c for m, p, _k, c in evo.pedidos if p == "/instance/create")
    assert criar == {"instanceName": "flic", "integration": "WHATSAPP-BAILEYS", "qrcode": True}
    evo.status_tudo = 401
    r = client.post(f"{URL}/qrcode", headers=gestor)
    assert r.status_code == 400 and r.json()["detail"].startswith("Não foi possível gerar o QR code") and _sem_chave(r.text)


def test_permissoes(client, comercial, financeiro, evo):
    assert client.put(URL, headers=comercial, json={"url": ef.URL, "apikey": ef.CHAVE}).status_code == 403
    assert client.post(f"{URL}/testar", headers=financeiro).status_code == 403
    assert client.post(f"{URL}/instancias", headers=comercial, json={}).status_code == 403
    assert client.post(f"{URL}/qrcode", headers=comercial).status_code == 403
    assert evo.pedidos == []


# ------------------------------------------------------------------------------------------------ core
def test_me_envio_mostra_whatsapp(client, gestor, comercial, db):
    r = client.get("/api/auth/me/envio", headers=comercial).json()
    assert r["whatsapp"] == {"pode_enviar": False, "numero": None}
    ef.conectar(db)
    r = client.get("/api/auth/me/envio", headers=comercial).json()
    assert r["whatsapp"] == {"pode_enviar": True, "numero": ef.NUMERO}
    ef.conectar(db, estado="desconectado")
    assert client.get("/api/auth/me/envio", headers=comercial).json()["whatsapp"]["pode_enviar"] is False


def test_notificador_evolution_envia_o_codigo_de_senha(client, db, evo, caplog):
    assert isinstance(notificador.get_notificador(), evolution.NotificadorEvolution)
    criar_usuario(db, "Financeiro", email="rec@exemplo.com", telefone="(11) 98888-7777")
    caplog.set_level(logging.INFO)
    client.post("/api/auth/forgot-codigo", json={"identificador": "rec"})
    assert evo.enviados == []  # sem WhatsApp conectado: nada sai (e o fluxo não quebra)
    ef.conectar(db)
    r = client.post("/api/auth/forgot-codigo", json={"identificador": "rec"})
    assert r.status_code == 200
    assert evo.enviados[0]["number"] == "5511988887777" and "código para redefinir a senha" in evo.enviados[0]["text"]
    evo.status_envio = 400
    client.post("/api/auth/forgot-codigo", json={"identificador": "rec"})
    assert _sem_chave(caplog.text) and "código para redefinir" not in caplog.text


# ------------------------------------------------------------------------------------------------ automações
def _automacao(db, destinatario="contato_principal"):
    a = Automacao(area="financeiro", nome="Cobrança zap", gatilho="titulo_vencido", acao="enviar_whatsapp",
                  destinatario=destinatario, conteudo="Olá, {{titulo.valor}} vencido", estado="ativa",
                  prazo_dias=0)
    db.add(a)
    db.commit()
    return a


def _contato_da_empresa_vencida(db) -> Pessoa:
    """O seed tem um título vencido (R$ 6.000,00); o contato principal da empresa dele recebe o WhatsApp."""
    from app.modules.financeiro.models import Titulo

    t = db.scalar(select(Titulo).where(Titulo.direcao == "receber", Titulo.status.in_(("aberto", "parcial")),
                                       Titulo.vencimento < hoje()).order_by(Titulo.vencimento))
    p = db.scalar(select(Pessoa).where(Pessoa.empresa_id == t.empresa_id, Pessoa.ativo.is_(True)).order_by(Pessoa.id))
    if p is None:
        p = Pessoa(nome="Contato Cobrança", empresa_id=t.empresa_id)
        db.add(p)
    p.telefones = [{"numero": "(11) 97777-6666", "tipo": "whatsapp", "principal": True}]
    db.commit()
    return p


def test_automacao_sem_conexao_fica_pendente(db, demo, evo):
    _automacao(db)
    assert motor.executar(db, hoje()) == {"pendente_conector": 1}
    assert evo.pedidos == []


def test_automacao_envia_quando_conectado(db, demo, evo):
    p = _contato_da_empresa_vencida(db)
    ef.conectar(db)
    _automacao(db)
    assert motor.executar(db, hoje()) == {"executada": 1}
    assert evo.enviados == [{"number": "5511977776666", "text": "Olá, R$ 6.000,00 vencido"}]
    ex = db.scalar(select(AutomacaoExecucao))
    assert ex.registro_criado.startswith("comunicacao:") and p.nome in ex.detalhe
    c = db.get(Comunicacao, int(ex.registro_criado.split(":")[1]))
    assert c.canal == "whatsapp" and c.conteudo.startswith("Para: +55 (11) 97777-6666")
    assert motor.executar(db, hoje()) == {"repetida": 1}  # idempotente: não manda de novo
    assert len(evo.enviados) == 1


def test_automacao_pula_opt_out(db, demo, evo):
    p = _contato_da_empresa_vencida(db)
    p.permissoes_comunicacao = ["opt_out"]
    db.commit()
    ef.conectar(db)
    _automacao(db)
    assert motor.executar(db, hoje()) == {"ignorada": 1}
    assert evo.enviados == []
    assert "opt-out" in db.scalar(select(AutomacaoExecucao)).detalhe


def test_automacao_falha_de_envio_vira_historico_sem_chave(db, demo, evo):
    _contato_da_empresa_vencida(db)
    ef.conectar(db)
    evo.status_envio = 400
    _automacao(db)
    assert motor.executar(db, hoje()) == {"falhou": 1}
    ex = db.scalar(select(AutomacaoExecucao))
    assert ex.erro.startswith("Não foi possível enviar pelo WhatsApp") and _sem_chave(ex.erro)
    assert db.scalar(select(Comunicacao).where(Comunicacao.canal == "whatsapp",
                                               Comunicacao.data >= hoje() - timedelta(days=1))) is None
