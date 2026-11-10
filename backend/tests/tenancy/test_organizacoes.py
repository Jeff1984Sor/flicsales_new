"""Um banco por organização: identificação (host, catálogo), isolamento de dados e arquivos, status, worker,
provisionamento e catálogo de logins."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import tenancy
from app.core.auth_service import MSG_LOGIN
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.models import Usuario
from tests.conftest import SENHA
from tests.tenancy.conftest import HOST_ALFA, HOST_BETA, bearer, controle_proprio, entrar


def _logins(slug: str) -> set[str]:
    from app.controle.models import Login, OrganizacaoCliente, SessaoControle

    with SessaoControle() as db:
        return set(db.scalars(select(Login.chave).join(OrganizacaoCliente).where(OrganizacaoCliente.slug == slug)))


def test_sem_controle_e_um_banco_so():
    assert tenancy.multi() is False
    assert tenancy.claims() == {}
    assert tenancy.pasta_base() == Path(settings.storage_dir)


def test_login_pelo_endereco_e_dados_isolados(multi, client):
    alfa = bearer(entrar(client, "ana", host=HOST_ALFA))
    beta = bearer(entrar(client, "ana", host=HOST_BETA))
    me_a = client.get("/api/auth/me", headers=alfa).json()
    me_b = client.get("/api/auth/me", headers=beta).json()
    assert (me_a["nome"], me_a["organizacao"]["slug"], me_a["organizacao"]["nome"]) == ("Ana Alfa", "alfa", "Organização Alfa")
    assert (me_b["nome"], me_b["organizacao"]["status"]) == ("Ana Beta", "ativo")

    # o que uma organização cadastra a outra não vê (os ids até coincidem: são bancos diferentes)
    r = client.post("/api/config/usuarios", headers=alfa, json={
        "nome": "Exclusivo Alfa", "email": "exclusivo@alfa.com", "login": "exclusivo", "perfil_acesso_id":
        me_a["perfil_acesso_id"], "acesso_sistema": False})
    assert r.status_code == 201, r.text
    nomes = lambda h: {u["nome"] for u in client.get("/api/config/usuarios", headers=h).json()}  # noqa: E731
    assert "Exclusivo Alfa" in nomes(alfa) and "Exclusivo Alfa" not in nomes(beta)

    # a marca pública sai do banco do endereço
    assert client.get("/api/public/identidade", headers={"Host": HOST_ALFA}).json()["nome_exibicao"] == "Organização Alfa"
    assert client.get("/api/public/identidade", headers={"X-Forwarded-Host": HOST_BETA}).json()["nome_exibicao"] == "Organização Beta"
    # no endereço da organização só valem os logins dela
    assert entrar(client, "carlos", host=HOST_BETA).status_code == 401


def test_login_pelo_catalogo_e_login_ambiguo(multi, client):
    carlos = bearer(entrar(client, "carlos"))  # sem endereço: o catálogo diz que é da alfa
    assert client.get("/api/auth/me", headers=carlos).json()["organizacao"]["slug"] == "alfa"
    assert client.get("/api/auth/me", headers=bearer(entrar(client, "BIA"))).json()["organizacao"]["slug"] == "beta"
    # "ana" existe nas duas: no endereço principal falha com a MESMA mensagem de senha errada (não revela nada)
    ambiguo = entrar(client, "ana")
    errado = entrar(client, "carlos", senha="Errada@123")
    inexistente = entrar(client, "ninguem")
    assert ambiguo.status_code == errado.status_code == inexistente.status_code == 401
    assert ambiguo.json()["detail"] == errado.json()["detail"] == inexistente.json()["detail"] == MSG_LOGIN


def test_token_de_uma_organizacao_nao_serve_na_outra(multi, client):
    alfa = bearer(entrar(client, "ana", host=HOST_ALFA))
    # o token manda: no endereço da beta, o token da alfa continua vendo SÓ a alfa
    me = client.get("/api/auth/me", headers={**alfa, "X-Forwarded-Host": HOST_BETA}).json()
    assert me["organizacao"]["slug"] == "alfa" and me["nome"] == "Ana Alfa"
    # sem token nem endereço de organização, nenhuma rota abre banco
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalido"}).status_code == 401
    assert client.get("/api/public/identidade").status_code == 401
    # host desconhecido nem chega à API
    assert client.get("/api/health", headers={"Host": "intruso.exemplo.com"}).status_code == 400


def test_organizacao_inativa_nao_entra_e_suspensa_entra(multi, client):
    beta = bearer(entrar(client, "bia"))
    try:
        multi.definir_status("beta", "inativo")
        assert client.get("/api/auth/me", headers=beta).status_code == 401
        assert entrar(client, "bia").status_code == 401
        assert entrar(client, "bia", host=HOST_BETA).status_code == 401
        # no endereço da inativa, "ana" não cai no catálogo (que acharia a ana da alfa)
        assert entrar(client, "ana", host=HOST_BETA).status_code == 401
        assert entrar(client, "ana").status_code == 200  # no endereço principal: agora só a alfa tem "ana"
        multi.definir_status("beta", "suspenso")
        assert client.get("/api/auth/me", headers=bearer(entrar(client, "bia"))).json()["organizacao"]["status"] == "suspenso"
    finally:
        multi.definir_status("beta", "ativo")


def test_arquivos_separados_por_organizacao(multi):
    from app.core import storage

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    with tenancy.usando(multi.por_slug("alfa")):
        assert storage.raiz() == (Path(settings.storage_dir) / "organizacoes" / "alfa").resolve()
        rel = storage.salvar("usuarios", "foto.png", png)
        assert storage.existe(rel)
    with tenancy.usando(multi.por_slug("beta")):
        assert storage.raiz() == (Path(settings.storage_dir) / "organizacoes" / "beta").resolve()
        assert not storage.existe(rel)


def test_worker_roda_cada_tarefa_em_cada_organizacao(multi):
    from app import worker

    vistos, globais = [], []
    worker.registrar_tarefa("teste-por-org", 60, lambda: vistos.append(tenancy.atual().slug))
    worker.registrar_tarefa("teste-global", 60, lambda: globais.append(tenancy.atual()), global_=True)
    try:
        feitas = worker.executar_pendentes(agora_s=1e9)
        assert sorted(vistos) == ["alfa", "beta"] and globais == [None]
        assert {"teste-por-org@alfa", "teste-por-org@beta", "teste-global"} <= set(feitas)
        worker.executar_pendentes(agora_s=1e9 + 1)  # ninguém venceu de novo
        assert len(vistos) == 2 and len(globais) == 1
        # organização inativa sai da volta seguinte
        multi.definir_status("beta", "inativo")
        worker.executar_pendentes(agora_s=1e9 + 120)
        assert sorted(vistos) == ["alfa", "alfa", "beta"]
    finally:
        multi.definir_status("beta", "ativo")
        worker.TAREFAS[:] = [t for t in worker.TAREFAS if not t.nome.startswith("teste-")]


def test_provisionar_com_convite_e_dominio_padrao(multi, client, monkeypatch, emails):
    monkeypatch.setattr(settings, "dominio_base", "flicsales.test")
    org, link = multi.provisionar("gama", "Organização Gama", admin_email="dono@gama.com", admin_login="dono")
    assert org.status == "ativo" and link.startswith("http://gama.flicsales.test:3000/redefinir-senha?token=gama.")
    assert multi.por_host("gama.flicsales.test") == multi.por_slug("gama")  # subdomínio padrão entrou sozinho
    with tenancy.usando(multi.por_slug("gama")), SessionLocal() as db:
        dono = db.scalar(select(Usuario).where(Usuario.login == "dono"))
        assert dono.administrador and dono.convite_pendente and dono.senha_hash is None
    assert "dono" in _logins("gama")
    token = link.split("token=")[1]
    assert client.post("/api/auth/reset", json={"token": token, "senha": SENHA}).status_code == 200
    assert client.get("/api/auth/me", headers=bearer(entrar(client, "dono"))).json()["organizacao"]["slug"] == "gama"


def test_provisionar_com_erro_nao_deixa_organizacao_pela_metade(multi, monkeypatch):
    def quebra(_org):
        raise RuntimeError("falhou a migration")

    monkeypatch.setattr(multi, "migrar", quebra)
    with pytest.raises(RuntimeError):
        multi.provisionar("delta", "Org Delta", admin_email="x@delta.com", admin_login="xdelta", admin_senha=SENHA)
    from app.controle.models import OrganizacaoCliente, SessaoControle

    with SessaoControle() as db:
        assert db.scalar(select(OrganizacaoCliente.id).where(OrganizacaoCliente.slug == "delta")) is None
    with pytest.raises(multi.RegraControle):
        multi.provisionar("Delta X", "x", admin_email="x@delta.com", admin_login="xdelta")
    with pytest.raises(multi.RegraControle, match="reservado"):
        multi.provisionar("admin", "x", admin_email="x@delta.com", admin_login="xdelta")


def test_convite_e_reset_por_link_levam_a_organizacao(multi, client, emails):
    assert client.post("/api/auth/forgot", json={"identificador": "carlos"}).status_code == 200
    (para, _, corpo), = emails
    token = corpo.split("token=")[1].split()[0]
    assert para == ["carlos@alfa.com"] and token.startswith("alfa.")
    assert f"http://{HOST_ALFA}:3000/redefinir-senha?token=" in corpo  # o link abre no endereço da organização
    # o link funciona no endereço principal: a organização vem do próprio token
    assert client.post("/api/auth/reset", json={"token": token, "senha": "Nova@Senha9"}).status_code == 200
    assert client.get("/api/auth/me", headers=bearer(entrar(client, "carlos", "Nova@Senha9"))).status_code == 200
    with tenancy.usando(multi.por_slug("alfa")), SessionLocal() as db:
        from app.core.security import hash_senha

        db.scalar(select(Usuario).where(Usuario.login == "carlos")).senha_hash = hash_senha(SENHA)
        db.commit()


def test_refresh_acha_a_organizacao_pelo_token(multi, client):
    r = entrar(client, "bia")
    novo = client.post("/api/auth/refresh", json={"refresh_token": r.json()["refresh_token"]})
    assert novo.status_code == 200 and novo.json()["usuario"]["organizacao"]["slug"] == "beta"


def test_sincronia_do_catalogo(multi):
    from app.core import perfis

    org = multi.por_slug("beta")
    with tenancy.usando(org), SessionLocal() as db:
        u = Usuario(nome="Novo", email="novo@beta.com", login="novo", perfil_acesso_id=perfis.garantir_padrao(db)["Gestor"].id)
        db.add(u)
        db.commit()
        assert "novo" in _logins("beta")
        u.login = "renomeado"
        db.commit()
        assert "renomeado" in _logins("beta") and "novo" not in _logins("beta")
        u.ativo = False
        db.commit()
        assert "renomeado" not in _logins("beta")
        db.delete(u)
        db.commit()
    assert multi.sincronizar_todos("beta") >= 2
    assert {"ana", "bia"} <= _logins("beta")


def test_dados_de_modulo_isolados_por_banco(multi):
    """Módulos não têm tenant_id: a empresa criada na alfa simplesmente não existe no banco da beta."""
    from app.modules.nucleo.models import Empresa

    with tenancy.usando(multi.por_slug("alfa")), SessionLocal() as db:
        db.add(Empresa(nome="Só da Alfa"))
        db.commit()
    with tenancy.usando(multi.por_slug("beta")), SessionLocal() as db:
        assert db.scalar(select(Empresa).where(Empresa.nome == "Só da Alfa")) is None


def test_primeiro_acesso_cria_o_gestor_uma_vez(multi, client):
    org, link = multi.provisionar("epsilon", "Organização Epsilon", admin_email="dono@epsilon.com", primeiro_acesso=True)
    assert "/primeiro-acesso?token=" in link
    with tenancy.usando(multi.por_slug("epsilon")), SessionLocal() as db:
        assert db.scalar(select(Usuario.id)) is None  # o Gestor ainda não existe
    token = link.split("token=")[1]
    info = client.get("/api/auth/primeiro-acesso", params={"token": token})
    assert info.json() == {"organizacao": "Organização Epsilon", "email": "dono@epsilon.com"}, info.text
    dados = {"token": token, "nome": "Dono Epsilon", "email": "dono@epsilon.com", "login": "dono.epsilon", "senha": SENHA}
    assert client.post("/api/auth/primeiro-acesso", json={**dados, "senha": "fraca"}).status_code == 400
    r = client.post("/api/auth/primeiro-acesso", json=dados)
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["administrador"] is True and r.json()["usuario"]["organizacao"]["slug"] == "epsilon"
    # o link vale uma vez só
    assert client.post("/api/auth/primeiro-acesso", json={**dados, "login": "outro"}).status_code == 409
    assert client.get("/api/auth/primeiro-acesso", params={"token": token}).status_code == 409
    assert "dono.epsilon" in _logins("epsilon")


# último: sai do controle próprio e desliga o modo multi do módulo
def test_registra_a_organizacao_do_banco_principal():
    from sqlalchemy.orm import Session

    from app.controle import service
    from app.core.models import Identidade

    with Session(tenancy.engine_do(None)) as db:  # o banco principal (DATABASE_URL), direto
        db.add(Identidade(id=1, nome_exibicao="Flic Demo"))
        db.add(Usuario(nome="Ana", email="ana@flic.com", login="ana.flic"))
        db.commit()
    with controle_proprio():
        assert service.registrar_principal_se_faltar() == "flic-demo"
        assert service.registrar_principal_se_faltar() is None
        assert service.por_slug("flic-demo").banco is None
        assert service.por_login("ana.flic").slug == "flic-demo"
        with tenancy.usando(service.por_slug("flic-demo")):
            assert tenancy.pasta_base() == Path(settings.storage_dir)  # a principal continua em storage/
