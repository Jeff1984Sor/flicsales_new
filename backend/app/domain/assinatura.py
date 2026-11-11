"""Assinatura de e-mail (funções puras, sem banco).

Regra: e-mail enviado POR um usuário (comunicações, cobranças, propostas) usa a assinatura dele (texto e/ou imagem);
sem assinatura própria, cai na assinatura padrão da Identidade. E-mails do sistema (senha, convite) usam a da
Identidade. A imagem vai embutida no HTML como CID (`<img src="cid:assinatura">`).
"""

import html as _html
from dataclasses import dataclass

CID_IMAGEM = "assinatura"
LIMITE_TEXTO = 4000
SEPARADOR = "-- "  # convenção de assinatura em texto puro


@dataclass(frozen=True)
class Assinatura:
    texto: str | None
    com_imagem: bool  # True = usar a imagem do usuário
    origem: str  # "usuario" | "identidade" | "nenhuma"


def _limpo(texto: str | None) -> str | None:
    t = (texto or "").strip()
    return t or None


def escolher(*, texto_usuario: str | None, tem_imagem_usuario: bool, texto_identidade: str | None,
             do_sistema: bool = False) -> Assinatura:
    """Qual assinatura usar. `do_sistema`: e-mail do sistema (ignora a do usuário)."""
    if not do_sistema and (_limpo(texto_usuario) or tem_imagem_usuario):
        return Assinatura(_limpo(texto_usuario), tem_imagem_usuario, "usuario")
    if _limpo(texto_identidade):
        return Assinatura(_limpo(texto_identidade), False, "identidade")
    return Assinatura(None, False, "nenhuma")


def aplicar(corpo: str, html: str | None, assinatura: Assinatura) -> tuple[str, str | None]:
    """Acrescenta a assinatura ao corpo em texto e ao HTML. Sem HTML mas com imagem, gera um HTML simples a partir do
    texto (escapado) para poder embutir a imagem. Devolve (corpo, html)."""
    if assinatura.origem == "nenhuma":
        return corpo, html
    if assinatura.texto:
        corpo = f"{corpo.rstrip()}\n\n{SEPARADOR}\n{assinatura.texto}"
    if html is None and not assinatura.com_imagem:
        return corpo, None
    if html is None:
        base = _html.escape(corpo if not assinatura.texto else corpo.rsplit(f"\n\n{SEPARADOR}\n", 1)[0])
        html = f"<div>{base.replace(chr(10), '<br>')}</div>"
    partes = []
    if assinatura.texto:
        partes.append(f"<div>{_html.escape(assinatura.texto).replace(chr(10), '<br>')}</div>")
    if assinatura.com_imagem:
        partes.append(f'<div><img src="cid:{CID_IMAGEM}" alt="Assinatura" style="max-width:480px"></div>')
    bloco = '<div class="assinatura" style="margin-top:16px">' + "".join(partes) + "</div>"
    if "</body>" in html:
        html = html.replace("</body>", bloco + "</body>", 1)
    else:
        html = html + bloco
    return corpo, html
