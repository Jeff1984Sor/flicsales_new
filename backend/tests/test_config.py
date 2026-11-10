"""Configurações pela API (identidade, usuários, perfis), cabeçalhos de segurança, worker e seed base.
Portado do MayaFit (tests/test_config_e_cli.py)."""

from sqlalchemy import select

from app import seed
from app.core.models import ConfigEmail, Identidade, PerfilAcesso, Usuario
from tests.conftest import auth, criar_usuario, entrar


def test_seed_base_e_idempotente_e_nao_sobrescreve_o_editado(db):
    seed.base(db)
    seed.base(db)
    db.commit()
    assert db.scalar(select(Identidade.nome_exibicao)) == "FlicSales Demo"
    assert db.get(ConfigEmail, 1) is not None
    assert not list(db.scalars(select(Usuario)))  # a base não cria usuário
    db.scalar(select(Identidade)).nome_exibicao = "Minha Organização"
    p = db.scalar(select(PerfilAcesso).where(PerfilAcesso.nome == "Comercial"))
    p.permissoes = ["comercial.oportunidades.ver"]
    db.commit()
    seed.base(db)
    db.commit()
    assert db.scalar(select(Identidade.nome_exibicao)) == "Minha Organização"
    assert db.scalar(select(PerfilAcesso.permissoes).where(PerfilAcesso.nome == "Comercial")) == ["comercial.oportunidades.ver"]


# ---------------------------------------------------------------------------------------------- usuários / identidade (API)
def test_identidade_publica_padrao_e_editada(client, db, token_admin):
    assert client.get("/api/public/identidade").json()["nome_exibicao"] == "FlicSales OS"  # padrão sem banco populado
    seed.base(db)
    db.commit()
    assert client.get("/api/public/identidade").json()["nome_exibicao"] == "FlicSales Demo"
    h = auth(token_admin)
    r = client.put("/api/config/identidade", headers=h, json={"nome_exibicao": "Outra Organização", "cor_destaque": "#0057D9"})
    assert r.status_code == 200
    assert client.get("/api/public/identidade").json() == {"nome_exibicao": "Outra Organização", "logo_url": None, "cor_destaque": "#0057D9"}
    assert client.put("/api/config/identidade", headers=h, json={"nome_exibicao": "X", "cor_destaque": "vermelho"}).status_code == 422


def test_crud_de_usuario_com_e_sem_login(client, db, token_admin, emails):
    h = auth(token_admin)
    perfil = client.get("/api/config/perfis", headers=h).json()
    pid = next(p["id"] for p in perfil if p["nome"] == "Comercial")
    r = client.post("/api/config/usuarios", headers=h, json={"nome": "Ana Comercial", "email": "ana@exemplo.com", "login": "ana", "perfil_acesso_id": pid})
    assert r.status_code == 201 and r.json()["convite_pendente"] is True
    assert emails and "redefinir-senha?token=" in emails[0][2]  # convite por link
    # pessoa sem login: não recebe convite e não consegue entrar
    r = client.post("/api/config/usuarios", headers=h, json={"nome": "Bia", "email": "bia@exemplo.com", "perfil_acesso_id": pid,
                                                             "acesso_sistema": False})
    assert r.status_code == 201 and len(emails) == 1
    assert db.scalar(select(Usuario.senha_hash).where(Usuario.email == "bia@exemplo.com")) is None
    # e-mail duplicado
    assert client.post("/api/config/usuarios", headers=h, json={"nome": "Dup", "email": "ANA@exemplo.com", "login": "dup",
                                                                "perfil_acesso_id": pid}).status_code == 409
    # perfil obrigatório e existente
    assert client.post("/api/config/usuarios", headers=h, json={"nome": "Sem", "email": "s@exemplo.com", "login": "sem"}).status_code == 404
    lista = client.get("/api/config/usuarios", headers=h).json()
    assert {u["email"] for u in lista} >= {"ana@exemplo.com", "bia@exemplo.com"}


def test_admin_define_senha_do_usuario_e_derruba_sessoes(client, db, token_admin):
    u = criar_usuario(db, "Comercial", email="p@exemplo.com")
    antigo = entrar(client, "p@exemplo.com").json()["access_token"]
    h = auth(token_admin)
    assert client.post(f"/api/config/usuarios/{u.id}/definir-senha", headers=h, json={"senha": "fraca"}).status_code == 400
    assert client.post(f"/api/config/usuarios/{u.id}/definir-senha", headers=h, json={"senha": "Nova@Senha5"}).status_code == 200
    assert client.get("/api/auth/me", headers=auth(antigo)).status_code == 401
    assert entrar(client, "p@exemplo.com", "Nova@Senha5").status_code == 200


def test_me_patch_e_preferencias(client, admin, token_admin):
    h = auth(token_admin)
    r = client.patch("/api/auth/me", headers=h, json={"nome": "Novo Nome", "telefone": "11999990000"})
    assert r.status_code == 200 and r.json()["nome"] == "Novo Nome"
    r = client.put("/api/auth/me/preferencias", headers=h, json={"menu_recolhido": ["Financeiro"]})
    assert r.json()["preferencias"] == {"menu_recolhido": ["Financeiro"]}
    r = client.get("/api/auth/me", headers=h).json()
    assert "senha_hash" not in r and "token_version" not in r and r["administrador"] is True


def test_cabecalhos_de_seguranca_e_host_invalido(client):
    r = client.get("/api/health")
    assert r.json()["ok"] is True
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert client.get("/api/health", headers={"Host": "evil.example.com"}).status_code == 400


def test_worker_executa_tarefas_vencidas_e_isola_falhas():
    from app import worker

    chamadas = []
    antes = list(worker.TAREFAS)
    worker.TAREFAS.clear()
    worker.registrar_tarefa("a", 10, lambda: chamadas.append("a"))
    worker.registrar_tarefa("quebra", 10, lambda: 1 / 0)
    worker.registrar_tarefa("b", 100, lambda: chamadas.append("b"))
    try:
        assert worker.executar_pendentes(agora_s=0) == ["a", "b"]  # a que quebrou não derruba as outras
        assert worker.executar_pendentes(agora_s=5) == []
        assert worker.executar_pendentes(agora_s=11) == ["a"]
    finally:
        worker.TAREFAS[:] = antes


def test_criar_usuario_com_acesso_exige_login(client, db, token_admin):
    h = auth(token_admin)
    pid = next(p["id"] for p in client.get("/api/config/perfis", headers=h).json() if p["nome"] == "Comercial")
    r = client.post("/api/config/usuarios", headers=h, json={"nome": "Sem Login", "email": "sl@exemplo.com", "perfil_acesso_id": pid})
    assert r.status_code == 422
    # login com "@" é recusado
    r = client.post("/api/config/usuarios", headers=h, json={"nome": "Email", "email": "e@exemplo.com", "login": "e@exemplo.com", "perfil_acesso_id": pid})
    assert r.status_code == 422


def test_regra_violada_vira_400_com_a_mensagem(client, token_admin):
    from fastapi import APIRouter, Depends

    from app.core.deps import Ctx, get_contexto
    from app.core.permissoes import adicionar_regras
    from app.domain import RegraViolada
    from app.main import app

    antes = list(app.router.routes)
    r = APIRouter()

    @r.post("/comercial/oportunidades/regra-teste")
    def quebra(ctx: Ctx):
        raise RegraViolada("Informe o motivo da perda")

    adicionar_regras([("POST", r"/comercial/oportunidades/regra-teste$", "comercial.oportunidades.editar")])
    app.include_router(r, prefix="/api", dependencies=[Depends(get_contexto)])
    try:
        resp = client.post("/api/comercial/oportunidades/regra-teste", headers=auth(token_admin))
        assert resp.status_code == 400 and resp.json() == {"detail": "Informe o motivo da perda"}
    finally:
        app.router.routes[:] = antes
