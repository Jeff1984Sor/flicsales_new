"""Plano e consumo: uso do mês da organização (Núcleo › Administração)."""

from sqlalchemy import func, select

from app.core.models import Usuario

URL = "/api/orquestracao/consumo"


def test_consumo_conta_perguntas_do_mes_e_usuarios_ativos(client, gestor, db):
    antes = client.get(URL, headers=gestor)
    assert antes.status_code == 200, antes.text
    d = antes.json()
    assert d["usuarios_ativos"] == db.scalar(select(func.count(Usuario.id)).where(Usuario.ativo.is_(True)))
    assert len(d["competencia"]) == 7 and d["competencia"][4] == "-"
    r = client.post("/api/orquestracao/ia/perguntar",
                    json={"escopo": "modulo", "modulo": "comercial", "pergunta": "O que precisa de atenção?"},
                    headers=gestor)
    assert r.status_code == 200, r.text
    depois = client.get(URL, headers=gestor).json()
    assert depois["perguntas_ia_mes"] == d["perguntas_ia_mes"] + 1
    assert depois["perguntas_ia_com_provedor_mes"] == d["perguntas_ia_com_provedor_mes"]  # IA desligada: regras
    assert depois["automacoes_ativas"] >= 0 and depois["execucoes_mes"] >= 0


def test_consumo_exige_administracao(client, comercial, financeiro):
    assert client.get(URL, headers=comercial).status_code == 403
    assert client.get(URL, headers=financeiro).status_code == 403
