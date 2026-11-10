"""Defeitos provados pelo QA: alçada burlável por edição, Comercial vendo caixa/contas a pagar e o escopo
"só meus registros" ignorado em Hoje, baixas, cobranças, aprovações e recorrências."""

from datetime import date, timedelta

from sqlalchemy import select

from app.core.models import Auditoria, PerfilAcesso, Usuario
from app.core.permissoes import PERFIS_PADRAO
from app.core.security import hash_senha
from app.domain.dinheiro import somar_meses
from tests.conftest import SENHA, auth, criar_usuario, entrar
from tests.financeiro.conftest import baixa, novo_titulo

URL = "/api/financeiro/titulos"


# ---------------------------------------------------------------- 1. alçada
def test_editar_valor_de_pagar_aprovado_volta_para_pendente(client, db, cen):
    t = novo_titulo(client, cen, direcao="pagar", valor="100.00", responsavel_id=cen.fin_id)
    assert client.post(f"{URL}/{t['id']}/aprovar", headers=cen.h_admin).status_code == 200
    r = client.patch(f"{URL}/{t['id']}", json={"valor_original": "90000.00"}, headers=cen.h_fin)
    assert r.status_code == 200
    assert r.json()["aprovacao"] == "pendente" and r.json()["aprovado_por_nome"] is None
    r = baixa(client, cen, t["id"], "90000.00", headers=cen.h_fin)
    assert r.status_code == 400 and "aprova" in r.json()["detail"].lower()
    aud = db.scalars(select(Auditoria).where(Auditoria.acao == "titulo.editar")).all()[-1]
    assert "aprovacao" in (aud.antes_json or {}) and (aud.depois_json or {}).get("aprovacao") == "pendente"


def test_editar_empresa_ou_vencimento_de_pagar_aprovado_exige_nova_aprovacao(client, db, cen):
    for campo, valor in (("vencimento", str(cen.hoje + timedelta(days=5))), ("empresa_id", cen.cliente.id)):
        t = novo_titulo(client, cen, direcao="pagar")
        client.post(f"{URL}/{t['id']}/aprovar", headers=cen.h_admin)
        r = client.patch(f"{URL}/{t['id']}", json={campo: valor}, headers=cen.h_fin)
        assert r.status_code == 200 and r.json()["aprovacao"] == "pendente", campo


def test_editar_descricao_de_pagar_aprovado_mantem_aprovacao(client, cen):
    t = novo_titulo(client, cen, direcao="pagar", valor="100.00")
    client.post(f"{URL}/{t['id']}/aprovar", headers=cen.h_admin)
    r = client.patch(f"{URL}/{t['id']}", json={"descricao": "Aluguel de novembro", "valor_original": "100"},
                     headers=cen.h_fin)
    assert r.status_code == 200 and r.json()["aprovacao"] == "aprovado"


# ---------------------------------------------------------------- 2. Comercial não vê caixa nem contas a pagar
def _comercial(client, db):
    criar_usuario(db, "Comercial", email="com@exemplo.com")
    return auth(entrar(client, "com").json()["access_token"])


def test_comercial_no_hoje_financeiro_nao_ve_saldo_de_caixa(client, db, cen):
    h = _comercial(client, db)
    r = client.get("/api/financeiro/hoje", headers=h)
    assert r.status_code == 200
    assert r.json()["saldo_gerencial"] is None and r.json()["aprovacoes_pendentes"] is None
    r = client.get("/api/financeiro/hoje", headers=cen.h_fin).json()
    assert r["saldo_gerencial"]["valor"] == "26000.00" and r["aprovacoes_pendentes"] == 0


def test_comercial_nao_lista_nem_abre_contas_a_pagar(client, db, cen):
    pagar = novo_titulo(client, cen, direcao="pagar")
    receber = novo_titulo(client, cen)
    h = _comercial(client, db)
    r = client.get(URL, params={"direcao": "pagar"}, headers=h)
    assert r.status_code == 403 and "a pagar" in r.json()["detail"]
    assert client.get(f"{URL}/contagens", params={"direcao": "pagar"}, headers=h).status_code == 403
    assert [t["id"] for t in client.get(URL, headers=h).json()["itens"]] == [receber["id"]]
    assert client.get(f"{URL}/{pagar['id']}", headers=h).status_code == 404
    assert client.get(f"{URL}/{receber['id']}", headers=h).status_code == 200
    # quem tem Baixas ou Aprovações (Financeiro, Somente leitura) vê
    assert client.get(URL, params={"direcao": "pagar"}, headers=cen.h_fin).json()["total"] == 1
    assert client.get(URL, params={"direcao": "pagar"}, headers=cen.h_leitura).json()["total"] == 1


def test_opcoes_sem_caixa_nao_traz_contas_financeiras(client, db, cen):
    h = _comercial(client, db)
    r = client.get(f"{URL}/opcoes", headers=h)
    assert r.status_code == 200 and r.json()["contas"] == [] and r.json()["empresas"]
    assert len(client.get(f"{URL}/opcoes", headers=cen.h_fin).json()["contas"]) == 2


# ---------------------------------------------------------------- 3. só meus registros
def _restrito(client, db) -> tuple[dict, int]:
    """Usuário com as permissões do perfil Financeiro, mas restrito aos registros de que é responsável."""
    perms = next(p["permissoes"] for p in PERFIS_PADRAO if p["nome"] == "Financeiro")
    p = PerfilAcesso(nome="Financeiro restrito", permissoes=perms, somente_meus_registros=True)
    db.add(p)
    db.commit()
    u = Usuario(nome="Restrito", email="rest@exemplo.com", login="rest", perfil_acesso_id=p.id,
                senha_hash=hash_senha(SENHA))
    db.add(u)
    db.commit()
    return auth(entrar(client, "rest").json()["access_token"]), u.id


def test_hoje_restrito_so_ve_a_propria_fila_e_totais(client, db, cen):
    h, uid = _restrito(client, db)
    novo_titulo(client, cen, valor="5000", vencimento=cen.hoje - timedelta(days=10), descricao="Sigiloso")
    meu = novo_titulo(client, cen, valor="300", vencimento=cen.hoje - timedelta(days=3), responsavel_id=uid)
    novo_titulo(client, cen, direcao="pagar", valor="50")  # aprovação pendente de outro
    r = client.get("/api/financeiro/hoje", headers=h).json()
    assert [f["titulo_id"] for f in r["fila_cobranca"]] == [meu["id"]]
    assert r["recebiveis_vencidos"]["valor"] == "300.00" and r["recebiveis_vencidos_qtd"] == 1
    assert r["aprovacoes_pendentes"] == 0
    assert "Sigiloso" not in str(r["leitura"])


def test_baixas_restrito_lista_e_estorna_so_as_proprias(client, db, cen):
    h, uid = _restrito(client, db)
    outro = novo_titulo(client, cen)
    meu = novo_titulo(client, cen, responsavel_id=uid)
    b_outro = baixa(client, cen, outro["id"], "100").json()
    b_meu = baixa(client, cen, meu["id"], "100").json()
    r = client.get("/api/financeiro/baixas", headers=h).json()
    assert [b["id"] for b in r["itens"]] == [b_meu["id"]] and r["total"] == 1
    r = client.post(f"/api/financeiro/baixas/{b_outro['id']}/estornar", json={"motivo": "x"}, headers=h)
    assert r.status_code == 404
    r = client.post(f"/api/financeiro/baixas/{b_meu['id']}/estornar", json={"motivo": "erro"}, headers=h)
    assert r.status_code == 200


def _cob(client, cen, titulo_id, responsavel_id):
    return client.post("/api/financeiro/cobrancas", headers=cen.h_admin, json={
        "assunto": "Lembrete", "titulo_id": titulo_id, "responsavel_id": responsavel_id, "canal": "email",
        "historico": "Cliente pediu boleto."}).json()


def test_cobrancas_restrito_ve_so_as_proprias(client, db, cen):
    h, uid = _restrito(client, db)
    outro = novo_titulo(client, cen, vencimento=cen.hoje - timedelta(days=2))
    meu = novo_titulo(client, cen, vencimento=cen.hoje - timedelta(days=2), responsavel_id=uid)
    c_outro = _cob(client, cen, outro["id"], cen.admin_id)
    c_meu = _cob(client, cen, meu["id"], uid)
    assert [c["id"] for c in client.get("/api/financeiro/cobrancas", headers=h).json()] == [c_meu["id"]]
    assert client.get(f"/api/financeiro/cobrancas/{c_outro['id']}", headers=h).status_code == 404
    assert client.get(f"/api/financeiro/cobrancas/{c_meu['id']}", headers=h).status_code == 200


def test_aprovacoes_restrito_ve_so_as_proprias(client, db, cen):
    h, uid = _restrito(client, db)
    novo_titulo(client, cen, direcao="pagar")
    meu = novo_titulo(client, cen, direcao="pagar", responsavel_id=uid)
    assert [t["id"] for t in client.get("/api/financeiro/aprovacoes", headers=h).json()] == [meu["id"]]


def test_recorrencias_restrito_ve_so_as_proprias(client, db, cen):
    h, uid = _restrito(client, db)
    inicio = date(cen.hoje.year, cen.hoje.month, 1)

    def rec(resp):
        return client.post("/api/financeiro/recorrencias", headers=cen.h_admin, json={
            "descricao": "Mensalidade", "direcao": "receber", "empresa_id": cen.cliente.id, "valor_ciclo": "100",
            "frequencia": "mensal", "inicio": str(inicio), "fim": str(somar_meses(inicio, 11)), "dia_vencimento": 10,
            "responsavel_id": resp}).json()

    outra = rec(cen.admin_id)
    minha = rec(uid)
    assert [r["id"] for r in client.get("/api/financeiro/recorrencias", headers=h).json()] == [minha["id"]]
    assert client.get(f"/api/financeiro/recorrencias/{outra['id']}", headers=h).status_code == 404
    assert client.get("/api/financeiro/hoje", headers=h).json()["recorrencias_ativas"] == 1
