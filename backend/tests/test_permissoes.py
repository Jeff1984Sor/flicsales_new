"""Catálogo de permissões, perfis padrão, mapa rota → permissão (negar por padrão) e escopo "só meus registros"."""

import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import Column, Integer, MetaData, Table, insert, select

from app.core import escopo
from app.core.deps import Contexto, Ctx, get_contexto
from app.core.permissoes import (
    PERFIS_PADRAO,
    RECURSOS,
    TODAS,
    adicionar_regras,
    normalizar,
    permissao_da_rota,
    separar,
)
from tests.conftest import auth, criar_usuario, entrar

RECURSOS_ESPERADOS = {
    "nucleo.cadastros", "nucleo.campos", "nucleo.administracao", "auditoria", "comercial.oportunidades",
    "comercial.atividades", "comercial.comunicacoes", "comercial.propostas", "comercial.metas", "comercial.desempenho",
    "comercial.recursos", "financeiro.titulos", "financeiro.baixas", "financeiro.aprovacoes", "financeiro.caixa",
    "financeiro.cobrancas", "financeiro.recorrencias", "financeiro.cadastros", "orquestracao.ia",
    "orquestracao.automacoes", "orquestracao.integracoes", "configuracoes",
}


def _perfil(nome: str) -> dict:
    return next(p for p in PERFIS_PADRAO if p["nome"] == nome)


def test_catalogo_tem_todos_os_recursos_dos_modulos():
    assert RECURSOS == RECURSOS_ESPERADOS
    assert {separar(p)[1] for p in TODAS} == {"ver", "editar"}
    assert "auditoria.ver" in TODAS and "auditoria.editar" not in TODAS
    assert separar("comercial.oportunidades.ver") == ("comercial.oportunidades", "ver")


def test_perfis_padrao():
    assert [p["nome"] for p in PERFIS_PADRAO] == ["Gestor", "Comercial", "Financeiro", "Somente leitura"]
    gestor = _perfil("Gestor")
    assert gestor["administrador"] and gestor["sistema"]
    for p in PERFIS_PADRAO:
        assert set(p["permissoes"]) <= TODAS, p["nome"]
        assert p["somente_meus_registros"] is False


def test_comercial_nao_mexe_no_financeiro_nem_na_administracao():
    perms = set(_perfil("Comercial")["permissoes"])
    assert {f"{r}.editar" for r in RECURSOS_ESPERADOS if r.startswith("comercial.")} <= perms
    assert {"nucleo.cadastros.editar", "financeiro.titulos.ver", "orquestracao.ia.ver"} <= perms
    for proibida in ("financeiro.titulos.editar", "financeiro.baixas.ver", "financeiro.caixa.ver",
                     "nucleo.administracao.ver", "configuracoes.ver", "auditoria.ver"):
        assert proibida not in perms, proibida


def test_financeiro_nao_aprova_e_nao_edita_comercial():
    perms = set(_perfil("Financeiro")["permissoes"])
    assert {"financeiro.titulos.editar", "financeiro.baixas.editar", "financeiro.aprovacoes.ver",
            "financeiro.cadastros.editar", "comercial.oportunidades.ver"} <= perms
    for proibida in ("financeiro.aprovacoes.editar", "comercial.oportunidades.editar", "nucleo.administracao.ver"):
        assert proibida not in perms, proibida


def test_somente_leitura_nao_edita_nada():
    perms = _perfil("Somente leitura")["permissoes"]
    assert perms and all(p.endswith(".ver") for p in perms)
    assert "comercial.oportunidades.ver" in perms and "financeiro.caixa.ver" in perms


def test_mapa_de_rotas_dos_modulos():
    casos = {
        ("GET", "/api/comercial/oportunidades"): "comercial.oportunidades.ver",
        ("POST", "/api/comercial/oportunidades/3/ganhar"): "comercial.oportunidades.editar",
        ("DELETE", "/api/nucleo/empresas/3"): "nucleo.cadastros.editar",  # nada é excluído: inativar = editar
        ("POST", "/api/financeiro/titulos/9/baixas"): "financeiro.baixas.editar",
        ("POST", "/api/financeiro/titulos/9/aprovar"): "financeiro.aprovacoes.editar",
        ("PATCH", "/api/financeiro/titulos/9"): "financeiro.titulos.editar",
        ("GET", "/api/financeiro/caixa"): "financeiro.caixa.ver",
        ("POST", "/api/financeiro/fornecedores"): "financeiro.cadastros.editar",
        ("POST", "/api/orquestracao/ia/perguntar"): "orquestracao.ia.editar",
        ("GET", "/api/config/perfis"): "nucleo.administracao.ver",
        ("PUT", "/api/config/ia"): "configuracoes.editar",
        ("GET", "/api/auditoria"): "auditoria.ver",
    }
    for (metodo, caminho), esperada in casos.items():
        assert permissao_da_rota(metodo, caminho) == (True, esperada), (metodo, caminho)
    assert permissao_da_rota("GET", "/api/auth/me") == (True, None)
    assert permissao_da_rota("GET", "/api/config/usuarios/opcoes") == (True, None)
    assert permissao_da_rota("GET", "/api/comercial/metas-x") == (False, None)  # fronteira de segmento
    assert permissao_da_rota("GET", "/api/rota/que/ninguem/mapeou") == (False, None)


def test_adicionar_regras_so_aceita_permissao_do_catalogo():
    with pytest.raises(ValueError, match="fora do catálogo"):
        adicionar_regras([("GET", r"/comercial/x$", "comercial.inventado.ver")])
    with pytest.raises(ValueError):
        adicionar_regras([("GET", r"/comercial/x$", "comercial.oportunidades.excluir")])


def test_normalizar_descarta_desconhecidas_e_inclui_ver():
    assert normalizar(["comercial.propostas.editar", "coisa.inventada"]) == [
        "comercial.propostas.editar", "comercial.propostas.ver"]


def test_rota_sem_mapa_responde_403_mesmo_para_gestor(client, token_admin):
    from app.main import app

    antes = list(app.router.routes)
    r = APIRouter()

    @r.get("/rota-orfa")
    def orfa(ctx: Ctx):
        return {"ok": True}

    app.include_router(r, prefix="/api", dependencies=[Depends(get_contexto)])
    try:
        assert client.get("/api/rota-orfa", headers=auth(token_admin)).status_code == 403
    finally:
        app.router.routes[:] = antes


def test_comercial_e_barrado_na_administracao(client, db):
    criar_usuario(db, "Comercial", email="marina@exemplo.com")
    h = auth(entrar(client, "marina").json()["access_token"])
    assert client.get("/api/auth/me", headers=h).status_code == 200
    for caminho in ("/api/config/usuarios", "/api/config/perfis", "/api/auditoria", "/api/config/email", "/api/config/ia"):
        assert client.get(caminho, headers=h).status_code == 403, caminho
    assert client.get("/api/config/identidade", headers=h).status_code == 200  # leitura livre
    opcoes = client.get("/api/config/usuarios/opcoes", headers=h)
    assert opcoes.status_code == 200 and opcoes.json()[0].keys() == {"id", "nome", "login"}


def test_gestor_padrao_nao_exclui_nem_perde_acesso_total(client, token_admin):
    h = auth(token_admin)
    gestor = next(p for p in client.get("/api/config/perfis", headers=h).json() if p["nome"] == "Gestor")
    assert client.delete(f"/api/config/perfis/{gestor['id']}", headers=h).status_code == 400
    assert client.put(f"/api/config/perfis/{gestor['id']}", headers=h,
                      json={"nome": "Gestor", "administrador": False}).status_code == 400


def test_perfil_com_so_meus_registros(client, token_admin):
    h = auth(token_admin)
    r = client.post("/api/config/perfis", headers=h, json={
        "nome": "Comercial restrito", "somente_meus_registros": True,
        "permissoes": ["comercial.oportunidades.editar"]})
    assert r.status_code == 201, r.text
    assert r.json()["somente_meus_registros"] is True
    assert r.json()["permissoes"] == ["comercial.oportunidades.editar", "comercial.oportunidades.ver"]
    # administrador nunca fica restrito
    r = client.post("/api/config/perfis", headers=h, json={"nome": "Adm 2", "administrador": True,
                                                           "somente_meus_registros": True})
    assert r.json()["somente_meus_registros"] is False


def test_escopo_filtra_pelo_responsavel(db):
    from app.core.models import PerfilAcesso

    t = Table("registro_stub", MetaData(), Column("id", Integer, primary_key=True), Column("responsavel_id", Integer))
    t.create(db.get_bind())
    marina = criar_usuario(db, "Comercial", email="marina@exemplo.com")
    lucas = criar_usuario(db, "Comercial", email="lucas@exemplo.com")
    gestor = criar_usuario(db, "Gestor", email="g@exemplo.com")
    db.execute(insert(t), [{"id": 1, "responsavel_id": marina.id}, {"id": 2, "responsavel_id": lucas.id}])

    def ids(u):
        ctx = Contexto(db=db, usuario=u, ip=None)
        return sorted(db.scalars(ctx.filtrar_meus(select(t.c.id), t.c.responsavel_id)))

    assert ids(marina) == [1, 2]  # perfil Comercial padrão não restringe
    db.scalar(select(PerfilAcesso).where(PerfilAcesso.nome == "Comercial")).somente_meus_registros = True
    db.commit()
    db.refresh(marina)
    assert ids(marina) == [1] and ids(lucas) == [2] and ids(gestor) == [1, 2]
    ctx = Contexto(db=db, usuario=marina, ip=None)
    assert ctx.somente_meus_registros() and ctx.pode_acessar(marina.id) and not ctx.pode_acessar(lucas.id)
    assert escopo.pode_acessar(Contexto(db=db, usuario=gestor, ip=None), lucas.id)
    t.drop(db.get_bind())
