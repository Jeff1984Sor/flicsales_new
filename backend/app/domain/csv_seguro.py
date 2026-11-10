"""Exportar CSV com segurança: separador `;`, BOM UTF-8 (Excel PT-BR abre certo) e células de TEXTO que começam com
`=`, `+`, `-`, `@` (ou tab/CR) neutralizadas com apóstrofo (injeção de fórmula)."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from app.domain import RegraViolada

PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")
BOM = "﻿"


def neutralizar(valor) -> str:
    """Converte para texto de célula. Números e datas saem formatados (pt-BR) e NÃO são neutralizados."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, Decimal | int):
        return str(valor).replace(".", ",")
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor)
    return "'" + texto if texto.startswith(PERIGOSOS) else texto


def gerar_csv(cabecalho: list[str], linhas: list[list]) -> bytes:
    """Bytes do arquivo (com BOM). Sem registros → RegraViolada("Sem registros para exportar")."""
    if not linhas:
        raise RegraViolada("Sem registros para exportar")
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow([neutralizar(c) for c in cabecalho])
    for linha in linhas:
        w.writerow([neutralizar(c) for c in linha])
    return (BOM + buf.getvalue()).encode("utf-8")
