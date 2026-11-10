"""Regras puras: sem banco. Anula o fixture autouse que recria as tabelas a cada teste."""

import pytest


@pytest.fixture(autouse=True)
def _banco_limpo():
    yield
