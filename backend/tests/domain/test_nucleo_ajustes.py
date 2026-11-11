"""Regras puras dos ajustes do Núcleo (11/2026): LGPD da pessoa, campos "multipla"/"link", lista branca da IA,
condição de automação sobre lista e assinatura de e-mail."""

import pytest

from app.domain import RegraViolada
from app.domain import assinatura as ass
from app.domain import enriquecimento as enr
from app.domain import planilha as cel
from app.domain.automacao import condicao_ok
from app.domain.cadastro import aceita_envio_automatico, validar_base_legal, validar_permissoes_comunicacao
from app.modules.nucleo import regras
from app.modules.nucleo.regras import DefCampo, normalizar_valor, validar_campos_custom, validar_definicao_campo


# ------------------------------------------------------------------------------------------------- LGPD
def test_base_legal():
    assert validar_base_legal("consentimento") == "consentimento"
    assert validar_base_legal(" ") is None and validar_base_legal(None) is None
    with pytest.raises(RegraViolada, match="Base legal inválida"):
        validar_base_legal("porque sim")


def test_permissoes_comunicacao_ordem_repeticao_e_opt_out_exclusivo():
    assert validar_permissoes_comunicacao(None) == []
    assert validar_permissoes_comunicacao(["comercial_pontual", "whatsapp_telefone", "whatsapp_telefone"]) == [
        "whatsapp_telefone", "comercial_pontual"]
    assert validar_permissoes_comunicacao(["opt_out"]) == ["opt_out"]
    with pytest.raises(RegraViolada) as e:
        validar_permissoes_comunicacao(["opt_out", "email_marketing"])
    assert e.value.mensagem == "Opt-out não combina com outras permissões de comunicação."
    with pytest.raises(RegraViolada, match="desconhecida: sms"):
        validar_permissoes_comunicacao(["sms"])
    with pytest.raises(RegraViolada, match="como lista"):
        validar_permissoes_comunicacao("opt_out")


def test_envio_automatico_bloqueado_com_opt_out():
    assert aceita_envio_automatico(["email_marketing"]) and aceita_envio_automatico(None)
    assert not aceita_envio_automatico(["opt_out"])


# ------------------------------------------------------------------------------------------------- campos
MULTI = DefCampo(slug="canais", nome="Canais", tipo="multipla", opcoes=("E-mail", "Telefone", "Visita"))
LINK = DefCampo(slug="portal", nome="Portal", tipo="link")


def test_definicao_multipla_e_link():
    assert validar_definicao_campo(nome="C", tipo="multipla", objeto="empresa", opcoes=["A", " A", "B", ""]) == ["A", "B"]
    with pytest.raises(RegraViolada, match="seleção múltipla precisa de ao menos uma opção"):
        validar_definicao_campo(nome="C", tipo="multipla", objeto="empresa", opcoes=[])
    with pytest.raises(RegraViolada, match="não pode ter “;”"):
        validar_definicao_campo(nome="C", tipo="multipla", objeto="empresa", opcoes=["A;B"])
    assert validar_definicao_campo(nome="L", tipo="link", objeto="pessoa", opcoes=["x"]) == []
    assert regras.ROTULO_TIPO["multipla"] == "Seleção múltipla" and regras.ROTULO_TIPO["link"] == "Hiperlink"


def test_valor_multipla():
    assert normalizar_valor(MULTI, ["Visita", "E-mail", "Visita"]) == ["E-mail", "Visita"]
    assert normalizar_valor(MULTI, "Telefone; E-mail") == ["E-mail", "Telefone"]
    assert normalizar_valor(MULTI, []) is None and normalizar_valor(MULTI, "") is None
    with pytest.raises(RegraViolada, match="“Fax” não é uma das opções"):
        normalizar_valor(MULTI, ["E-mail", "Fax"])
    with pytest.raises(RegraViolada, match="escolha uma ou mais"):
        normalizar_valor(MULTI, 3)


def test_valor_link():
    assert normalizar_valor(LINK, "https://aurora.com.br/portal?x=1") == "https://aurora.com.br/portal?x=1"
    assert normalizar_valor(LINK, "www.aurora.com.br") == "https://www.aurora.com.br"
    for ruim in ("javascript:alert(1)", "ftp://aurora.com.br", "não é link", "mailto:a@b.com"):
        with pytest.raises(RegraViolada, match="http:// ou https://"):
            normalizar_valor(LINK, ruim)


def test_obrigatorio_multipla_vazia_falta():
    d = DefCampo(slug="canais", nome="Canais", tipo="multipla", opcoes=("A",), obrigatorio=True)
    with pytest.raises(RegraViolada, match="Preencha o campo obrigatório: Canais"):
        validar_campos_custom([d], {"canais": []})
    assert validar_campos_custom([d], {"canais": ["A"]}) == {"canais": ["A"]}


def test_valor_corresponde_para_filtros():
    assert regras.valor_corresponde(["E-mail", "Visita"], "visita")
    assert not regras.valor_corresponde(["E-mail"], "Visita")
    assert regras.valor_corresponde("Alto", " alto ") and not regras.valor_corresponde(None, "x")


def test_planilha_lista_com_separador_proprio():
    opcoes = {"Aceita contato via WhatsApp / Telefone": "whatsapp_telefone", "Apenas pontual": "pontual"}
    assert cel.lista("Aceita contato via WhatsApp / Telefone; apenas pontual", opcoes, separadores=";") == [
        "whatsapp_telefone", "pontual"]


# ------------------------------------------------------------------------------------------------- IA
def test_lista_branca_ia_multipla_e_link():
    m = enr.campo_custom("canais", "Canais", "multipla", ["E-mail", "Telefone", "Visita, presencial"])
    link = enr.campo_custom("portal", "Portal", "link")
    assert (m.tipo, m.opcoes) == ("multipla", ("E-mail", "Telefone", "Visita, presencial"))
    assert link.tipo == "site" and link.opcoes == ()
    assert enr.normalizar(m, "telefone; e-mail") == ["E-mail", "Telefone"]
    assert enr.normalizar(m, ["Visita, presencial"]) == ["Visita, presencial"]
    assert enr.normalizar(m, "Visita, presencial") == ["Visita, presencial"]
    assert enr.normalizar(m, "['E-mail', 'Telefone']") == ["E-mail", "Telefone"]
    assert enr.normalizar(m, "E-mail; Fax") is None  # opção inexistente: a sugestão é descartada
    assert enr.normalizar(m, 5) is None
    assert enr.igual(m, ["Telefone", "E-mail"], ["E-mail", "Telefone"])
    assert not enr.igual(m, ["E-mail"], ["E-mail", "Telefone"])
    assert enr.normalizar(link, "aurora.com.br/portal") == "https://aurora.com.br/portal"
    assert enr.normalizar(link, "não é link") is None


def test_condicao_de_automacao_sobre_selecao_multipla():
    dados = {"canais": ["E-mail", "Visita"]}
    assert condicao_ok(dados, "canais", "igual", "visita")
    assert not condicao_ok(dados, "canais", "igual", "Telefone")
    assert condicao_ok(dados, "canais", "diferente", "Telefone")
    assert condicao_ok(dados, "canais", "preenchido", None)
    assert not condicao_ok({"canais": []}, "canais", "preenchido", None)


# ------------------------------------------------------------------------------------------------- assinatura
def test_escolher_assinatura():
    a = ass.escolher(texto_usuario="Marina\nComercial", tem_imagem_usuario=True, texto_identidade="Equipe")
    assert (a.texto, a.com_imagem, a.origem) == ("Marina\nComercial", True, "usuario")
    a = ass.escolher(texto_usuario="  ", tem_imagem_usuario=False, texto_identidade="Equipe")
    assert (a.texto, a.origem) == ("Equipe", "identidade")
    a = ass.escolher(texto_usuario="Marina", tem_imagem_usuario=True, texto_identidade="Equipe", do_sistema=True)
    assert (a.texto, a.com_imagem, a.origem) == ("Equipe", False, "identidade")
    assert ass.escolher(texto_usuario=None, tem_imagem_usuario=False, texto_identidade=None).origem == "nenhuma"


def test_aplicar_assinatura_texto_html_e_imagem():
    corpo, html = ass.aplicar("Olá", None, ass.Assinatura("Equipe <Flic>", False, "identidade"))
    assert corpo == "Olá\n\n-- \nEquipe <Flic>" and html is None
    corpo, html = ass.aplicar("Olá\nTudo bem?", None, ass.Assinatura("Marina", True, "usuario"))
    assert corpo.endswith("-- \nMarina")
    assert html.startswith("<div>Olá<br>Tudo bem?</div>") and 'src="cid:assinatura"' in html
    _, html = ass.aplicar("x", "<html><body><p>x</p></body></html>", ass.Assinatura("<b>M</b>", False, "usuario"))
    assert "&lt;b&gt;M&lt;/b&gt;" in html and html.endswith("</div></body></html>")
    assert ass.aplicar("x", None, ass.Assinatura(None, False, "nenhuma")) == ("x", None)
