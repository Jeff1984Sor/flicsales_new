"""WhatsApp pela Evolution API v2 (servidor da organização). Contrato proposta + WhatsApp 11/2026, parte B.

- `Cliente`: fala com a Evolution (httpx, timeout 15 s, header `apikey`). Erros viram `ErroEvolution` com motivo
  curto em PT-BR, SEM a chave e sem a resposta crua do servidor. Testes trocam o transporte com
  `definir_transporte(httpx.MockTransport(...))` — nenhum teste chama a Evolution real.
- Configuração: a linha `Integracao(tipo="whatsapp")` com `provedor="evolution"`, `url`, `instancia` e a apikey em
  `segredo_cifrado` (somente escrita). `conta` guarda o número conectado (vem da Evolution no "Testar conexão").
- `NotificadorEvolution`: implementação do `Notificador` do core (código de recuperação de senha). Lê a configuração
  do banco da organização do pedido atual (a sessão segue `app.core.tenancy`).
"""

import base64
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import segredos
from app.core.db import SessionLocal, agora
from app.domain import RegraViolada
from app.modules.orquestracao.models import Integracao

log = logging.getLogger(__name__)

PROVEDOR = "evolution"
TIMEOUT_S = 15.0
INTEGRACAO_BAILEYS = "WHATSAPP-BAILEYS"
SEM_WHATSAPP = "Configure o WhatsApp em Núcleo › Integrações."
ESTADOS = {"open": "conectado", "connecting": "conectando", "close": "desconectado", "closed": "desconectado"}

_transporte: httpx.BaseTransport | None = None


def definir_transporte(t: httpx.BaseTransport | None) -> None:
    """Testes: injeta um transporte falso (httpx.MockTransport). None = rede de verdade."""
    global _transporte
    _transporte = t


class ErroEvolution(Exception):
    """Falha ao falar com a Evolution. `mensagem` é curta, em PT-BR e nunca contém a apikey."""

    def __init__(self, mensagem: str, status: int | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


@dataclass(frozen=True)
class Config:
    url: str
    apikey: str
    instancia: str | None = None


def validar_url(url: str | None) -> str:
    """URL da API: http(s), com servidor, sem barra no fim."""
    u = (url or "").strip().rstrip("/")
    partes = urlsplit(u)
    if partes.scheme not in ("http", "https") or not partes.netloc or " " in u:
        raise RegraViolada("Informe a URL da API do WhatsApp começando com http:// ou https:// "
                           "(ex.: https://evolution.suaempresa.com.br).")
    return u


def validar_instancia(instancia: str | None) -> str | None:
    v = (instancia or "").strip()
    if not v:
        return None
    if len(v) > 100 or not re.fullmatch(r"[\w.\- ]+", v):
        raise RegraViolada("Nome da instância inválido: use letras, números, ponto, hífen ou sublinhado.")
    return v


def _numero_do_jid(jid: Any) -> str | None:
    d = re.sub(r"\D", "", str(jid or "").split("@", 1)[0])
    return d or None


def estado_legivel(state: str | None) -> str:
    return ESTADOS.get((state or "").lower(), "desconectado")


class Cliente:
    def __init__(self, url: str, apikey: str) -> None:
        self._url = url.rstrip("/")
        self._apikey = apikey

    def _limpar(self, texto: str) -> str:
        """Tira a chave de qualquer texto que possa sair para tela/log."""
        t = " ".join(str(texto or "").split())
        if self._apikey:
            t = t.replace(self._apikey, "••••")
        return t[:150]

    def _detalhe(self, r: httpx.Response) -> str:
        try:
            dados = r.json()
        except ValueError:
            return ""
        msg: Any = None
        if isinstance(dados, dict):
            resp = dados.get("response")
            msg = (resp.get("message") if isinstance(resp, dict) else None) or dados.get("message") \
                or dados.get("error")
        if isinstance(msg, list):
            msg = "; ".join(str(m) for m in msg[:3])
        msg = self._limpar(msg) if msg else ""
        return f" ({msg})" if msg else ""

    def _pedir(self, metodo: str, caminho: str, corpo: dict[str, Any] | None = None) -> Any:
        try:
            with httpx.Client(base_url=self._url, timeout=TIMEOUT_S, transport=_transporte,
                              headers={"apikey": self._apikey}) as c:
                r = c.request(metodo, caminho, json=corpo)
        except httpx.TimeoutException:
            raise ErroEvolution("a API do WhatsApp não respondeu a tempo (15 s)") from None
        except httpx.HTTPError:
            raise ErroEvolution("não foi possível conectar à URL da API do WhatsApp") from None
        if r.status_code in (401, 403):
            raise ErroEvolution("a API key foi recusada pela Evolution", r.status_code)
        if r.status_code == 404:
            raise ErroEvolution("instância não encontrada na Evolution", 404)
        if r.status_code >= 400:
            raise ErroEvolution(f"a Evolution respondeu HTTP {r.status_code}{self._detalhe(r)}", r.status_code)
        try:
            return r.json()
        except ValueError:
            return None

    @staticmethod
    def _inst(instancia: str) -> str:
        return quote(instancia, safe="")

    def instancias(self) -> list[dict[str, Any]]:
        """[{nome, estado, numero}] (aceita o formato da v2 e o antigo da v1)."""
        dados = self._pedir("GET", "/instance/fetchInstances")
        saida: list[dict[str, Any]] = []
        for item in dados if isinstance(dados, list) else []:
            if not isinstance(item, dict):
                continue
            v1 = item.get("instance") if isinstance(item.get("instance"), dict) else None
            if v1 is not None:
                nome, state, jid = v1.get("instanceName"), v1.get("status") or v1.get("state"), v1.get("owner")
            else:
                nome = item.get("name") or item.get("instanceName")
                state = item.get("connectionStatus") or item.get("status")
                jid = item.get("ownerJid") or item.get("owner") or item.get("number")
            if nome:
                saida.append({"nome": str(nome), "estado": estado_legivel(state), "numero": _numero_do_jid(jid)})
        return saida

    def estado(self, instancia: str) -> str:
        """Estado cru da instância ("open", "close", "connecting")."""
        dados = self._pedir("GET", f"/instance/connectionState/{self._inst(instancia)}") or {}
        inst = dados.get("instance") if isinstance(dados.get("instance"), dict) else dados
        return str(inst.get("state") or "")

    def conectar(self, instancia: str) -> dict[str, Any]:
        dados = self._pedir("GET", f"/instance/connect/{self._inst(instancia)}") or {}
        return _qrcode(dados)

    def criar(self, instancia: str) -> dict[str, Any]:
        dados = self._pedir("POST", "/instance/create", {"instanceName": instancia,
                                                         "integration": INTEGRACAO_BAILEYS, "qrcode": True}) or {}
        return _qrcode(dados.get("qrcode") if isinstance(dados.get("qrcode"), dict) else dados)

    def enviar_texto(self, instancia: str, numero: str, texto: str) -> None:
        self._pedir("POST", f"/message/sendText/{self._inst(instancia)}", {"number": numero, "text": texto})

    def enviar_documento(self, instancia: str, numero: str, texto: str, nome: str, conteudo: bytes,
                         mime: str) -> None:
        self._pedir("POST", f"/message/sendMedia/{self._inst(instancia)}", {
            "number": numero, "mediatype": "document", "mimetype": mime,
            "media": base64.b64encode(conteudo).decode("ascii"), "fileName": nome, "caption": texto})


def _qrcode(dados: dict[str, Any]) -> dict[str, Any]:
    inst = dados.get("instance") if isinstance(dados.get("instance"), dict) else {}
    return {"base64": dados.get("base64") or None, "codigo_pareamento": dados.get("pairingCode") or None,
            "estado": estado_legivel(inst.get("state")) if inst.get("state") else None}


# ------------------------------------------------------------------------------------------------ configuração
def integracao(db: Session) -> Integracao | None:
    return db.scalar(select(Integracao).where(Integracao.tipo == "whatsapp"))


def apikey_salva(i: Integracao | None) -> str | None:
    if i is None or not i.segredo_cifrado:
        return None
    try:
        return segredos.decifrar_texto(i.segredo_cifrado)
    except segredos.SegredoInvalido:
        return None


def configurada(i: Integracao | None) -> bool:
    return bool(i and i.provedor == PROVEDOR and i.url and i.instancia and i.segredo_cifrado)


def config_de(i: Integracao | None, *, url: str | None = None, apikey: str | None = None) -> Config:
    """URL/apikey do formulário (se vieram) ou as salvas. Sem elas → RegraViolada com o que fazer."""
    u = validar_url(url) if (url or "").strip() else (i.url if i and i.url else None)
    k = (apikey or "").strip() or apikey_salva(i)
    if not u or not k:
        raise RegraViolada("Informe a URL e a API key da Evolution e salve antes de continuar.")
    return Config(url=u, apikey=k, instancia=i.instancia if i else None)


def conectada(db: Session) -> Config | None:
    """Config pronta para ENVIAR: Evolution configurada e com o último teste "conectado"."""
    i = integracao(db)
    if not configurada(i) or i.estado != "conectado":
        return None
    k = apikey_salva(i)
    return Config(url=i.url, apikey=k, instancia=i.instancia) if k else None


def cliente(cfg: Config) -> Cliente:
    return Cliente(cfg.url, cfg.apikey)


def saida(i: Integracao | None) -> dict[str, Any]:
    """GET /integracoes/whatsapp/evolution (sem a chave: só os 4 últimos caracteres)."""
    k = apikey_salva(i)
    return {"configurado": configurada(i), "provedor": i.provedor if i else None, "url": i.url if i else None,
            "instancia": i.instancia if i else None, "chave_final": segredos.mascarar(k),
            "estado": i.estado if i else "desconectado", "numero": i.conta if i else None,
            "testado_em": i.testado_em if i else None, "ultimo_erro": i.ultimo_erro if i else None}


def testar(i: Integracao) -> dict[str, Any]:
    """connectionState da instância: open → conectado (e guarda o número em `conta`); senão desconectado; falha →
    erro + último erro (sem a chave). Atualiza `i` e devolve {ok, estado, mensagem}."""
    i.testado_em = agora()
    i.aguardando_conector = False
    if not configurada(i):
        i.estado, i.ultimo_erro = "erro", "Informe a URL, a API key e a instância da Evolution."
        return {"ok": False, "estado": i.estado, "mensagem": i.ultimo_erro}
    c = cliente(config_de(i))
    try:
        state = c.estado(i.instancia)
    except ErroEvolution as e:
        i.estado, i.ultimo_erro = "erro", f"Não foi possível consultar a instância: {e.mensagem}."
        return {"ok": False, "estado": i.estado, "mensagem": i.ultimo_erro}
    if state.lower() != "open":
        i.estado, i.ultimo_erro, i.conectado_em = "desconectado", None, None
        return {"ok": False, "estado": i.estado,
                "mensagem": f"A instância “{i.instancia}” não está conectada ({state or 'sem estado'}). "
                            "Use “Conectar número (QR code)” e leia o código no WhatsApp do celular."}
    i.estado, i.ultimo_erro = "conectado", None
    i.conectado_em = i.conectado_em or agora()
    try:  # o número é cortesia: se a lista falhar, a conexão continua valendo
        numero = next((x["numero"] for x in c.instancias() if x["nome"] == i.instancia), None)
        if numero:
            i.conta = numero
    except ErroEvolution:
        pass
    return {"ok": True, "estado": i.estado,
            "mensagem": "WhatsApp conectado" + (f" pelo número {i.conta}." if i.conta else ".")}


def qrcode(i: Integracao) -> dict[str, Any]:
    """QR code / código de pareamento para conectar o número. Instância inexistente é criada antes."""
    if not (i.provedor == PROVEDOR and i.url and i.segredo_cifrado):
        raise RegraViolada("Salve a URL e a API key da Evolution antes de conectar o número.")
    if not i.instancia:
        raise RegraViolada("Informe o nome da instância antes de conectar o número.")
    c = cliente(config_de(i))
    try:
        try:
            r = c.conectar(i.instancia)
        except ErroEvolution as e:
            if e.status != 404:
                raise
            r = c.criar(i.instancia)
            if not r["base64"] and not r["codigo_pareamento"]:
                r = c.conectar(i.instancia)
    except ErroEvolution as e:
        i.ultimo_erro = f"Não foi possível gerar o QR code: {e.mensagem}."
        raise RegraViolada(i.ultimo_erro) from None
    if r.get("estado") == "conectado":
        return {"base64": None, "codigo_pareamento": None, "estado": "conectado",
                "mensagem": "Esta instância já está conectada. Use “Testar conexão”."}
    return {"base64": r["base64"], "codigo_pareamento": r["codigo_pareamento"], "estado": "conectando",
            "mensagem": "Abra o WhatsApp no celular › Aparelhos conectados › Conectar aparelho e leia o QR code. "
                        "Depois clique em “Testar conexão”."}


# ------------------------------------------------------------------------------------------------ envio
def enviar(cfg: Config, numero: str, texto: str, documento: tuple[str, bytes, str] | None = None) -> None:
    """Um envio (texto ou documento com legenda). Levanta ErroEvolution."""
    c = cliente(cfg)
    if documento is None:
        c.enviar_texto(cfg.instancia, numero, texto)
    else:
        nome, conteudo, mime = documento
        c.enviar_documento(cfg.instancia, numero, texto, nome, conteudo, mime)


class NotificadorEvolution:
    """Notificador do core (código de recuperação de senha) pela Evolution da organização do pedido atual."""

    def enviar_texto(self, telefone: str, texto: str) -> bool:
        try:
            with SessionLocal() as db:
                cfg = conectada(db)
        except Exception:  # noqa: BLE001 — sem banco/organização: não envia, não derruba o fluxo
            log.warning("WhatsApp (Evolution): não foi possível ler a configuração da organização.")
            return False
        if cfg is None:
            log.warning("WhatsApp (Evolution) não conectado: mensagem não enviada.")
            return False
        try:
            enviar(cfg, telefone, texto)
        except ErroEvolution as e:  # o texto (pode ter um código) nunca vai para o log
            log.warning("WhatsApp (Evolution) não enviou a mensagem: %s.", e.mensagem)
            return False
        return True
