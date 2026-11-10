"""Arquivos do storage SÓ para usuários logados, com a permissão da categoria (ver core/storage.py)."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core import storage
from app.core.deps import Ctx

router = APIRouter(tags=["arquivos"])


@router.get("/arquivos/{caminho:path}")
def ler_arquivo(caminho: str, ctx: Ctx):
    try:
        cat = storage.categoria_do_caminho(caminho)
        destino = storage.resolver(caminho)
    except storage.ArquivoInvalido:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado.") from None
    if cat.permissao:
        ctx.exigir(cat.permissao)
    if not destino.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado.")
    return FileResponse(destino, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff",
                                          "Content-Security-Policy": "sandbox"})
