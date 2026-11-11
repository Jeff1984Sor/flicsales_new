"""Evolution API FALSA para os testes de WhatsApp (httpx.MockTransport): nada sai da máquina.

Uso num arquivo de teste:

    @pytest.fixture
    def evo():
        with evolution_falsa.instalada() as f:
            yield f

`f.pedidos` guarda (método, caminho, apikey, corpo); `f.enviados` só os envios de mensagem.
`conectar(db)` grava a integração WhatsApp (Evolution) já conectada.
"""

import json
from contextlib import contextmanager
from typing import Any

import httpx

from app.core import segredos
from app.modules.orquestracao import evolution
from app.modules.orquestracao.models import Integracao

URL = "https://evo.exemplo.test"
CHAVE = "evo-chave-secreta-XYZ9"
INSTANCIA = "flic"
NUMERO = "5511900001111"


class EvolutionFalsa:
    def __init__(self) -> None:
        self.pedidos: list[tuple[str, str, str | None, Any]] = []
        self.estado = "open"
        self.instancia_existe = True
        self.status_envio = 201  # mude para simular falha no envio
        self.status_tudo: int | None = None  # força este status em qualquer rota (ex.: 401)
        self.erro_rede: type[Exception] | None = None

    @property
    def enviados(self) -> list[dict[str, Any]]:
        return [c for m, p, _k, c in self.pedidos if p.startswith("/message/")]

    def __call__(self, req: httpx.Request) -> httpx.Response:
        corpo = json.loads(req.content) if req.content else None
        caminho = req.url.path
        self.pedidos.append((req.method, caminho, req.headers.get("apikey"), corpo))
        if self.erro_rede is not None:
            raise self.erro_rede("falha simulada", request=req)
        if req.headers.get("apikey") != CHAVE:
            return httpx.Response(401, json={"status": 401, "error": "Unauthorized",
                                             "response": {"message": f"apikey {req.headers.get('apikey')} inválida"}})
        if self.status_tudo:
            return httpx.Response(self.status_tudo, json={"response": {"message": [f"erro com {CHAVE}"]}})
        if caminho == "/instance/fetchInstances":
            return httpx.Response(200, json=[
                {"name": INSTANCIA, "connectionStatus": self.estado, "ownerJid": f"{NUMERO}@s.whatsapp.net"},
                {"name": "outra", "connectionStatus": "close", "ownerJid": None}])
        if caminho == f"/instance/connectionState/{INSTANCIA}":
            if not self.instancia_existe:
                return httpx.Response(404, json={"response": {"message": ["instance does not exist"]}})
            return httpx.Response(200, json={"instance": {"instanceName": INSTANCIA, "state": self.estado}})
        if caminho == f"/instance/connect/{INSTANCIA}":
            if not self.instancia_existe:
                return httpx.Response(404, json={"response": {"message": ["instance does not exist"]}})
            return httpx.Response(200, json={"pairingCode": "WZYEH1YY", "code": "2@abc",
                                             "base64": "data:image/png;base64,iVBORw0KGgo="})
        if caminho == "/instance/create":
            self.instancia_existe = True
            return httpx.Response(201, json={"instance": {"instanceName": corpo["instanceName"], "status": "created"},
                                             "qrcode": {"pairingCode": "NOVO1234",
                                                        "base64": "data:image/png;base64,Tk9WTw=="}})
        if caminho.startswith("/message/send"):
            return httpx.Response(self.status_envio, json={"key": {"id": "MSG1"}} if self.status_envio < 400 else
                                  {"response": {"message": ["number not on whatsapp"]}})
        return httpx.Response(404, json={"error": "rota desconhecida"})


@contextmanager
def instalada():
    f = EvolutionFalsa()
    evolution.definir_transporte(httpx.MockTransport(f))
    try:
        yield f
    finally:
        evolution.definir_transporte(None)


def conectar(db, *, estado: str = "conectado", conta: str | None = NUMERO) -> Integracao:
    i = evolution.integracao(db) or Integracao(tipo="whatsapp", escopos=[])
    i.provedor, i.url, i.instancia = evolution.PROVEDOR, URL, INSTANCIA
    i.segredo_cifrado = segredos.cifrar_texto(CHAVE)
    i.estado, i.conta = estado, conta
    db.add(i)
    db.commit()
    return i
