"""Descobre a organização de cada pedido (HTTP e WebSocket) quando há um banco por organização. Portado do MayaFit
(app/core/estudio_http.py).

Ordem: o token (cabeçalho Authorization ou ?token=, que o SSE, o WebSocket e os links usam) e, sem token com
organização, o endereço: `X-Forwarded-Host` (o BFF do Next repassa o host original) e depois `Host`. Sem nenhum dos
dois o pedido segue sem organização: só o login (que procura no catálogo de logins) e as rotas que leem a organização
de um token no corpo (refresh, redefinir senha) funcionam assim; qualquer acesso ao banco vira 401 "Sessão expirada"
(tenancy.OrganizacaoNaoIdentificada).

Também confere o Host (substitui o TrustedHostMiddleware): vale o que estiver em ALLOWED_HOSTS (aceita `*.dominio`)
e, no modo multi, qualquer domínio cadastrado no controle.
"""

import contextvars
from urllib.parse import parse_qs

import anyio
import jwt
from starlette.responses import PlainTextResponse

from app.core import tenancy
from app.core.config import settings
from app.core.tenancy import Organizacao

# o pedido veio pelo endereço de uma organização que não pode entrar (inativa): o login não cai no catálogo
_endereco_bloqueado: contextvars.ContextVar[bool] = contextvars.ContextVar("endereco_bloqueado", default=False)


def endereco_bloqueado() -> bool:
    return _endereco_bloqueado.get()


def organizacao_do_token(token: str | None) -> Organizacao | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        return None
    slug = payload.get(tenancy.CLAIM)
    if not slug or not isinstance(slug, str):
        return None
    from app.controle import service

    return service.por_slug(slug)


def definir_pelo_token(token: str | None) -> Organizacao | None:
    """Para os tokens que chegam no corpo (refresh). Sem multi, não faz nada."""
    if not tenancy.multi():
        return None
    org = organizacao_do_token(token)
    if org is not None:
        tenancy.definir(org)
    return org


def _cabecalhos(scope) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}


def host_do_pedido(headers: dict[str, str]) -> str:
    """O endereço que a pessoa abriu: o BFF repassa em X-Forwarded-Host; direto na API, o Host."""
    return (headers.get("x-forwarded-host") or headers.get("host") or "").split(",")[0].strip()


def _identificar(scope) -> tuple[Organizacao | None, bool]:
    """(organização, endereço de organização inativa?)."""
    from app.controle import service

    headers = _cabecalhos(scope)
    auth = headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else None
    if not token:
        token = (parse_qs(scope.get("query_string", b"").decode()).get("token") or [None])[0]
    org = organizacao_do_token(token)
    bloqueado = False
    if org is None and (host := host_do_pedido(headers)):
        org = service.por_host(host)
        bloqueado = org is None and service.host_conhecido(host)
    return org, bloqueado


def _host_permitido(host: str, permitidos: list[str]) -> bool:
    for p in permitidos:
        if p == "*" or p == host or (p.startswith("*.") and host.endswith(p[1:])):
            return True
    return False


def host_aceito(host_bruto: str) -> bool:
    """ALLOWED_HOSTS (com `*.dominio`) ou, no modo multi, um domínio cadastrado no controle."""
    from app.controle.service import normalizar_host

    host = normalizar_host(host_bruto)
    if _host_permitido(host, settings.allowed_hosts):
        return True
    if not tenancy.multi() or not host:
        return False
    from app.controle import service

    return service.host_conhecido(host)


class OrganizacaoMiddleware:
    """Confere o Host e define a organização do pedido (ContextVar) enquanto ele roda."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        host = _cabecalhos(scope).get("host", "")
        if not _host_permitido(host.split(":")[0].lower(), settings.allowed_hosts):
            if not await anyio.to_thread.run_sync(host_aceito, host):
                if scope["type"] == "http":
                    await PlainTextResponse("Invalid host header", status_code=400)(scope, receive, send)
                else:  # websocket: fecha sem aceitar
                    await send({"type": "websocket.close", "code": 1008})
                return
        if not tenancy.multi():
            await self.app(scope, receive, send)
            return
        org, bloqueado = await anyio.to_thread.run_sync(_identificar, scope)  # consulta o controle (com cache)
        token = tenancy.definir(org)
        marca = _endereco_bloqueado.set(bloqueado)
        try:
            await self.app(scope, receive, send)
        finally:
            _endereco_bloqueado.reset(marca)
            tenancy.resetar(token)
