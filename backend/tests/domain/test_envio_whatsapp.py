"""WhatsApp (contrato proposta + WhatsApp 11/2026, parte B): regras puras de app.domain.envio."""

from datetime import date

import pytest

from app.domain import RegraViolada
from app.domain import envio as e


@pytest.mark.parametrize("entrada, saida", [
    ("(11) 99999-0000", "5511999990000"),
    ("11999990000", "5511999990000"),
    ("+55 11 99999-0000", "5511999990000"),
    ("55 (11) 99999-0000", "5511999990000"),
    ("(11) 3333-4444", "551133334444"),
    ("011 3333-4444", "551133334444"),
    ("+1 (415) 555-0100", "14155550100"),  # estrangeiro só com "+"
])
def test_normalizar_whatsapp(entrada, saida):
    assert e.normalizar_whatsapp(entrada) == saida


@pytest.mark.parametrize("entrada", ["", None, "abc", "12345", "(11) 89999-0000", "(10) 99999-0000",
                                     "+55 11 9999", "1199999000011223"])
def test_normalizar_whatsapp_recusa(entrada):
    with pytest.raises(RegraViolada, match="Telefone inválido para WhatsApp"):
        e.normalizar_whatsapp(entrada)


def test_validar_mensagem_whatsapp_normaliza_e_tira_repetidos():
    m = e.validar_mensagem_whatsapp(para=["(11) 99999-0000", "+55 11 99999-0000", " ", "21 98888-7777"],
                                    texto="  Olá!  ")
    assert m.para == ["5511999990000", "5521988887777"] and m.texto == "Olá!"


@pytest.mark.parametrize("kw, msg", [
    ({"para": []}, "ao menos um telefone"),
    ({"para": ["123"]}, "Telefone inválido"),
    ({"para": [f"11 9{i:04d}-0000" for i in range(11)]}, "no máximo 10"),
    ({"texto": "  "}, "Escreva a mensagem"),
    ({"texto": "a" * 4001}, "4000 caracteres"),
])
def test_validar_mensagem_whatsapp_recusa(kw, msg):
    base = {"para": ["11 99999-0000"], "texto": "Oi"}
    with pytest.raises(RegraViolada, match=msg):
        e.validar_mensagem_whatsapp(**{**base, **kw})


def test_assinatura_curta():
    assert e.assinar_whatsapp("Olá", "Marina Costa") == "Olá\n\n— Marina Costa"
    assert e.assinar_whatsapp("Olá\n\n— Marina Costa", "Marina Costa") == "Olá\n\n— Marina Costa"  # não repete
    assert e.assinar_whatsapp("Olá", "  ") == "Olá"


CONTATOS = [
    e.Contato("Paula Mendes", ("paula@x.com",), ("opt_out",), ("(11) 99999-0000", "11 3333-4444")),
    e.Contato("Rui Lima", (), ("opt_out",), ("21 98888-7777",)),
    e.Contato("Ana Livre", (), ("email",), ("31 97777-6666",)),
]


def test_opt_out_por_telefone_compara_normalizado():
    assert e.telefones_bloqueados(["+55 (11) 99999-0000", "31977776666"], CONTATOS) == [
        ("5511999990000", "Paula Mendes")]
    with pytest.raises(RegraViolada, match=r"^Paula Mendes pediu para não receber comunicações \(opt-out\)\."):
        e.conferir_opt_out_telefones(["5511999990000"], CONTATOS)
    with pytest.raises(RegraViolada, match="Paula Mendes e Rui Lima pediram"):
        e.conferir_opt_out_telefones(["5511999990000", "5521988887777"], CONTATOS)
    e.conferir_opt_out_telefones(["31 97777-6666", "41 96666-5555"], CONTATOS)  # sem opt-out / sem cadastro passa


def test_filtrar_opt_out_telefones_para_envio_automatico():
    liberados, pulados = e.filtrar_opt_out_telefones(["11 99999-0000", "31 97777-6666", "lixo", "31977776666"],
                                                     CONTATOS)
    assert liberados == ["5531977776666"] and pulados == [("5511999990000", "Paula Mendes")]


def test_textos_registrados():
    m = e.MensagemWhatsApp(para=["5511999990000", "551133334444"], texto="Oi\n\n— Fin")
    assert e.formatar_whatsapp("5511999990000") == "+55 (11) 99999-0000"
    assert e.formatar_whatsapp("551133334444") == "+55 (11) 3333-4444"
    assert e.conteudo_comunicacao_whatsapp(m) == "Para: +55 (11) 99999-0000, +55 (11) 3333-4444\n\nOi\n\n— Fin"
    assert e.linha_historico_cobranca_whatsapp(date(2026, 11, 11), m, "Fin") == (
        "11/11/2026 — WhatsApp enviado para +55 (11) 99999-0000, +55 (11) 3333-4444 por Fin")
