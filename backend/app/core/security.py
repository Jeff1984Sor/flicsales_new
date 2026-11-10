"""Hash de senha (Argon2) e tokens JWT. Cifra de segredos fica em `app.core.segredos`."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_hasher = PasswordHash.recommended()

TokenTipo = Literal["access", "refresh", "primeiro"]


def hash_senha(senha: str) -> str:
    return _hasher.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return _hasher.verify(senha, senha_hash)
    except Exception:
        return False


@lru_cache
def _hash_falso() -> str:
    return hash_senha(secrets.token_urlsafe(12))


def gastar_tempo_de_verificacao(senha: str) -> None:
    """Conta inexistente também paga o custo do Argon2: o tempo de resposta não revela se ela existe."""
    verificar_senha(senha, _hash_falso())


def criar_token(sub: str, tipo: TokenTipo, extra: dict[str, Any] | None = None) -> str:
    """No modo um banco por organização, todo token leva a organização atual na claim `org` (app.core.tenancy)."""
    from app.core import tenancy

    duracao = {
        "access": timedelta(minutes=settings.jwt_access_minutes),
        "refresh": timedelta(days=settings.jwt_refresh_days),
        "primeiro": timedelta(days=7),  # boas-vindas: quem contratou cria o Gestor da organização nova
    }[tipo]
    now = datetime.now(UTC)
    payload = {"sub": sub, "typ": tipo, "iat": now, "exp": now + duracao, "jti": secrets.token_hex(16)}
    payload.update(tenancy.claims())
    payload.update(extra or {})
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decodificar_token(token: str, tipo: TokenTipo) -> dict[str, Any]:
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "typ", "jti"]}
    )
    if payload.get("typ") != tipo:
        raise jwt.InvalidTokenError("tipo de token inválido")
    return payload


def hash_token(valor: str) -> str:
    """Digest de tokens/códigos de uso único guardados no banco (nunca o valor em claro)."""
    return hmac.new(settings.jwt_secret.encode(), valor.encode(), hashlib.sha256).hexdigest()


def validar_politica_senha(senha: str) -> str | None:
    if len(senha) < 8:
        return "A senha precisa ter pelo menos 8 caracteres."
    if len(senha) > 128:
        return "A senha pode ter no máximo 128 caracteres."
    if senha.isdigit() or senha.isalpha():
        return "Use letras e números na senha."
    return None
