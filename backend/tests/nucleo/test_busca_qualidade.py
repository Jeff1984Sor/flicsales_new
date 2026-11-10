"""Busca global (respeita a permissão de cada recurso) e qualidade dos dados (duplicidades + mesclagem sem perder
vínculo)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.core.models import Auditoria, PerfilAcesso
from app.modules.comercial.models import (
    Atividade,
    Comunicacao,
    Funil,
    Oportunidade,
    Proposta,
)
from app.modules.financeiro.models import Recorrencia, Titulo
from app.modules.nucleo import servico
from app.modules.nucleo.models import Empresa, Pessoa


def _cenario(db, usuario_id, nome="Aurora Consultoria"):
    e = Empresa(nome=nome, campos_custom={})
    e.papeis = ["cliente"]
    funil = db.scalar(select(Funil)) or Funil(nome="Serviços B2B")
    db.add_all([e, funil])
    db.flush()
    op = Oportunidade(titulo=f"Projeto {nome}", funil_id=funil.id, empresa_id=e.id, responsavel_id=usuario_id)
    db.add_all([op, Pessoa(nome=f"Contato {nome}", empresa_id=e.id, campos_custom={})])
    db.flush()
    db.add_all([
        Titulo(direcao="receber", empresa_id=e.id, descricao=f"Parcela {nome}", vencimento=date(2026, 11, 20),
               valor_original=Decimal("10"), saldo=Decimal("10"), responsavel_id=usuario_id, status="aberto"),
        Atividade(assunto="Ligar", tipo="tarefa", responsavel_id=usuario_id, empresa_id=e.id, prazo=date(2026, 11, 10)),
        Comunicacao(canal="notas", conteudo="x", empresa_id=e.id),
        Proposta(titulo="P", oportunidade_id=op.id, empresa_id=e.id, versao=1, escopo="x", quantidade=Decimal("1"),
                 preco_unitario=Decimal("1"), validade=date(2026, 12, 1), condicao="à vista",
                 responsavel_id=usuario_id, total=Decimal("1")),
        Recorrencia(descricao="Mensalidade", direcao="receber", empresa_id=e.id, valor_ciclo=Decimal("1"),
                    frequencia="mensal", inicio=date(2026, 1, 1), fim=date(2026, 12, 1), dia_vencimento=10),
    ])
    db.commit()
    return e


# ------------------------------------------------------------------------------------------------- busca
def test_busca_todos_os_grupos(gestor, db):
    _cenario(db, gestor.usuario.id)
    r = gestor.get("/nucleo/busca", params={"q": "aurora"})
    assert r.status_code == 200
    grupos = {g["tipo"]: g["itens"] for g in r.json()["grupos"]}
    assert set(grupos) == {"empresas", "pessoas", "oportunidades", "titulos"}
    assert grupos["empresas"][0]["href"].startswith("/nucleo/cadastros?aba=empresas&id=")
    assert grupos["titulos"][0]["href"].startswith("/financeiro/receber?id=")
    assert grupos["oportunidades"][0]["titulo"] == "Projeto Aurora Consultoria"


def test_busca_maximo_cinco_e_termo_curto(gestor, db):
    for i in range(7):
        db.add(Empresa(nome=f"Atlas {i}", campos_custom={}))
    db.commit()
    grupos = gestor.get("/nucleo/busca", params={"q": "atlas"}).json()["grupos"]
    assert len(grupos[0]["itens"]) == 5
    assert gestor.get("/nucleo/busca", params={"q": "a"}).json()["grupos"] == []


def test_busca_respeita_permissao(gestor, comercial, financeiro, db):
    _cenario(db, gestor.usuario.id)
    tipos = lambda api: {g["tipo"] for g in api.get("/nucleo/busca", params={"q": "aurora"}).json()["grupos"]}  # noqa: E731
    assert tipos(financeiro) == {"empresas", "pessoas", "oportunidades", "titulos"}
    # o Comercial vê oportunidades, mas com "só meus registros" a oportunidade de outro responsável some
    perfil = db.get(PerfilAcesso, comercial.usuario.perfil_acesso_id)
    perfil.somente_meus_registros = True
    perfil.permissoes = [p for p in perfil.permissoes if p != "financeiro.titulos.ver"]
    db.commit()
    assert tipos(comercial) == {"empresas", "pessoas"}


# ------------------------------------------------------------------------------------------------- duplicidades
def test_duplicidades(gestor, leitura, db):
    _cenario(db, gestor.usuario.id, "Aurora Consultoria")
    db.add_all([Empresa(nome="Aurora Consultoria Ltda.", campos_custom={}), Empresa(nome="Nuvem", campos_custom={})])
    db.commit()
    r = gestor.get("/nucleo/duplicidades")
    assert r.status_code == 200
    (par,) = r.json()
    assert {par["a"]["nome"], par["b"]["nome"]} == {"Aurora Consultoria", "Aurora Consultoria Ltda."}
    assert par["a"]["oportunidades"] == 1 and par["motivo"] == "Mesmo nome sem sufixos e pontuação"
    assert leitura.get("/nucleo/duplicidades").status_code == 403  # Qualidade dos dados = Administração


# ------------------------------------------------------------------------------------------------- mesclar
def _refs(db, empresa_id) -> int:
    return sum(db.scalar(select(func.count()).select_from(t).where(c == empresa_id)) or 0
               for t, c in servico.referencias_a_empresa())


def test_mesclar_move_todos_os_vinculos(gestor, db):
    fica = _cenario(db, gestor.usuario.id, "Aurora Consultoria")
    sai = _cenario(db, gestor.usuario.id, "Aurora Consultoria Ltda")
    sai.documento, sai.telefone, sai.papeis = "12.345.678/0001-90", "11 4000", ["fornecedor"]
    sai.campos_custom = {"origem": "Site"}
    db.commit()
    tabelas = {t.name for t, _ in servico.referencias_a_empresa()}
    assert {"pessoa", "oportunidade", "atividade", "comunicacao", "proposta", "titulo", "recorrencia"} <= tabelas
    total_antes = _refs(db, fica.id) + _refs(db, sai.id)
    ids_fica, ids_sai = fica.id, sai.id

    r = gestor.post(f"/nucleo/empresas/{ids_fica}/mesclar", {"duplicada_id": ids_sai})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["movidos"] == {"pessoa.empresa_id": 1, "oportunidade.empresa_id": 1, "atividade.empresa_id": 1,
                                "comunicacao.empresa_id": 1, "proposta.empresa_id": 1, "titulo.empresa_id": 1,
                                "recorrencia.empresa_id": 1}
    db.expire_all()
    assert _refs(db, ids_sai) == 0  # nenhum registro aponta mais para a duplicada
    assert _refs(db, ids_fica) == total_antes  # e nenhum vínculo se perdeu
    fica, sai = db.get(Empresa, ids_fica), db.get(Empresa, ids_sai)
    assert sai.ativo is False and "Mesclada em “Aurora Consultoria”" in sai.observacoes
    assert fica.ativo is True and fica.documento == "12.345.678/0001-90" and fica.telefone == "11 4000"
    assert fica.papeis == ["cliente", "fornecedor"] and fica.campos_custom == {"origem": "Site"}
    assert corpo["empresa"]["oportunidades"] == 2 and corpo["empresa"]["titulos_receber"] == 2
    aud = db.query(Auditoria).filter_by(acao="empresa.mesclar", entidade_id=str(ids_fica)).one()
    assert aud.depois_json["vinculos_movidos"]["titulo.empresa_id"] == 1
    assert db.query(Auditoria).filter_by(acao="empresa.inativar", entidade_id=str(ids_sai)).count() == 1
    assert gestor.get("/nucleo/duplicidades").json() == []


def test_mesclar_validacoes_404_403(gestor, comercial, db):
    a = _cenario(db, gestor.usuario.id, "A")
    b = _cenario(db, gestor.usuario.id, "B")
    assert gestor.post(f"/nucleo/empresas/{a.id}/mesclar", {"duplicada_id": a.id}).json()["detail"] == \
        "Escolha duas empresas diferentes para mesclar."
    assert gestor.post(f"/nucleo/empresas/{a.id}/mesclar", {"duplicada_id": 999}).status_code == 404
    assert gestor.post("/nucleo/empresas/999/mesclar", {"duplicada_id": a.id}).status_code == 404
    assert comercial.post(f"/nucleo/empresas/{a.id}/mesclar", {"duplicada_id": b.id}).status_code == 403
    gestor.delete(f"/nucleo/empresas/{a.id}")
    assert gestor.post(f"/nucleo/empresas/{a.id}/mesclar", {"duplicada_id": b.id}).json()["detail"] == \
        "A empresa que fica precisa estar ativa."


def test_servico_obter_ou_criar_empresa(db):
    e, criada = servico.obter_ou_criar_empresa(db, "Aurora Consultoria")
    assert criada and e.papeis == ["prospect"]
    e2, criada2 = servico.obter_ou_criar_empresa(db, " aurora consultória ", papeis=["cliente"])
    assert e2.id == e.id and not criada2 and e2.papeis == ["prospect", "cliente"]
