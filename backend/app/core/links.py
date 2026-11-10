"""Link assinado com prazo (HMAC-SHA256 + expiração), para arquivos/PDFs públicos por link.

    token = assinar("arquivo", {"p": "recibos/2026/abc.pdf"}, validade_s=3600)
    dados = verificar(token, "arquivo")      # LinkInvalido se adulterado, expirado ou de outra finalidade

A chave é derivada do JWT_SECRET + finalidade: um token de uma finalidade não vale em outra.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.core.config import settings


class LinkInvalido(Exception):
    pass


class LinkExpirado(LinkInvalido):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _chave(finalidade: str) -> bytes:
    return hashlib.sha256(b"link-assinado:" + finalidade.encode() + b":" + settings.jwt_secret.encode()).digest()


def assinar(finalidade: str, dados: dict[str, Any], validade_s: int, *, agora_s: float | None = None) -> str:
    corpo = {"d": dados, "f": finalidade, "e": int((agora_s if agora_s is not None else time.time()) + validade_s)}
    bruto = _b64(json.dumps(corpo, separators=(",", ":"), sort_keys=True).encode())
    mac = _b64(hmac.new(_chave(finalidade), bruto.encode(), hashlib.sha256).digest())
    return f"{bruto}.{mac}"


def verificar(token: str, finalidade: str, *, agora_s: float | None = None) -> dict[str, Any]:
    try:
        bruto, mac = token.split(".", 1)
        esperado = _b64(hmac.new(_chave(finalidade), bruto.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, esperado):
            raise LinkInvalido("assinatura inválida")
        corpo = json.loads(_unb64(bruto))
    except LinkInvalido:
        raise
    except Exception:
        raise LinkInvalido("link malformado") from None
    if corpo.get("f") != finalidade:
        raise LinkInvalido("finalidade diferente")
    if (agora_s if agora_s is not None else time.time()) > corpo.get("e", 0):
        raise LinkExpirado("link expirado")
    return corpo["d"]
