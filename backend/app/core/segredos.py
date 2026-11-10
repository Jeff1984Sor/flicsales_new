"""Cifra de segredos guardados no banco (senha SMTP, chave de IA, tokens de integração) com Fernet/MASTER_KEY.

Suporta rotação: defina MASTER_KEY_ANTERIOR com a chave velha, rode `recifrar` nos registros e depois retire-a.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings


def _fernet() -> MultiFernet:
    chaves = [Fernet(settings.master_key.encode())]
    if settings.master_key_anterior:
        chaves.append(Fernet(settings.master_key_anterior.encode()))
    return MultiFernet(chaves)


class SegredoInvalido(Exception):
    """Dado cifrado com outra chave ou corrompido."""


def cifrar(dados: bytes) -> bytes:
    return _fernet().encrypt(dados)


def decifrar(dados: bytes) -> bytes:
    try:
        return _fernet().decrypt(dados)
    except InvalidToken:
        raise SegredoInvalido("Não foi possível decifrar o segredo (MASTER_KEY diferente da usada para cifrar).") from None


def cifrar_texto(texto: str) -> bytes:
    return cifrar(texto.encode())


def decifrar_texto(dados: bytes) -> str:
    return decifrar(dados).decode()


def recifrar(dados: bytes) -> bytes:
    """Recifra com a chave atual (para o fim de uma rotação de MASTER_KEY)."""
    return _fernet().rotate(dados)


def mascarar(texto: str | None, visiveis: int = 4) -> str | None:
    """Mostra só o final de um segredo (conferência na tela)."""
    return None if not texto else "•" * 6 + texto[-visiveis:]
