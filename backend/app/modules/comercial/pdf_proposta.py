"""Desenho do PDF da proposta (fpdf2). Recebe um `DocumentoProposta` já montado (textos renderizados, valores do
cadastro) e devolve os bytes. Quem junta os dados do banco é `servico.gerar_pdf_proposta`.

Fonte padrão (Helvetica, latin-1): acentos do português cabem; travessão/aspas curvas são trocados (`_t`).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from io import BytesIO

from fpdf import FPDF

from app.domain.dinheiro import formatar_brl

INK = (11, 16, 32)
MUTED = (89, 101, 121)
LINHA = (200, 206, 216)
AMBER = (180, 83, 9)
PRIMARY = (0, 87, 217)


def _t(v) -> str:
    s = "" if v is None else str(v)
    for a, b in (("—", "-"), ("–", "-"), ("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"), ("…", "..."),
                 ("•", "-"), ("✧", "*")):
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def _rgb(hexa: str | None) -> tuple[int, int, int]:
    h = (hexa or "").lstrip("#")
    if len(h) in (6, 8):
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except ValueError:
            pass
    return PRIMARY


def _data(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "-"


def _qtd(q: Decimal) -> str:
    s = f"{q.normalize():f}" if q == q.to_integral() else f"{q:f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _pct(p: Decimal) -> str:
    return _qtd(Decimal(p)) + "%"


@dataclass
class DocumentoProposta:
    organizacao: str
    cor: str | None
    logo: bytes | None
    titulo: str
    versao: int
    emissao: date
    validade: date
    status: str
    rascunho: bool
    empresa_nome: str
    empresa_cnpj: str | None
    empresa_endereco: str | None
    contato_nome: str | None
    contato_email: str | None
    introducao: str | None
    escopo: str
    item_nome: str
    quantidade: Decimal
    preco_unitario: Decimal
    desconto_pct: Decimal
    total: Decimal
    mensalidade_adicional: Decimal
    condicao: str
    termos: str | None
    responsavel_nome: str | None
    responsavel_email: str | None
    rodape: str | None
    extras: dict = field(default_factory=dict)


class _PDF(FPDF):
    def __init__(self, doc: DocumentoProposta):
        super().__init__(format="A4")
        self.doc = doc

    def header(self):
        if not self.doc.rascunho:
            return
        # marca d'água diagonal (desenhada antes do conteúdo da página) + faixa no topo
        with self.local_context(text_color=(232, 236, 242)):
            self.set_font("Helvetica", "B", 54)
            with self.rotation(35, x=self.w / 2, y=self.h / 2):
                self.text(self.w / 2 - self.get_string_width("RASCUNHO") / 2, self.h / 2 + 8, "RASCUNHO")
        self.set_xy(self.l_margin, 4)
        self.set_fill_color(*AMBER)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 6, _t("RASCUNHO — não enviar"), align="C", fill=True)
        self.set_text_color(*INK)
        self.set_y(14)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 5, _t(f"{self.doc.organizacao} · {self.doc.titulo} · v{self.doc.versao} · "
                           f"página {self.page_no()}/{{nb}}"), align="C")
        self.set_text_color(*INK)


def _secao(pdf: FPDF, titulo: str, cor: tuple[int, int, int]) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*cor)
    pdf.cell(0, 5, _t(titulo.upper()), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINHA)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)
    pdf.set_text_color(*INK)


def _paragrafos(pdf: FPDF, texto: str | None, tamanho: int = 10) -> None:
    pdf.set_font("Helvetica", "", tamanho)
    for p in (texto or "").split("\n"):
        pdf.multi_cell(0, 5, _t(p) if p.strip() else "", new_x="LMARGIN", new_y="NEXT")


def desenhar(doc: DocumentoProposta) -> bytes:
    cor = _rgb(doc.cor)
    pdf = _PDF(doc)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(True, margin=16)
    pdf.set_title(_t(doc.titulo))
    pdf.set_author(_t(doc.organizacao))
    pdf.add_page()

    # ---- cabeçalho: logo + nome da organização / PROPOSTA COMERCIAL
    topo = pdf.get_y()
    x_texto = pdf.l_margin
    if doc.logo:
        try:
            pdf.image(BytesIO(doc.logo), x=pdf.l_margin, y=topo, h=14)
            x_texto = pdf.l_margin + 40
        except Exception:  # noqa: BLE001 — logo ilegível não impede o documento
            x_texto = pdf.l_margin
    pdf.set_xy(x_texto, topo)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*cor)
    pdf.cell(0, 7, _t(doc.organizacao), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(x_texto)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, "PROPOSTA COMERCIAL", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(max(pdf.get_y(), topo + 16))
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 8, _t(doc.titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, _t(f"Versão {doc.versao} · Emitida em {_data(doc.emissao)} · Válida até {_data(doc.validade)}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)

    # ---- cliente
    _secao(pdf, "Cliente", cor)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 5, _t(doc.empresa_nome), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for linha in (f"CNPJ/CPF: {doc.empresa_cnpj}" if doc.empresa_cnpj else None, doc.empresa_endereco,
                  ("Contato: " + doc.contato_nome + (f" · {doc.contato_email}" if doc.contato_email else ""))
                  if doc.contato_nome else None):
        if linha:
            pdf.multi_cell(0, 5, _t(linha), new_x="LMARGIN", new_y="NEXT")

    # ---- introdução e escopo
    if (doc.introducao or "").strip():
        _secao(pdf, "Apresentação", cor)
        _paragrafos(pdf, doc.introducao)
    _secao(pdf, "Escopo", cor)
    _paragrafos(pdf, doc.escopo)

    # ---- tabela de valores
    _secao(pdf, "Investimento", cor)
    larg = pdf.w - pdf.l_margin - pdf.r_margin
    cols = [("Produto / serviço", larg * 0.40, "L"), ("Qtd.", larg * 0.10, "R"), ("Valor unitário", larg * 0.18, "R"),
            ("Desconto", larg * 0.12, "R"), ("Total", larg * 0.20, "R")]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(245, 248, 255)
    for nome, w, al in cols:
        pdf.cell(w, 7, _t(nome), border="B", align=al, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    valores = [doc.item_nome, _qtd(doc.quantidade), formatar_brl(doc.preco_unitario), _pct(doc.desconto_pct),
               formatar_brl(doc.total)]
    for (_n, w, al), v in zip(cols, valores, strict=True):
        pdf.cell(w, 7, _t(v)[:60], border="B", align=al)
    pdf.ln()
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(larg * 0.80, 8, "Total da proposta", align="R")
    pdf.cell(larg * 0.20, 8, _t(formatar_brl(doc.total)), align="R", new_x="LMARGIN", new_y="NEXT")
    if doc.mensalidade_adicional and doc.mensalidade_adicional > 0:
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(larg * 0.80, 6, "Mensalidade adicional", align="R")
        pdf.cell(larg * 0.20, 6, _t(formatar_brl(doc.mensalidade_adicional)), align="R", new_x="LMARGIN",
                 new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, _t(f"Condição de pagamento: {doc.condicao}"), new_x="LMARGIN", new_y="NEXT")

    # ---- termos, responsável e rodapé
    if (doc.termos or "").strip():
        _secao(pdf, "Termos e condições", cor)
        _paragrafos(pdf, doc.termos, 9)
    if doc.responsavel_nome:
        _secao(pdf, "Responsável", cor)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _t(doc.responsavel_nome + (f" · {doc.responsavel_email}" if doc.responsavel_email
                                                         else "")), new_x="LMARGIN", new_y="NEXT")
    if (doc.rodape or "").strip():
        pdf.ln(4)
        pdf.set_text_color(*MUTED)
        _paragrafos(pdf, doc.rodape, 8)
        pdf.set_text_color(*INK)
    return bytes(pdf.output())
