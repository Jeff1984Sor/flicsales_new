from datetime import date, time
from decimal import Decimal as D

import pytest

from app.domain import RegraViolada, funil
from app.domain import atividade as atv
from app.domain import indicadores as ind
from app.domain import leitura as lei
from app.domain import proposta as prop
from app.domain.cadastro import chave_de_nome, validar_nome, validar_nome_unico, validar_papeis
from app.domain.csv_seguro import BOM, gerar_csv, neutralizar

HOJE = date(2026, 11, 10)


# ---------------------------------------------------------------- funil
def test_etapas_validas_e_invalidas():
    assert funil.validar_etapas([" Entrada ", "Discovery", "Proposta", "Negociação"])[0] == "Entrada"
    for ruim in (["Entrada"], [], ["Entrada", "entrada"], ["Entrada", "Ganha"], ["Perdida", "Proposta"], ["A", " "]):
        with pytest.raises(RegraViolada, match="pelo menos duas etapas únicas"):
            funil.validar_etapas(ruim)


def test_forecast_ponderado():
    itens = [funil.ItemForecast(D("24000"), 75), funil.ItemForecast(D("18000"), 50),
             funil.ItemForecast(D("12000"), 25), funil.ItemForecast(D("9600"), 10)]
    assert funil.forecast_ponderado(itens) == D("30960.00")  # 18000 + 9000 + 3000 + 960
    with pytest.raises(RegraViolada):
        funil.forecast_ponderado([funil.ItemForecast(D("1"), 101)])


def test_dias_na_etapa_e_limite():
    assert funil.dias_na_etapa(date(2026, 11, 1), HOJE) == 9
    assert funil.alem_do_limite(date(2026, 11, 1), 7, HOJE) is True
    assert funil.alem_do_limite(date(2026, 11, 3), 7, HOJE) is False  # exatamente no limite
    assert funil.alem_do_limite(date(2026, 1, 1), None, HOJE) is False
    assert funil.dias_na_etapa(None, HOJE) == 0


def test_perda_ganho_e_valor():
    with pytest.raises(RegraViolada, match="Informe o motivo da perda"):
        funil.validar_perda("  ")
    assert funil.validar_perda(" Preço ") == "Preço"
    with pytest.raises(RegraViolada, match="revisão financeira"):
        funil.validar_alteracao_valor("ganha")
    funil.validar_alteracao_valor("aberta")
    with pytest.raises(RegraViolada):
        funil.validar_valores("-1", "0")
    assert funil.validar_probabilidade(0) == 0 and funil.validar_limite_dias(None) is None
    with pytest.raises(RegraViolada):
        funil.validar_limite_dias(0)


# ---------------------------------------------------------------- proposta
def test_total_da_proposta():
    assert prop.calcular_total("1", "24000", "10") == D("21600.00")
    assert prop.validar_proposta(quantidade=2, preco_unitario="1500", desconto_pct=0, justificativa_desconto=None) == D("3000.00")


def test_proposta_validacoes():
    for q, d in ((0, 0), (-1, 0), (1, -1), (1, D("100.01"))):
        with pytest.raises(RegraViolada, match="Quantidade deve ser positiva e desconto entre 0 e 100%"):
            prop.validar_proposta(quantidade=q, preco_unitario="10", desconto_pct=d, justificativa_desconto="x")
    with pytest.raises(RegraViolada, match="Registre a justificativa do desconto"):
        prop.validar_proposta(quantidade=1, preco_unitario="10", desconto_pct=5, justificativa_desconto=" ")
    assert prop.validar_proposta(quantidade=1, preco_unitario="10", desconto_pct=100, justificativa_desconto="Cortesia") == D("0.00")
    assert prop.exige_aprovacao_desconto(5) and not prop.exige_aprovacao_desconto(0)
    assert prop.proxima_versao([1, 2]) == 3 and prop.proxima_versao([]) == 1


# ---------------------------------------------------------------- indicadores
def test_indicadores_do_prototipo():
    assert ind.conversao(8, 16) == D("33.3")
    assert ind.ticket_medio(D("160000"), 8) == D("20000.00")
    assert ind.conversao(0, 0) is None and ind.ticket_medio(D("0"), 0) is None


def test_ciclo_mediano_e_meta():
    pares = [(date(2026, 1, 1), date(2026, 1, 11)), (date(2026, 1, 1), date(2026, 1, 31)),
             (date(2026, 1, 1), date(2026, 1, 21))]
    assert ind.ciclo_mediano(pares) == D("20.0")
    assert ind.ciclo_mediano(pares[:2]) == D("20.0")  # (10 + 30) / 2
    assert ind.ciclo_mediano([]) is None
    assert ind.apuracao_meta(D("45000"), D("60000")) == D("75.0") and ind.apuracao_meta(1, 0) is None
    assert "ganhas" in ind.FORMULAS["conversao"]


# ---------------------------------------------------------------- atividade
def test_reuniao_exige_inicio_antes_do_fim():
    kw = dict(assunto="Discovery", tipo="reuniao", prazo=HOJE)
    atv.validar_atividade(**kw, hora_inicio=time(9), hora_fim=time(10))
    for ini, fim in ((None, time(10)), (time(10), None), (time(10), time(10)), (time(11), time(10))):
        with pytest.raises(RegraViolada, match="Reunião exige início e fim válido no mesmo dia"):
            atv.validar_atividade(**kw, hora_inicio=ini, hora_fim=fim)
    atv.validar_atividade(assunto="Ligar", tipo="ligacao", prazo=HOJE, hora_inicio=None, hora_fim=None)
    with pytest.raises(RegraViolada):
        atv.validar_atividade(assunto="", tipo="tarefa", prazo=HOJE, hora_inicio=None, hora_fim=None)
    with pytest.raises(RegraViolada):
        atv.validar_atividade(assunto="x", tipo="sms", prazo=HOJE, hora_inicio=None, hora_fim=None)


def test_atividade_atrasada_e_conclusao():
    assert atv.atrasada(prazo=date(2026, 11, 9), status="pendente", hoje=HOJE)
    assert not atv.atrasada(prazo=HOJE, status="pendente", hoje=HOJE)
    assert not atv.atrasada(prazo=date(2026, 11, 9), status="concluida", hoje=HOJE)
    assert atv.validar_conclusao("pendente") == "concluida"
    with pytest.raises(RegraViolada):
        atv.validar_conclusao("concluida")


# ---------------------------------------------------------------- cadastro
def test_nome_de_empresa_unico_normalizado():
    assert chave_de_nome("  Aurora   Consultória ") == "aurora consultoria"
    with pytest.raises(RegraViolada, match="Já existe empresa com este nome"):
        validar_nome_unico("AURORA consultoria", {"aurora consultoria"})
    validar_nome_unico("Aurora Tech", {"aurora consultoria"})
    with pytest.raises(RegraViolada):
        validar_nome("   ", o_que="o nome da empresa")
    assert validar_papeis(["fornecedor", "cliente"]) == ["cliente", "fornecedor"]
    with pytest.raises(RegraViolada):
        validar_papeis(["concorrente"])


# ---------------------------------------------------------------- CSV
def test_csv_neutraliza_formula_com_bom_e_ponto_e_virgula():
    dados = gerar_csv(["Empresa", "Valor", "Vencimento"],
                      [["=HYPERLINK(\"x\")", D("1234.50"), date(2026, 11, 20)], ["+55 11", D("-5"), None],
                       ["-cmd", 1, None], ["@SUM(A1)", True, None], ["Aurora; filial", 0, None]])
    texto = dados.decode("utf-8")
    assert texto.startswith(BOM)
    linhas = texto.removeprefix(BOM).split("\r\n")
    assert linhas[0] == "Empresa;Valor;Vencimento"
    assert linhas[1] == "\"'=HYPERLINK(\"\"x\"\")\";1234,50;20/11/2026"
    assert linhas[2].startswith("'+55 11;-5;")  # número negativo continua número
    assert linhas[3].startswith("'-cmd") and linhas[4].startswith("'@SUM(A1);Sim")
    assert linhas[5] == "\"Aurora; filial\";0;"
    assert neutralizar("Normal") == "Normal"
    with pytest.raises(RegraViolada, match="Sem registros para exportar"):
        gerar_csv(["a"], [])


# ---------------------------------------------------------------- leitura do momento
def _leitura(**kw):
    return lei.ler_momento(hoje=HOJE, **kw)


TITULOS = [
    lei.TituloResumo(1, "Ponto Norte", "Consultoria • parcela 1/2", "receber", "aberto", date(2026, 11, 3), D("6000")),
    lei.TituloResumo(2, "Estúdio Base", "Mensalidade", "receber", "aberto", date(2026, 11, 20), D("4800")),
    lei.TituloResumo(3, "Espaço Compartilhado", "Aluguel", "pagar", "aberto", date(2026, 11, 1), D("4200")),
    lei.TituloResumo(4, "Lume", "Implantação", "receber", "rascunho", date(2026, 10, 1), D("8500")),
]
OPORTUNIDADES = [
    lei.OportunidadeResumo(10, "Consultoria recorrente", "Atlas Tecnologia", "Entrada", D("9600"), proxima_acao=None,
                           entrou_etapa_em=date(2026, 11, 9), limite_dias=2),
    lei.OportunidadeResumo(11, "Diagnóstico estratégico", "Horizonte Gestão", "Discovery", D("12000"),
                           proxima_acao="Preparar discovery", entrou_etapa_em=date(2026, 11, 1), limite_dias=7),
    lei.OportunidadeResumo(12, "Ganha antiga", "X", "Negociação", D("1"), resultado="ganha"),
]
ATIVIDADES = [lei.AtividadeResumo(20, "Retomar proposta da Vértice", date(2026, 11, 9), empresa="Vértice Serviços"),
              lei.AtividadeResumo(21, "Concluída", date(2026, 11, 1), status="concluida")]


def test_leitura_prioriza_vencido_e_tem_formato_da_ia():
    r = _leitura(titulos=TITULOS, oportunidades=OPORTUNIDADES, atividades=ATIVIDADES)
    assert set(r) == {"titulo", "analise", "proxima_acao", "evidencias", "limites", "acoes_sugeridas", "origem",
                      "ferramentas"}
    assert all({"fonte", "trecho"} <= set(e) for e in r["evidencias"])
    assert all({"tipo", "rotulo", "payload"} <= set(a) for a in r["acoes_sugeridas"])
    criar = [a for a in r["acoes_sugeridas"] if a["tipo"] == "criar_atividade"]
    assert criar and criar[0]["payload"]["oportunidade_id"] == 10 and criar[0]["payload"]["assunto"]
    assert r["origem"] == "regras" and r["titulo"] == "Recebível vencido pede ação"
    assert [e["registro"] for e in r["evidencias"]] == [
        {"tipo": "titulo", "id": 1}, {"tipo": "oportunidade", "id": 10}, {"tipo": "oportunidade", "id": 11},
        {"tipo": "atividade", "id": 20}]
    assert "R$ 6.000,00" in r["evidencias"][0]["texto"] and "1 recebível(is) vencido(s)" in r["analise"]
    assert r["proxima_acao"] == "Abrir cobrança de Ponto Norte"
    assert any("IA desligada" in x for x in r["limites"])
    assert len(r["acoes_sugeridas"]) == 3


def test_leitura_deterministica_e_sem_pendencias():
    a = _leitura(titulos=TITULOS, oportunidades=OPORTUNIDADES, atividades=ATIVIDADES)
    b = _leitura(titulos=list(reversed(TITULOS)), oportunidades=list(reversed(OPORTUNIDADES)),
                 atividades=list(reversed(ATIVIDADES)))
    assert a == b
    vazio = _leitura(ia_ligada=True)
    assert vazio["titulo"] == "Tudo em dia" and vazio["evidencias"] == []
    assert not any("IA desligada" in x for x in vazio["limites"])
    so_opp = _leitura(oportunidades=OPORTUNIDADES[:1])
    assert so_opp["titulo"] == "Negociação sem próxima ação"
