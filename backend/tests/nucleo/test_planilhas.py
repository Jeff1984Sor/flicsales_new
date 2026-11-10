"""Planilhas de migração: modelo .xlsx, simular (não grava), confirmar (tudo ou nada), chaves de atualização."""

import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook, load_workbook

from app.core.models import Auditoria
from app.modules.financeiro.models import Baixa, Titulo
from app.modules.nucleo.models import (
    CampoCustom,
    Categoria,
    CentroCusto,
    ContaFinanceira,
    Empresa,
    Pessoa,
    Produto,
)


def _csv(*linhas: str, sep=";", bom=True) -> bytes:
    texto = "\n".join(linhas).replace(";", sep)
    return (("﻿" if bom else "") + texto).encode("utf-8")


def _importar(api, objeto, conteudo: bytes, *, simular=True, nome="dados.csv"):
    return api.post(f"/nucleo/planilhas/{objeto}/importar", params={"simular": str(simular).lower()},
                    files={"arquivo": (nome, conteudo, "text/csv")})


def _contar(db, modelo):
    db.expire_all()
    return db.query(modelo).count()


# ------------------------------------------------------------------------------------------------- modelo
def test_modelo_xlsx_tem_dados_instrucoes_exemplo_e_listas(gestor, db):
    db.add(CampoCustom(nome="Origem", slug="origem", tipo="lista", objeto="empresa", opcoes=["Site", "Evento"]))
    db.add(CampoCustom(nome="Antigo", slug="antigo", tipo="texto", objeto="empresa", arquivado=True))
    db.commit()
    r = gestor.get("/nucleo/planilhas/empresas/modelo")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert 'modelo-empresas.xlsx' in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Dados", "Instruções"]
    ws = wb["Dados"]
    cab = [c.value for c in ws[1]]
    assert cab[0] == "Nome *" and "CNPJ/CPF" in cab and "CEP" in cab and "UF" in cab
    assert "Origem (personalizado)" in cab and "Antigo" not in cab  # colide com a coluna fixa "Origem"
    assert ws["A2"].value.startswith("EXEMPLO")
    listas = {dv.formula1 for dv in ws.data_validations.dataValidation}
    assert '"Site,Evento"' in listas and any("SP" in f for f in listas)
    inst = [c.value for c in wb["Instruções"]["A"]]
    assert any(v and "Chave para atualizar" in v for v in inst)


def test_modelo_de_todos_os_objetos(gestor):
    for objeto in ("empresas", "fornecedores", "pessoas", "produtos", "categorias", "centros-custo", "contas"):
        r = gestor.get(f"/nucleo/planilhas/{objeto}/modelo")
        assert r.status_code == 200, objeto
    assert gestor.get("/nucleo/planilhas/oportunidades/modelo").status_code == 404


def test_modelo_baixado_e_reenviado_sem_preencher_nao_tem_linhas(gestor):
    modelo = gestor.get("/nucleo/planilhas/pessoas/modelo").content
    r = _importar(gestor, "pessoas", modelo, nome="modelo.xlsx")
    assert r.status_code == 200 and r.json()["total"] == 0  # a linha EXEMPLO é ignorada


# ------------------------------------------------------------------------------------------------- empresas
EMPRESAS = _csv(
    "Nome *;CNPJ/CPF;Segmento;Papéis;CEP;Cidade;UF;Coluna estranha",
    "EXEMPLO: Aurora;;;;;;;",
    "Aurora Consultoria;11.222.333/0001-81;Consultoria;cliente;01310100;São Paulo;sp;x",
    "Vértice Serviços;;Serviços;prospect, parceiro;;;;",
    ";;;;;;;",
)


def test_simular_nao_grava(gestor, db):
    r = _importar(gestor, "empresas", EMPRESAS)
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["total"], d["criar"], d["atualizar"], d["ignorar"], d["erros"]) == (2, 2, 0, 0, [])
    assert d["previa"] == [{"linha": 3, "acao": "criar", "nome": "Aurora Consultoria"},
                           {"linha": 4, "acao": "criar", "nome": "Vértice Serviços"}]
    assert _contar(db, Empresa) == 0
    assert db.query(Auditoria).filter(Auditoria.acao.like("importacao%")).count() == 0


def test_confirmar_grava_audita_e_reimportar_nao_duplica(gestor, db):
    r = _importar(gestor, "empresas", EMPRESAS, simular=False)
    assert r.status_code == 200, r.text
    assert _contar(db, Empresa) == 2
    aurora = db.query(Empresa).filter_by(nome="Aurora Consultoria").one()
    assert (aurora.documento, aurora.cep, aurora.uf, aurora.papeis) == ("11.222.333/0001-81", "01310-100", "SP",
                                                                         ["cliente"])
    assert db.query(Empresa).filter_by(nome="Vértice Serviços").one().papeis == ["prospect", "parceiro"]
    aud = db.query(Auditoria).filter_by(acao="importacao.empresas").all()
    assert len(aud) == 3 and sum(a.entidade == "importacao" for a in aud) == 1  # 2 linhas + resumo
    # de novo, com o nome escrito diferente (chave = CNPJ) e só uma célula nova: atualiza; a outra fica igual
    de_novo = _csv("Nome;CNPJ/CPF;Telefone", "AURORA CONSULTORIA;11222333000181;(11) 3333-4444",
                   "vertice servicos;;")
    d = _importar(gestor, "empresas", de_novo, simular=False).json()
    assert (d["criar"], d["atualizar"], d["ignorar"]) == (0, 1, 1)
    db.expire_all()
    aurora = db.get(Empresa, aurora.id)
    assert aurora.telefone == "(11) 3333-4444" and aurora.segmento == "Consultoria"  # vazio não apaga
    assert aurora.nome == "Aurora Consultoria" and _contar(db, Empresa) == 2


def test_confirmar_com_erro_e_tudo_ou_nada(gestor, db):
    ruim = _csv("Nome;CNPJ/CPF;CEP;UF", "Boa Ltda;;;", "Ruim Ltda;12.345.678/0001-90;123;XX", ";;;SP")
    r = _importar(gestor, "empresas", ruim, simular=False)
    assert r.status_code == 400
    d = r.json()
    assert "nada foi gravado" in d["detail"] and d["criar"] == 1
    assert {"linha": 3, "coluna": "CNPJ/CPF", "mensagem": "CNPJ inválido."} in d["erros"]
    assert {(e["linha"], e["coluna"]) for e in d["erros"]} == {(3, "CNPJ/CPF"), (3, "CEP"), (3, "UF"), (4, "Nome")}
    assert _contar(db, Empresa) == 0


def test_coluna_obrigatoria_ausente_e_arquivo_invalido(gestor):
    d = _importar(gestor, "empresas", _csv("Segmento", "TI")).json()
    assert d["erros"][0]["linha"] == 1 and "Coluna obrigatória ausente: Nome" in d["erros"][0]["mensagem"]
    r = _importar(gestor, "empresas", b"", nome="x.csv")
    assert r.status_code == 400 and r.json()["detail"] == "O arquivo está vazio."
    r = _importar(gestor, "empresas", b"abc", nome="x.pdf")
    assert r.status_code == 400 and ".xlsx" in r.json()["detail"]
    r = _importar(gestor, "empresas", b"PK\x03\x04lixo", nome="x.xlsx")
    assert r.status_code == 400 and "Não foi possível ler" in r.json()["detail"]
    assert _importar(gestor, "empresas", b"x" * (5 * 1024 * 1024 + 1)).json()["detail"].startswith("Arquivo maior")


def test_limite_de_linhas(gestor):
    linhas = ["Nome"] + [f"Empresa {i}" for i in range(5001)]
    r = _importar(gestor, "empresas", _csv(*linhas))
    assert r.status_code == 400 and "5000 linhas" in r.json()["detail"]


def test_csv_com_virgula_sem_bom_e_campo_personalizado(gestor, db):
    db.add(CampoCustom(nome="Origem", slug="origem", tipo="lista", objeto="empresa", opcoes=["Site", "Evento"]))
    db.add(CampoCustom(nome="Faturamento", slug="faturamento", tipo="moeda", objeto="empresa"))
    db.commit()
    arq = _csv("Nome,Origem (personalizado),Faturamento", "Aurora,Site,\"1.234,50\"", "Atlas,Feira,", sep=",",
               bom=False)
    d = _importar(gestor, "empresas", arq).json()
    assert d["criar"] == 1 and d["erros"] == [{"linha": 3, "coluna": "Origem (personalizado)",
                                               "mensagem": "Origem: escolha uma das opções (Site, Evento)."}]
    _importar(gestor, "empresas", _csv("Nome,Origem (personalizado),Faturamento", "Aurora,Site,\"1.234,50\"",
                                       sep=","), simular=False)
    assert db.query(Empresa).one().campos_custom == {"origem": "Site", "faturamento": "1234.50"}


def test_xlsx_preenchido(gestor, db):
    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"
    ws.append(["Nome *", "CNPJ/CPF", "CEP", "Telefone"])
    ws.append(["EXEMPLO: x", None, None, None])
    ws.append(["Aurora", 11222333000181, 1310100, 11999998888])
    buf = io.BytesIO()
    wb.save(buf)
    r = _importar(gestor, "empresas", buf.getvalue(), simular=False, nome="migracao.xlsx")
    assert r.status_code == 200, r.text
    e = db.query(Empresa).one()
    assert (e.documento, e.cep, e.telefone) == ("11.222.333/0001-81", "01310-100", "11999998888")


def test_endereco_da_empresa_importado_propaga(gestor, db):
    e = gestor.post("/nucleo/empresas", {"nome": "Aurora", "cidade": "Santos"}).json()
    p = gestor.post("/nucleo/pessoas", {"nome": "Paula", "empresa_id": e["id"]}).json()
    _importar(gestor, "empresas", _csv("Nome;Cidade;UF", "Aurora;Campinas;SP"), simular=False)
    assert gestor.get(f"/nucleo/pessoas/{p['id']}").json()["cidade"] == "Campinas"
    assert db.query(Auditoria).filter_by(acao="pessoa.endereco_da_empresa").count() == 1


# ------------------------------------------------------------------------------------------------- fornecedores
def test_fornecedores(financeiro, db):
    db.add(Categoria(nome="Estrutura", natureza="despesa"))
    db.add(Empresa(nome="Lume Serviços", campos_custom={}, papel_cliente=True))
    db.commit()
    arq = _csv("Nome;Contato;E-mail;Categoria padrão;Condição habitual",
               "Lume Serviços;Joana;contas@lume.com;Estrutura;Boleto",
               "Nuvem Digital;;;Marketing;")
    d = _importar(financeiro, "fornecedores", arq).json()
    assert d["erros"] == [{"linha": 3, "coluna": "Categoria padrão", "mensagem":
                           "Categoria de despesa “Marketing” não encontrada. Cadastre-a (ou importe as categorias) "
                           "antes."}]
    arq = _csv("Nome;Contato;E-mail;Categoria padrão", "Lume Serviços;Joana;contas@lume.com;Estrutura", "Nuvem Digital;;;")
    d = _importar(financeiro, "fornecedores", arq, simular=False).json()
    assert (d["criar"], d["atualizar"]) == (1, 1)
    lume = db.query(Empresa).filter_by(nome="Lume Serviços").one()
    assert lume.papeis == ["cliente", "fornecedor"] and lume.email_financeiro == "contas@lume.com"
    assert db.query(Pessoa).filter_by(nome="Joana", empresa_id=lume.id).count() == 1
    assert db.query(Empresa).filter_by(nome="Nuvem Digital").one().papeis == ["fornecedor"]


# ------------------------------------------------------------------------------------------------- pessoas
def test_pessoas_criam_empresa_por_nome_e_atualizam_por_email(gestor, db):
    gestor.post("/nucleo/empresas", {"nome": "Aurora", "cidade": "Santos", "uf": "SP"})
    arq = _csv("Nome;Empresa;E-mail;Canal preferido;Usa endereço da empresa;Cidade",
               "Paula;Aurora;Paula@Aurora.com;Ligação;;",
               "Rafael;Vértice Nova;;WhatsApp;Não;Recife",
               "Camila;;;fax;;")
    d = _importar(gestor, "pessoas", arq).json()
    assert d["erros"] == [{"linha": 4, "coluna": "Canal preferido",
                           "mensagem": "Use uma das opções: E-mail, Ligação, WhatsApp."}]
    assert _contar(db, Empresa) == 1  # simulação não criou "Vértice Nova"
    arq = _csv("Nome;Empresa;E-mail;Canal preferido;Usa endereço da empresa;Cidade",
               "Paula;Aurora;Paula@Aurora.com;Ligação;;", "Rafael;Vértice Nova;;WhatsApp;Não;Recife")
    assert _importar(gestor, "pessoas", arq, simular=False).status_code == 200
    paula = db.query(Pessoa).filter_by(nome="Paula").one()
    assert (paula.email, paula.canal_preferido, paula.cidade, paula.usa_endereco_da_empresa) == (
        "paula@aurora.com", "ligacao", "Santos", True)
    rafael = db.query(Pessoa).filter_by(nome="Rafael").one()
    assert rafael.cidade == "Recife" and not rafael.usa_endereco_da_empresa
    assert db.query(Empresa).filter_by(nome="Vértice Nova").count() == 1
    d = _importar(gestor, "pessoas", _csv("Nome;E-mail;Cargo", "Paula Mendes;PAULA@aurora.com;Diretora"),
                  simular=False).json()
    assert d["atualizar"] == 1 and _contar(db, Pessoa) == 2
    assert db.get(Pessoa, paula.id).nome == "Paula Mendes"


# ------------------------------------------------------------------------------------------------- produtos
def test_produtos(gestor, db):
    db.add(Produto(nome="Consultoria", tipo="servico", codigo="CONS"))
    db.commit()
    arq = _csv("Nome;Tipo;Código;Preço de referência;Recorrente",
               "Consultoria estratégica;Serviço;CONS;24.000,00;Não",
               "Licença;Produto;;199,90;Sim",
               "Sem tipo;;;;",
               "Negativo;Produto;;-1;")
    d = _importar(gestor, "produtos", arq).json()
    assert (d["criar"], d["atualizar"]) == (1, 1)
    assert {(e["linha"], e["coluna"]) for e in d["erros"]} == {(4, "Tipo"), (5, "Preço de referência")}
    _importar(gestor, "produtos", _csv(*arq.decode("utf-8-sig").splitlines()[:3]), simular=False)
    cons = db.query(Produto).filter_by(codigo="CONS").one()
    assert cons.nome == "Consultoria estratégica" and cons.preco_referencia == Decimal("24000.00")
    assert db.query(Produto).filter_by(nome="Licença").one().recorrente is True


# ------------------------------------------------------------------------------------------------- financeiros
def test_categorias_com_superior(financeiro, db):
    arq = _csv("Nome;Natureza;Categoria superior", "Despesas fixas;Despesa;", "Aluguel;despesa;Despesas fixas",
               "Serviços;Receita;Inexistente")
    d = _importar(financeiro, "categorias", arq).json()
    assert d["criar"] == 2 and d["erros"][0]["linha"] == 4 and d["erros"][0]["coluna"] == "Categoria superior"
    _importar(financeiro, "categorias", _csv("Nome;Natureza;Categoria superior", "Despesas fixas;Despesa;",
                                             "Aluguel;despesa;Despesas fixas"), simular=False)
    aluguel = db.query(Categoria).filter_by(nome="Aluguel").one()
    assert db.get(Categoria, aluguel.superior_id).nome == "Despesas fixas"
    d = _importar(financeiro, "categorias", _csv("Nome;Natureza", "aluguel;Despesa")).json()
    assert d["ignorar"] == 1


def test_centros_e_contas(financeiro, db, admin):
    d = _importar(financeiro, "centros-custo", _csv("Código;Nome;Responsável", "op;Operação;admin", "MKT;;",
                                                    "TI;Tecnologia;fulano"), simular=False)
    assert d.status_code == 400
    assert {(e["linha"], e["coluna"]) for e in d.json()["erros"]} == {(3, "Nome"), (4, "Responsável")}
    _importar(financeiro, "centros-custo", _csv("Código;Nome;Responsável", "op;Operação;admin"), simular=False)
    assert db.query(CentroCusto).one().codigo == "OP" and db.query(CentroCusto).one().responsavel_id == admin.id

    contas = _csv("Nome;Instituição;Saldo inicial;Data-base", "Conta operacional;Banco;25.000,00;01/11/2026",
                  "Caixa;;;")
    d = _importar(financeiro, "contas", contas).json()
    assert d["erros"] == [{"linha": 3, "coluna": "Saldo inicial", "mensagem": "Informe o saldo inicial."}]
    _importar(financeiro, "contas", _csv(*contas.decode("utf-8-sig").splitlines()[:2]), simular=False)
    conta = db.query(ContaFinanceira).one()
    assert conta.saldo_inicial == Decimal("25000.00") and conta.data_base == date(2026, 11, 1)
    # com movimento, o saldo inicial não muda pela planilha
    e = Empresa(nome="Cliente", campos_custom={})
    db.add(e)
    db.flush()
    t = Titulo(direcao="receber", empresa_id=e.id, descricao="x", vencimento=date(2026, 11, 20),
               valor_original=Decimal("10"), saldo=Decimal("0"), responsavel_id=admin.id, status="liquidado")
    db.add(t)
    db.flush()
    db.add(Baixa(titulo_id=t.id, conta_id=conta.id, valor=Decimal("10"), data=date(2026, 11, 5),
                 forma="pix", registrada_por_id=admin.id))
    db.commit()
    d = _importar(financeiro, "contas", _csv("Nome;Saldo inicial", "Conta operacional;1,00")).json()
    assert d["erros"][0]["coluna"] == "Saldo inicial"


# ------------------------------------------------------------------------------------------------- permissões
def test_permissoes_por_objeto(comercial, financeiro, leitura, sem_acesso):
    arq = _csv("Nome;Natureza", "X;Receita")
    assert _importar(comercial, "categorias", arq).status_code == 403  # Comercial não tem financeiro.cadastros
    assert comercial.get("/nucleo/planilhas/contas/modelo").status_code == 403
    assert _importar(comercial, "empresas", _csv("Nome", "X")).status_code == 200
    assert _importar(financeiro, "categorias", arq).status_code == 200
    assert leitura.get("/nucleo/planilhas/empresas/modelo").status_code == 200
    assert _importar(leitura, "empresas", _csv("Nome", "X")).status_code == 403  # importar = editar
    assert sem_acesso.get("/nucleo/planilhas/empresas/modelo").status_code == 403
    assert _importar(comercial, "oportunidades", arq).status_code == 404
