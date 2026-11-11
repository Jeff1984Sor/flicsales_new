"""Envio de e-mail por usuário (contrato de envio 11/2026): regras puras de app.domain.envio."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain import RegraViolada
from app.domain import envio as e


def test_pode_receber_email():
    assert e.pode_receber_email(None) and e.pode_receber_email([]) and e.pode_receber_email(["email", "whatsapp"])
    assert not e.pode_receber_email(["opt_out"])


def test_validar_mensagem_normaliza_e_tira_repetidos():
    m = e.validar_mensagem(para=[" Paula@Aurora.com.br ", "paula@aurora.com.br", ""], cc=["PAULA@aurora.com.br", "b@x.com"],
                           assunto="  Proposta   v2 ", corpo="  Olá  ")
    assert m.para == ["paula@aurora.com.br"] and m.cc == ["b@x.com"]
    assert m.assunto == "Proposta v2" and m.corpo == "Olá"


@pytest.mark.parametrize("kw, msg", [
    ({"para": []}, "ao menos um destinatário"),
    ({"para": ["nao-e-email"]}, "E-mail inválido"),
    ({"cc": ["x@"]}, "E-mail inválido"),
    ({"assunto": "  "}, "assunto"),
    ({"assunto": "a" * 201}, "200 caracteres"),
    ({"corpo": ""}, "mensagem"),
    ({"para": [f"p{i}@x.com" for i in range(15)], "cc": [f"c{i}@x.com" for i in range(6)]}, "no máximo 20"),
])
def test_validar_mensagem_recusa(kw, msg):
    base = {"para": ["a@x.com"], "cc": [], "assunto": "Oi", "corpo": "Texto"}
    with pytest.raises(RegraViolada, match=msg):
        e.validar_mensagem(**{**base, **kw})


CONTATOS = [e.Contato("Paula Mendes", ("paula@aurora.com.br", "paula.pessoal@x.com"), ("opt_out",)),
            e.Contato("Rafael", ("rafael@vertice.com",), ("email",)),
            e.Contato("Camila", ("camila@h.com",), ("opt_out",))]


def test_opt_out_bloqueia_qualquer_email_da_pessoa():
    assert e.destinatarios_bloqueados(["rafael@vertice.com", "sem.cadastro@x.com"], CONTATOS) == []
    assert e.destinatarios_bloqueados(["PAULA.PESSOAL@x.com"], CONTATOS) == [("paula.pessoal@x.com", "Paula Mendes")]
    e.conferir_opt_out(["rafael@vertice.com"], CONTATOS)
    with pytest.raises(RegraViolada, match=r"^Paula Mendes pediu para não receber comunicações \(opt-out\)\."):
        e.conferir_opt_out(["rafael@vertice.com", "paula@aurora.com.br"], CONTATOS)
    with pytest.raises(RegraViolada, match="Paula Mendes e Camila pediram"):
        e.conferir_opt_out(["paula@aurora.com.br", "camila@h.com"], CONTATOS)


def test_envio_automatico_pula_opt_out():
    liberados, pulados = e.filtrar_opt_out(["rafael@vertice.com", "camila@h.com"], CONTATOS)
    assert liberados == ["rafael@vertice.com"] and pulados == [("camila@h.com", "Camila")]


def test_textos_registrados():
    m = e.validar_mensagem(para=["a@x.com"], cc=["b@x.com"], assunto="Lembrete", corpo="Corpo")
    assert e.conteudo_comunicacao(m) == "Para: a@x.com\nCc: b@x.com\n\nCorpo"
    linha = e.linha_historico_cobranca(date(2026, 11, 11), m, "Fin")
    assert linha == "11/11/2026 — E-mail enviado para a@x.com, b@x.com por Fin: Lembrete"
    assert e.acrescentar_historico("Antes\n", linha) == f"Antes\n{linha}"
    assert e.acrescentar_historico("", linha) == linha


@pytest.mark.parametrize("status, desconto, esperado", [
    ("rascunho", Decimal("0"), "enviada"),
    ("rascunho", Decimal("5"), "rascunho"),  # desconto sem aprovação interna: não muda
    ("aprovada_internamente", Decimal("5"), "enviada"),
    ("em_aprovacao", Decimal("5"), "em_aprovacao"),
    ("enviada", Decimal("0"), "enviada"),
    ("aceita", Decimal("0"), "aceita"),
    ("recusada", Decimal("0"), "recusada"),
])
def test_status_da_proposta_apos_envio(status, desconto, esperado):
    assert e.status_proposta_apos_envio(status, desconto) == esperado
