"""Ajustes do Núcleo, parte 2 (contrato 11/2026): vários telefones/e-mails, desconto e recorrência do produto,
campos de dados (sugestões, padrões, exibir na etapa, objeto produto), listas da governança, imagem da assinatura
da Identidade e e-mail financeiro fora da planilha-modelo."""

import io

from openpyxl import load_workbook

from app.core import email as mail
from app.core import storage
from app.core.models import Auditoria, Identidade
from app.modules.comercial.models import Etapa, Funil
from app.modules.nucleo.models import CampoCustom, Empresa, OpcaoLista, Pessoa, Produto
from tests.nucleo.test_planilhas import _importar

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


# ------------------------------------------------------------------------------------------------- pessoa
def test_pessoa_com_varios_telefones_e_emails(gestor, db):
    r = gestor.post("/nucleo/pessoas", {
        "nome": "Paula", "cargo": "Diretora",
        "telefones": [{"numero": "11 3333-4444", "tipo": "fixo"},
                      {"numero": "11988887777", "tipo": "whatsapp", "principal": True}],
        "emails": [{"email": "Paula@Aurora.com.br"}, {"email": "paula@gmail.com", "tipo": "pessoal"}]})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["telefone"] == "(11) 98888-7777" and p["email"] == "paula@aurora.com.br"  # espelham o principal
    assert [t["numero"] for t in p["telefones"]] == ["(11) 98888-7777", "(11) 3333-4444"]
    assert p["emails"][0] == {"email": "paula@aurora.com.br", "tipo": "comercial", "principal": True}
    # troca o principal pela lista
    r = gestor.patch(f"/nucleo/pessoas/{p['id']}", {"emails": [{"email": "paula@aurora.com.br"},
                                                                {"email": "paula@gmail.com", "principal": True}]})
    assert r.status_code == 200 and r.json()["email"] == "paula@gmail.com"
    # a busca acha pelo e-mail que não é o principal
    assert gestor.get("/nucleo/pessoas", params={"q": "aurora.com"}).json()["total"] == 1
    a = db.query(Auditoria).filter_by(acao="pessoa.alterar").one()
    assert a.depois_json["email"] == "paula@gmail.com"


def test_pessoa_contatos_validacao_e_cliente_antigo(gestor, comercial, sem_acesso, db):
    r = gestor.post("/nucleo/pessoas", {"nome": "X", "emails": [{"email": "a@b.com", "principal": True},
                                                                {"email": "c@d.com", "principal": True}]})
    assert r.status_code == 400 and "só um e-mail" in r.json()["detail"]
    r = gestor.post("/nucleo/pessoas", {"nome": "X", "emails": [{"email": "a@b.com"}, {"email": "A@b.com"}]})
    assert r.status_code == 400 and "repetido" in r.json()["detail"]
    r = gestor.post("/nucleo/pessoas", {"nome": "X", "telefones": [{"numero": "12"}]})
    assert r.status_code == 400 and "Telefone inválido" in r.json()["detail"]
    # tela antiga: só email/telefone → vira o principal da lista
    r = comercial.post("/nucleo/pessoas", {"nome": "Antigo", "email": "ant@x.com", "telefone": "1133334444"})
    assert r.status_code == 201
    p = r.json()
    assert p["emails"] == [{"email": "ant@x.com", "tipo": "comercial", "principal": True}]
    assert p["telefones"][0]["principal"] is True
    r = comercial.patch(f"/nucleo/pessoas/{p['id']}", {"email": "novo@x.com"})
    assert [e["email"] for e in r.json()["emails"]] == ["novo@x.com"]
    assert sem_acesso.post("/nucleo/pessoas", {"nome": "Y"}).status_code == 403
    assert gestor.patch("/nucleo/pessoas/999", {"emails": []}).status_code == 404


# ------------------------------------------------------------------------------------------------- produto
def test_produto_desconto_e_recorrencia(gestor, db):
    r = gestor.post("/nucleo/produtos", {"nome": "Suporte", "tipo": "servico", "preco_referencia": "1000",
                                         "desconto_tipo": "percentual", "desconto_valor": "10", "recorrente": True,
                                         "frequencia": "semanal", "intervalo": 2, "dias_semana": ["qua", "seg"]})
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["desconto_tipo"], p["desconto_valor"]) == ("percentual", "10.00")
    assert p["dias_semana"] == ["seg", "qua"] and p["recorrencia_texto"] == "A cada 2 semanas: seg, qua"
    # recorrente=false limpa a recorrência
    r = gestor.patch(f"/nucleo/produtos/{p['id']}", {"recorrente": False})
    assert r.json()["frequencia"] is None and r.json()["dias_semana"] == [] and r.json()["recorrencia_texto"] is None
    r = gestor.patch(f"/nucleo/produtos/{p['id']}", {"recorrente": True, "frequencia": "semestral", "intervalo": 3})
    assert r.json()["intervalo"] == 1 and r.json()["recorrencia_texto"] == "Semestral"
    # desconto em valor não passa do preço (nem quando o preço baixa)
    r = gestor.patch(f"/nucleo/produtos/{p['id']}", {"desconto_tipo": "valor", "desconto_valor": "900"})
    assert r.status_code == 200
    r = gestor.patch(f"/nucleo/produtos/{p['id']}", {"preco_referencia": "500"})
    assert r.status_code == 400 and "preço de referência" in r.json()["detail"]
    for corpo, msg in (({"desconto_tipo": "percentual", "desconto_valor": "120"}, "0 a 100"),
                       ({"desconto_tipo": None, "desconto_valor": "5"}, "tipo do desconto"),
                       ({"frequencia": "semanal", "dias_semana": []}, "ao menos um dia")):
        r = gestor.patch(f"/nucleo/produtos/{p['id']}", corpo)
        assert r.status_code == 400 and msg in r.json()["detail"], (corpo, r.text)
    assert gestor.patch(f"/nucleo/produtos/{p['id']}", {"frequencia": "quinzenal"}).status_code == 422
    assert gestor.patch("/nucleo/produtos/999", {"recorrente": False}).status_code == 404


def test_produto_campos_personalizados(gestor, comercial):
    r = gestor.post("/nucleo/campos", {"nome": "Garantia", "tipo": "texto", "objeto": "produto"})
    assert r.status_code == 201 and r.json()["objeto"] == "produto"
    p = gestor.post("/nucleo/produtos", {"nome": "Item", "tipo": "produto", "campos_custom": {"garantia": "12 meses"}})
    assert p.status_code == 201 and p.json()["campos_custom"] == {"garantia": "12 meses"}
    r = gestor.post("/nucleo/produtos", {"nome": "Outro", "tipo": "produto", "campos_custom": {"cor": "azul"}})
    assert r.status_code == 400 and "desconhecido" in r.json()["detail"]
    assert [c["slug"] for c in comercial.get("/nucleo/campos", params={"objeto": "produto"}).json()] == ["garantia"]


# ------------------------------------------------------------------------------------------------- campos de dados
def test_campos_sugeridos(gestor, comercial):
    sugestoes = gestor.get("/nucleo/campos/sugestoes", params={"objeto": "pessoa"}).json()
    assert {s["chave"] for s in sugestoes} == {"data_de_nascimento", "linkedin", "cpf", "departamento"}
    assert gestor.get("/nucleo/campos/sugeridos").json()  # sem objeto: todos
    r = gestor.post("/nucleo/campos/sugeridos/oportunidade/fonte_do_lead")
    assert r.status_code == 201, r.text
    assert r.json()["tipo"] == "lista" and "Indicação" in r.json()["opcoes"]
    nomes = [s["nome"] for s in gestor.get("/nucleo/campos/sugestoes", params={"objeto": "oportunidade"}).json()]
    assert "Fonte do lead" not in nomes  # já criada não aparece
    r = gestor.post("/nucleo/campos/sugeridos/oportunidade/fonte_do_lead")
    assert r.status_code == 400 and "já existe" in r.json()["detail"]
    assert gestor.post("/nucleo/campos/sugeridos/oportunidade/nao_existe").status_code == 404
    assert gestor.post("/nucleo/campos/sugeridos/titulo/cpf").status_code == 404
    assert comercial.post("/nucleo/campos/sugeridos/pessoa/cpf").status_code == 403  # só nucleo.campos.ver


def test_campos_padroes_configurar_e_exigir(gestor, comercial, sem_acesso, db):
    padroes = sem_acesso.get("/nucleo/campos/padroes", params={"objeto": "empresa"})
    assert padroes.status_code == 200  # livre para logados (os formulários usam)
    nome = next(c for c in padroes.json() if c["campo"] == "nome")
    assert nome["fixo"] and nome["obrigatorio"] and nome["visivel"]
    r = gestor.patch("/nucleo/campos/padroes/empresa/nome", {"obrigatorio": False})
    assert r.status_code == 400 and "sempre obrigatório" in r.json()["detail"]
    r = gestor.patch("/nucleo/campos/padroes/empresa/segmento", {"visivel": False, "obrigatorio": True})
    assert r.status_code == 400 and "visível" in r.json()["detail"]
    r = gestor.patch("/nucleo/campos/padroes/empresa/segmento", {"obrigatorio": True})
    assert r.status_code == 200 and r.json()["obrigatorio"] is True and r.json()["visivel"] is True
    assert db.query(Auditoria).filter_by(acao="campo_padrao.alterar").count() == 1
    assert gestor.patch("/nucleo/campos/padroes/empresa/inexistente", {"visivel": False}).status_code == 404
    assert comercial.patch("/nucleo/campos/padroes/empresa/porte", {"visivel": False}).status_code == 403
    # o servidor exige o obrigatório: criar sem → 400; alterar outro campo continua livre; apagar → 400
    r = gestor.post("/nucleo/empresas", {"nome": "Sem segmento"})
    assert r.status_code == 400 and "Segmento" in r.json()["detail"]
    e = gestor.post("/nucleo/empresas", {"nome": "Com segmento", "segmento": "Tecnologia"}).json()
    assert gestor.patch(f"/nucleo/empresas/{e['id']}", {"site": "https://x.com"}).status_code == 200
    r = gestor.patch(f"/nucleo/empresas/{e['id']}", {"segmento": ""})
    assert r.status_code == 400 and "Segmento" in r.json()["detail"]
    # pessoa e produto
    gestor.patch("/nucleo/campos/padroes/pessoa/email", {"obrigatorio": True})
    assert gestor.post("/nucleo/pessoas", {"nome": "Sem e-mail"}).status_code == 400
    assert gestor.post("/nucleo/pessoas", {"nome": "Com", "emails": [{"email": "a@b.com"}]}).status_code == 201
    gestor.patch("/nucleo/campos/padroes/produto/codigo", {"obrigatorio": True})
    r = gestor.post("/nucleo/produtos", {"nome": "Sem código", "tipo": "servico"})
    assert r.status_code == 400 and "Código" in r.json()["detail"]


def _funil(db):
    f = Funil(nome="Vendas")
    db.add(f)
    db.flush()
    etapas = [Etapa(funil_id=f.id, nome=n, ordem=i, probabilidade=10 * i) for i, n in enumerate(
        ("Entrada", "Proposta", "Fechamento"), 1)]
    db.add_all(etapas)
    db.commit()
    return f, etapas


def test_campo_exibir_na_etapa(gestor, db):
    f, (entrada, proposta, fechamento) = _funil(db)
    r = gestor.post("/nucleo/campos", {"nome": "Concorrente", "tipo": "texto", "objeto": "oportunidade",
                                       "exibir_etapa_id": proposta.id, "exigido_na_etapa_id": fechamento.id})
    assert r.status_code == 201, r.text
    c = r.json()
    assert (c["exibir_funil_id"], c["exibir_etapa_nome"], c["exibir_etapa_ordem"]) == (f.id, "Proposta", 2)
    assert c["visivel"] is True and c["criado_em"]
    r = gestor.patch(f"/nucleo/campos/{c['id']}", {"exigido_na_etapa_id": entrada.id})
    assert r.status_code == 400 and "anterior" in r.json()["detail"]
    r = gestor.patch(f"/nucleo/campos/{c['id']}", {"exibir_funil_id": None, "visivel": False, "ordem": 3})
    assert r.status_code == 200
    assert (r.json()["exibir_funil_id"], r.json()["exibir_etapa_id"], r.json()["visivel"]) == (None, None, False)
    r = gestor.post("/nucleo/campos", {"nome": "Setor", "tipo": "texto", "objeto": "empresa",
                                       "exibir_funil_id": f.id})
    assert r.status_code == 400 and "Só campos de oportunidade" in r.json()["detail"]


# ------------------------------------------------------------------------------------------------- listas
def test_listas_da_governanca(gestor, comercial, sem_acesso, db):
    db.add_all([OpcaoLista(tipo="porte", nome="ME", ordem=1), OpcaoLista(tipo="porte", nome="EPP", ordem=2)])
    db.commit()
    assert [o["nome"] for o in sem_acesso.get("/nucleo/listas/porte").json()] == ["ME", "EPP"]  # livre
    r = gestor.post("/nucleo/listas/porte", {"nome": "Grande"})
    assert r.status_code == 201 and r.json()["ordem"] == 3 and r.json()["criado_em"]
    r = gestor.post("/nucleo/listas/porte", {"nome": "grande"})
    assert r.status_code == 400 and "Já existe" in r.json()["detail"]
    gid = gestor.get("/nucleo/listas/porte").json()[2]["id"]
    assert gestor.patch(f"/nucleo/listas/porte/{gid}", {"nome": "Grande porte"}).json()["nome"] == "Grande porte"
    r = gestor.delete(f"/nucleo/listas/porte/{gid}")
    assert r.status_code == 200 and r.json()["ativo"] is False
    assert len(gestor.get("/nucleo/listas/porte").json()) == 2
    todos = gestor.get("/nucleo/listas/porte", params={"incluir_inativos": True}).json()
    assert len(todos) == 3
    ids = [o["id"] for o in reversed(todos)]
    r = gestor.post("/nucleo/listas/porte/reordenar", {"ids": ids})
    assert r.status_code == 200 and [o["id"] for o in r.json()] == ids
    r = gestor.post("/nucleo/listas/porte/reordenar", {"ids": ids[:2]})
    assert r.status_code == 400 and "não bate" in r.json()["detail"]
    assert gestor.get("/nucleo/listas/cor").status_code == 404
    assert gestor.patch("/nucleo/listas/segmento/1", {"nome": "x"}).status_code == 404  # id de outra lista
    assert comercial.post("/nucleo/listas/segmento", {"nome": "Varejo"}).status_code == 403
    acoes = {a.acao for a in db.query(Auditoria)}
    assert {"opcao_lista.criar", "opcao_lista.alterar", "opcao_lista.inativar", "opcao_lista.reordenar"} <= acoes


def test_seed_semeia_listas(db):
    from app.modules.nucleo.servico import garantir_listas_padrao

    db.add(Empresa(nome="Log", segmento="Logística"))
    db.commit()
    assert garantir_listas_padrao(db) > 0
    db.commit()
    assert garantir_listas_padrao(db) == 0  # idempotente
    segmentos = [o.nome for o in db.query(OpcaoLista).filter_by(tipo="segmento")]
    assert "Logística" in segmentos and "Consultoria" in segmentos
    assert [o.nome for o in db.query(OpcaoLista).filter_by(tipo="porte").order_by(OpcaoLista.ordem)] == [
        "ME", "EPP", "Médio", "Grande"]


# ------------------------------------------------------------------------------------------------- identidade
def test_assinatura_imagem_da_identidade(client, gestor, comercial, db):
    db.add(Identidade(id=1, nome_exibicao="Flic"))
    db.commit()
    assert comercial.get("/config/identidade/assinatura-imagem").status_code == 404
    assert comercial.post("/config/identidade/assinatura-imagem",
                          files={"arquivo": ("a.png", PNG, "image/png")}).status_code == 403
    r = gestor.post("/config/identidade/assinatura-imagem", files={"arquivo": ("a.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["assinatura_imagem_url"].startswith("/config/identidade/assinatura-imagem?v=")
    img = comercial.get("/config/identidade/assinatura-imagem")  # livre para logados
    assert img.status_code == 200 and img.content == PNG
    r = gestor.post("/config/identidade/assinatura-imagem", files={"arquivo": ("a.gif", b"GIF89a", "image/gif")})
    assert r.status_code == 400
    # e-mail sem assinatura própria cai na da Identidade, com a imagem
    db.expire_all()
    assert mail.enviar(["x@exemplo.com"], "Oi", "Corpo", db=db, assinar=True)
    import email
    from email import policy

    arq = sorted((storage.raiz() / "outbox").glob("*.eml"))[-1]
    msg = email.message_from_bytes(arq.read_bytes(), policy=policy.default)
    assert 'src="cid:assinatura"' in msg.get_body(("html",)).get_content()
    assert [p.get_content() for p in msg.walk() if p.get_content_type() == "image/png"] == [PNG]
    r = gestor.delete("/config/identidade/assinatura-imagem")
    assert r.status_code == 200 and r.json()["assinatura_imagem_url"] is None
    assert gestor.delete("/config/identidade/assinatura-imagem").status_code == 404
    assert db.query(Auditoria).filter_by(acao="identidade.assinatura_imagem").count() == 2


# ------------------------------------------------------------------------------------------------- planilhas
def _cabecalho(api, objeto):
    wb = load_workbook(io.BytesIO(api.get(f"/nucleo/planilhas/{objeto}/modelo").content))
    return [c.value for c in wb["Dados"][1]]


def test_planilha_modelo_sem_email_financeiro_mas_importa_coluna_antiga(gestor, db):
    assert "E-mail financeiro" not in _cabecalho(gestor, "empresas")
    assert "E-mail" not in _cabecalho(gestor, "fornecedores")
    conteudo = "﻿Nome;E-mail financeiro\nAntiga;fin@antiga.com\n".encode()
    r = _importar(gestor, "empresas", conteudo, simular=False)
    assert r.status_code == 200 and r.json()["erros"] == [] and r.json()["criar"] == 1
    assert db.query(Empresa).filter_by(nome="Antiga").one().email_financeiro == "fin@antiga.com"


def test_planilha_pessoas_contatos_adicionais_e_produtos_novos(gestor, db):
    cab = _cabecalho(gestor, "pessoas")
    assert "E-mails adicionais" in cab and "Telefones adicionais" in cab
    conteudo = ('﻿Nome,E-mail,E-mails adicionais,Telefone,Telefones adicionais\n'
                'Paula,paula@a.com,"p2@a.com; p3@a.com",11988887777,"1133334444"\n').encode()
    r = _importar(gestor, "pessoas", conteudo, simular=False)
    assert r.status_code == 200 and r.json()["erros"] == [], r.text
    p = db.query(Pessoa).filter_by(nome="Paula").one()
    assert [e["email"] for e in p.emails] == ["paula@a.com", "p2@a.com", "p3@a.com"] and p.email == "paula@a.com"
    assert [t["numero"] for t in p.telefones] == ["11988887777", "(11) 3333-4444"]

    assert {"Frequência", "Intervalo", "Dias da semana", "Tipo de desconto", "Desconto"} <= set(
        _cabecalho(gestor, "produtos"))
    conteudo = ("﻿Nome;Tipo;Recorrente;Frequência;Intervalo;Dias da semana;Tipo de desconto;Desconto\n"
                "Suporte;Serviço;Sim;Semanal;1;seg, qua;Percentual;5\n").encode()
    r = _importar(gestor, "produtos", conteudo, simular=False)
    assert r.status_code == 200 and r.json()["erros"] == [], r.text
    pr = db.query(Produto).filter_by(nome="Suporte").one()
    assert (pr.frequencia, pr.intervalo, pr.dias_semana, pr.desconto_tipo) == ("semanal", 1, ["seg", "qua"],
                                                                              "percentual")
    conteudo = "﻿Nome;Tipo;Tipo de desconto\nRuim;Serviço;Valor\n".encode()
    r = _importar(gestor, "produtos", conteudo)
    assert r.json()["erros"] and "valor do desconto" in r.json()["erros"][0]["mensagem"]
    assert db.query(CampoCustom).count() == 0
