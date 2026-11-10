"""Nomes dos bancos vêm do .env (BANCO_CONTROLE e BANCO_PREFIXO): o FlicSales OS não colide com bancos do flicsales
antigo no mesmo PostgreSQL e hml/prod coexistem."""

import pytest
from sqlalchemy import select

from app.core import tenancy
from app.core.config import Settings, settings
from tests.conftest import SENHA
from tests.tenancy.conftest import _apagar_bancos, controle_proprio


def test_padroes_nao_colidem_com_o_flicsales_antigo(monkeypatch):
    from app.controle import service

    # padrões do código, sem o .env do servidor (hml/prod têm nomes próprios lá)
    monkeypatch.setattr(settings, "banco_controle", Settings.model_fields["banco_controle"].default)
    monkeypatch.setattr(settings, "banco_prefixo", Settings.model_fields["banco_prefixo"].default)
    assert settings.banco_controle == "flicsalesos_controle" and tenancy.banco_controle() == "flicsalesos_controle"
    assert service.nome_do_banco("test") == "flicsalesos_test"
    assert service.nome_do_banco("acme-sul") == "flicsalesos_acme_sul"


def test_env_define_controle_e_prefixo(monkeypatch):
    monkeypatch.setenv("BANCO_CONTROLE", "flicsalesos_controle_hml")
    monkeypatch.setenv("BANCO_PREFIXO", "flicsalesos_hml_")
    s = Settings()
    assert (s.banco_controle, s.banco_prefixo) == ("flicsalesos_controle_hml", "flicsalesos_hml_")


@pytest.mark.parametrize("var,valor", [("BANCO_CONTROLE", "x; DROP"), ("BANCO_PREFIXO", "Maiuscula_"),
                                       ("BANCO_PREFIXO", "")])
def test_nome_invalido_e_recusado(monkeypatch, var, valor):
    monkeypatch.setenv(var, valor)
    with pytest.raises(ValueError, match=var):
        Settings()


def test_prefixo_do_env_e_respeitado_no_provisionamento(monkeypatch):
    from app.controle import service
    from app.controle.models import OrganizacaoCliente, SessaoControle

    monkeypatch.setattr(settings, "banco_prefixo", "flicsalesos_hml_")
    monkeypatch.setattr(settings, "banco_controle", "flicsalesos_controle_hml")
    assert tenancy.banco_controle() == "flicsalesos_controle_hml"
    # o deploy/instalar.sh lê `tenancy.BANCO_CONTROLE` e `service.nome_do_banco("x")[:-1]`
    assert tenancy.BANCO_CONTROLE == "flicsalesos_controle_hml"
    assert service.nome_do_banco("x")[:-1] == "flicsalesos_hml_"
    assert tenancy.url_do_banco(tenancy.banco_controle()).endswith("/flicsalesos_controle_hml.db")
    _apagar_bancos("delta")
    try:
        with controle_proprio():
            service.provisionar("delta", "Organização Delta", admin_email="ana@delta.com", admin_login="ana",
                                admin_senha=SENHA)
            with SessaoControle() as db:
                banco = db.scalar(select(OrganizacaoCliente.banco).where(OrganizacaoCliente.slug == "delta"))
            assert banco == "flicsalesos_hml_delta"
    finally:
        _apagar_bancos("delta")
