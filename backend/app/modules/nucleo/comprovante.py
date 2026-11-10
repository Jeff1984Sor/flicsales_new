"""PDF "Comprovante de consulta CNPJ": os dados públicos devolvidos pela consulta, com fonte e data/hora.

O Cartão CNPJ oficial da Receita exige captcha e não tem API: este comprovante NÃO o substitui (o texto do PDF diz
isso); o oficial pode ser anexado à mão em Anexos.
"""

from datetime import datetime

from fpdf import FPDF


def _t(v) -> str:
    """Fonte padrão do PDF é latin-1: troca o que não cabe (travessão, aspas curvas…)."""
    s = "" if v is None else str(v)
    for a, b in (("—", "-"), ("–", "-"), ("“", '"'), ("”", '"'), ("’", "'"), ("…", "...")):
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def _data_br(iso: str | None) -> str:
    if iso and len(iso) >= 10 and iso[4] == "-":
        return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"
    return iso or ""


def _moeda(v: str | None) -> str:
    if not v:
        return ""
    inteiro, _, cent = f"{float(v):,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{cent}"


def gerar_comprovante_cnpj(dados: dict, consultado_em: datetime) -> bytes:
    """`dados` = retorno de consultas.consultar_cnpj; `consultado_em` já no fuso de negócio."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, _t("Comprovante de consulta CNPJ"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(89, 101, 121)
    pdf.multi_cell(0, 5, _t(f"Consulta feita pelo FlicSales OS em {consultado_em:%d/%m/%Y %H:%M} "
                            f"(horário de Brasília). Fonte: {dados.get('fonte') or 'consulta pública'}. "
                            "Documento informativo com dados públicos: não substitui o Comprovante de Inscrição e "
                            "Situação Cadastral emitido pela Receita Federal."), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(11, 16, 32)
    pdf.ln(3)

    endereco = ", ".join(x for x in (dados.get("logradouro"), dados.get("numero"), dados.get("complemento")) if x)
    cidade = " - ".join(x for x in (dados.get("bairro"), dados.get("cidade"), dados.get("uf")) if x)
    linhas = [
        ("CNPJ", dados.get("documento")),
        ("Razão social", dados.get("nome")),
        ("Nome fantasia", dados.get("nome_fantasia")),
        ("Situação cadastral", dados.get("situacao")),
        ("Data de abertura", _data_br(dados.get("abertura"))),
        ("Porte", dados.get("porte")),
        ("Natureza jurídica", dados.get("natureza_juridica")),
        ("Capital social", _moeda(dados.get("capital_social"))),
        ("Atividade principal", dados.get("cnae_principal") or dados.get("segmento")),
        ("Endereço", endereco),
        ("", cidade),
        ("CEP", dados.get("cep")),
        ("Telefone", dados.get("telefone")),
        ("E-mail", dados.get("email_financeiro")),
    ]
    for rotulo, valor in linhas:
        if not valor:
            continue
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(45, 6, _t(rotulo))
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, _t(valor), new_x="LMARGIN", new_y="NEXT")

    secundarias = dados.get("cnaes_secundarios") or []
    if secundarias:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, _t("Atividades secundárias"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for c in secundarias:
            pdf.multi_cell(0, 5, _t(f"- {c}"), new_x="LMARGIN", new_y="NEXT")

    socios = dados.get("socios") or []
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, _t("Quadro societário"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    if not socios:
        pdf.multi_cell(0, 5, _t("Não informado pela fonte."), new_x="LMARGIN", new_y="NEXT")
    for s in socios:
        extra = " · ".join(x for x in (s.get("qualificacao"), s.get("documento"),
                                       f"desde {_data_br(s.get('data_entrada'))}" if s.get("data_entrada") else None)
                           if x)
        pdf.multi_cell(0, 5, _t(f"- {s.get('nome')}" + (f" ({extra})" if extra else "")), new_x="LMARGIN",
                       new_y="NEXT")
    return bytes(pdf.output())
