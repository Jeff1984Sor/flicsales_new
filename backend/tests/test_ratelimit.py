import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core import ratelimit
from app.core.ratelimit import LimiteMemoria, limitar
from tests.conftest import entrar


def test_janela_deslizante_em_memoria():
    lim = LimiteMemoria()
    assert [lim.registrar("k", 3, 10, agora_s=t) for t in (0, 1, 2)] == [None, None, None]
    espera = lim.registrar("k", 3, 10, agora_s=3)
    assert espera == pytest.approx(7)
    assert lim.registrar("outra", 3, 10, agora_s=3) is None  # chaves independentes
    # a primeira saiu da janela em t=10: abre uma vaga
    assert lim.registrar("k", 3, 10, agora_s=10.5) is None
    assert lim.registrar("k", 3, 10, agora_s=10.6) is not None


def _app_com_limite():
    a = FastAPI()

    @a.get("/x", dependencies=[Depends(limitar("teste", 3, 60))])
    def x():
        return {"ok": True}

    return a


def test_dependencia_devolve_429_com_retry_after():
    ratelimit.resetar()
    with TestClient(_app_com_limite()) as c:
        assert [c.get("/x").status_code for _ in range(3)] == [200, 200, 200]
        r = c.get("/x")
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) >= 1
        # IPs diferentes têm limites separados
        assert c.get("/x", headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 200


def test_backend_em_banco(db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "rate_limit_backend", "banco")
    a = FastAPI()
    from app.core.db import get_db

    @a.get("/y", dependencies=[Depends(limitar("banco", 2, 60))])
    def y():
        return {"ok": True}

    a.dependency_overrides[get_db] = lambda: db
    with TestClient(a) as c:
        assert [c.get("/y").status_code for _ in range(3)] == [200, 200, 429]
    from app.core.ratelimit import LimiteBanco

    assert LimiteBanco.limpar_antigos(db, mais_velhos_que_s=-10) == 2


def test_login_tem_rate_limit_por_ip(client, admin):
    codigos = [entrar(client, "admin", "errada1A").status_code for _ in range(6)]
    assert 429 not in codigos  # 5 falhas bloqueiam a conta (401), mas o IP ainda não estourou
    ratelimit.resetar()
    codigos = [client.post("/api/auth/login", json={"identificador": f"x{i}@a.com", "senha": "abc"}).status_code
               for i in range(25)]
    assert codigos[:20] == [401] * 20 and set(codigos[20:]) == {429}


def test_forgot_limita_por_conta_e_por_ip(client, admin, emails):
    codigos = [client.post("/api/auth/forgot", json={"identificador": "admin"}).status_code for _ in range(5)]
    assert codigos[:3] == [200, 200, 200]
    assert codigos[3] == 429  # 3 por hora por conta
    assert len(emails) == 3


def test_rate_limit_pode_ser_desligado_so_em_dev(monkeypatch):
    from app.core.config import Settings

    with pytest.raises(ValueError, match="RATE_LIMIT_ATIVO"):
        Settings(ambiente="hml", rate_limit_ativo=False, jwt_secret="x" * 40, master_key=_chave(), debug=False,
                 allowed_hosts=["hml.exemplo.com"], frontend_url="https://hml.exemplo.com", cors_origins=["https://hml.exemplo.com"])


def _chave() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()
