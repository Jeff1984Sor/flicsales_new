"""Documento do cadastro de empresa/fornecedor: só CNPJ ou CPF válidos, com máscara, sem duplicar."""

import pytest

from app.domain import RegraViolada
from app.domain.cadastro import formas_do_documento, validar_documento_cadastro, validar_documento_livre


def test_aceita_cnpj_e_cpf_validos_e_mascara():
    assert validar_documento_cadastro("11222333000181") == "11.222.333/0001-81"
    assert validar_documento_cadastro(" 11.222.333/0001-81 ") == "11.222.333/0001-81"
    assert validar_documento_cadastro("52998224725") == "529.982.247-25"
    assert validar_documento_cadastro("529.982.247-25") == "529.982.247-25"
    assert validar_documento_cadastro(None) is None and validar_documento_cadastro("  ") is None


@pytest.mark.parametrize("doc", ["11.222.333/0001-82", "11111111111111", "529.982.247-26", "111.111.111-11", "123",
                                 "abc", "112223330001810"])
def test_recusa_invalido(doc):
    with pytest.raises(RegraViolada, match=r"^CNPJ ou CPF inválido\.$"):
        validar_documento_cadastro(doc)


def test_documento_duplicado_diz_qual_empresa():
    validar_documento_livre("11.222.333/0001-81", [(2, "Outra", "52998224725"), (3, "Sem doc", None)])
    validar_documento_livre(None, [(2, "Outra", "11222333000181")])
    with pytest.raises(RegraViolada, match=r"“Aurora” \(#7\)"):
        validar_documento_livre("11.222.333/0001-81", [(7, "Aurora", "11222333000181")])
    with pytest.raises(RegraViolada, match="Este CPF"):
        validar_documento_livre("529.982.247-25", [(8, "Paula ME", "529.982.247-25")])
    assert formas_do_documento("11.222.333/0001-81") == ("11.222.333/0001-81", "11222333000181")
