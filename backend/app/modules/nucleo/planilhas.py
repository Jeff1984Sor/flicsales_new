"""Planilhas de migração: modelo .xlsx para baixar e importação (simular / confirmar) dos cadastros.

Objetos: empresas, fornecedores, pessoas, produtos (nucleo.cadastros) e categorias, centros-custo, contas
(financeiro.cadastros). O Núcleo é dono dos modelos de cadastro financeiro (`nucleo/models.py`); fornecedor é a
`empresa` com `papel_fornecedor`.

Fluxo da importação (`importar`): lê o arquivo (.xlsx do modelo ou .csv `;`/`,` UTF-8), converte cada célula
(app.domain.planilha), aplica linha a linha NA SESSÃO (assim a simulação enxerga exatamente o que a confirmação faria,
inclusive a empresa criada numa linha e usada na seguinte) e devolve o relatório. Quem chama decide: simular ou houve
erro → `db.rollback()` (nada gravado: tudo ou nada); senão audita o resumo e faz commit.

Chaves para atualizar (não duplicar): empresa/fornecedor por CNPJ/CPF, senão nome normalizado; pessoa por e-mail,
senão nome + empresa; produto por código, senão nome; categoria por nome + natureza; centro por código; conta por nome.
Célula vazia não apaga nada: só o que veio preenchido é gravado.
"""

import csv
import io
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.models import Usuario
from app.domain import RegraViolada
from app.domain import planilha as cel
from app.domain.cadastro import (
    BASES_LEGAIS,
    CAMPOS_ENDERECO,
    PAPEIS_EMPRESA,
    PERMISSOES_COMUNICACAO,
    UFS,
    chave_de_nome,
    endereco_de,
    resolver_endereco_pessoa,
    so_digitos,
    validar_cep,
    validar_documento,
    validar_nome,
    validar_permissoes_comunicacao,
    validar_uf,
)
from app.domain.caixa import validar_edicao_conta
from app.modules.nucleo import servico
from app.modules.nucleo.models import CampoCustom, Categoria, CentroCusto, ContaFinanceira, Empresa, Pessoa, Produto
from app.modules.nucleo.regras import SEPARADOR_MULTIPLA, DefCampo, normalizar_valor

LIMITE_BYTES = 5 * 1024 * 1024
LIMITE_LINHAS = 5000
LIMITE_PREVIA = 1000
LINHAS_COM_VALIDACAO = 5000
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ================================================================================================= colunas
@dataclass(frozen=True)
class Coluna:
    cabecalho: str
    campo: str
    # texto | email | documento | cep | uf | decimal | data | sim_nao | opcao | papeis | multipla | custom
    tipo: str = "texto"
    obrigatoria: bool = False  # obrigatória para CRIAR (na atualização, vazio não muda nada)
    max_len: int | None = None
    opcoes: tuple[tuple[str, str], ...] = ()  # (rótulo exibido, valor gravado)
    formato: str = "Texto"
    exemplo: Any = ""
    ajuda: str = ""
    minimo: Decimal | None = None
    campo_custom: DefCampo | None = None

    @property
    def mapa_opcoes(self) -> dict[str, str]:
        return dict(self.opcoes)


SIM_NAO = (("Sim", "sim"), ("Não", "nao"))
PAPEIS = tuple((p, p) for p in PAPEIS_EMPRESA)
CANAIS = (("E-mail", "email"), ("Ligação", "ligacao"), ("WhatsApp", "whatsapp"))
TIPOS_PRODUTO = (("Serviço", "servico"), ("Produto", "produto"))
NATUREZAS = (("Receita", "receita"), ("Despesa", "despesa"))
BASES = tuple((r, v) for v, r in BASES_LEGAIS.items())
PERMISSOES = tuple((r, v) for v, r in PERMISSOES_COMUNICACAO.items())

ENDERECO = (
    Coluna("CEP", "cep", "cep", formato="00000-000", exemplo="01310-100"),
    Coluna("Logradouro", "logradouro", max_len=200, exemplo="Avenida Paulista"),
    Coluna("Número", "numero", max_len=20, exemplo="1000"),
    Coluna("Complemento", "complemento", max_len=100, exemplo="Conjunto 12"),
    Coluna("Bairro", "bairro", max_len=100, exemplo="Bela Vista"),
    Coluna("Cidade", "cidade", max_len=100, exemplo="São Paulo"),
    Coluna("UF", "uf", "uf", opcoes=tuple((u, u) for u in UFS), formato="Sigla do estado", exemplo="SP"),
)


def _colunas_fixas(objeto: str) -> tuple[Coluna, ...]:
    if objeto == "empresas":
        return (
            Coluna("Nome", "nome", obrigatoria=True, max_len=200, exemplo="Aurora Consultoria",
                   ajuda="Nome único da empresa (não diferencia acento nem maiúsculas)."),
            Coluna("CNPJ/CPF", "documento", "documento", formato="00.000.000/0000-00 ou 000.000.000-00",
                   exemplo="11.222.333/0001-81", ajuda="Com CNPJ, a linha atualiza a empresa que já tem esse CNPJ."),
            Coluna("Nome fantasia", "nome_fantasia", max_len=200, exemplo="Aurora"),
            Coluna("Segmento", "segmento", max_len=100, exemplo="Consultoria"),
            Coluna("Porte", "porte", max_len=30, exemplo="EPP"),
            Coluna("Site", "site", max_len=300, exemplo="https://aurora.com.br"),
            Coluna("E-mail financeiro", "email_financeiro", "email", max_len=200, exemplo="financeiro@aurora.com.br"),
            Coluna("Telefone", "telefone", max_len=30, exemplo="(11) 3333-4444"),
            Coluna("Papéis", "papeis", "papeis", opcoes=PAPEIS, formato="prospect, cliente, fornecedor, parceiro",
                   exemplo="cliente", ajuda="Um ou mais, separados por vírgula. Papéis informados são acrescentados "
                                        "(nenhum é removido). Sem papel, a empresa nova nasce como prospect."),
            Coluna("Origem", "origem", max_len=100, exemplo="Indicação"),
            Coluna("Observações", "observacoes", exemplo=""),
            *ENDERECO,
        )
    if objeto == "fornecedores":
        return (
            Coluna("Nome", "nome", obrigatoria=True, max_len=200, exemplo="Nuvem Digital",
                   ajuda="Se já existe empresa com este nome (ou CNPJ), ela passa a ser também fornecedor."),
            Coluna("CNPJ/CPF", "documento", "documento", formato="00.000.000/0000-00 ou 000.000.000-00",
                   exemplo="11.222.333/0001-81"),
            Coluna("Contato", "contato", max_len=200, exemplo="Joana Lima",
                   ajuda="Cria a pessoa de contato na empresa, se ainda não existir."),
            Coluna("E-mail", "email_financeiro", "email", max_len=200, exemplo="contas@nuvem.com.br"),
            Coluna("Telefone", "telefone", max_len=30, exemplo="(11) 98888-7777"),
            Coluna("Categoria padrão", "categoria_padrao", max_len=120, exemplo="Estrutura",
                   ajuda="Nome de uma categoria de DESPESA já cadastrada."),
            Coluna("Condição habitual", "condicao_habitual", max_len=200, exemplo="Boleto todo dia 5"),
            Coluna("Observações", "observacoes"),
            *ENDERECO,
        )
    if objeto == "pessoas":
        return (
            Coluna("Nome", "nome", obrigatoria=True, max_len=200, exemplo="Paula Mendes"),
            Coluna("Empresa", "empresa", max_len=200, exemplo="Aurora Consultoria",
                   ajuda="Nome da empresa. Se não existir, é criada (o nome basta)."),
            Coluna("Cargo", "cargo", max_len=120, exemplo="Diretora de operações"),
            Coluna("E-mail", "email", "email", max_len=200, exemplo="paula@aurora.com.br",
                   ajuda="Com e-mail, a linha atualiza a pessoa que já tem esse e-mail."),
            Coluna("Telefone", "telefone", max_len=30, exemplo="(11) 97777-6666"),
            Coluna("Canal preferido", "canal_preferido", "opcao", opcoes=CANAIS, formato="E-mail, Ligação ou WhatsApp",
                   exemplo="E-mail"),
            Coluna("Observações", "observacoes"),
            Coluna("Usa endereço da empresa", "usa_endereco_da_empresa", "sim_nao", opcoes=SIM_NAO,
                   formato="Sim ou Não", exemplo="Sim",
                   ajuda="Sim (padrão): copia e acompanha o endereço da empresa. Endereço preenchido sem esta coluna "
                         "desliga a marca."),
            Coluna("Base legal", "base_legal", "opcao", opcoes=BASES, formato="Uma das opções", exemplo="Consentimento",
                   ajuda="Base legal do tratamento dos dados (LGPD)."),
            Coluna("Permissão de comunicação", "permissoes_comunicacao", "multipla", opcoes=PERMISSOES,
                   formato="Uma ou mais, separadas por ;", exemplo=PERMISSOES[0][0],
                   ajuda="Separe por ponto e vírgula. Célula preenchida substitui as permissões atuais. "
                         "Opt-out não combina com as outras."),
            *ENDERECO,
        )
    if objeto == "produtos":
        return (
            Coluna("Nome", "nome", obrigatoria=True, max_len=200, exemplo="Consultoria estratégica"),
            Coluna("Tipo", "tipo", "opcao", obrigatoria=True, opcoes=TIPOS_PRODUTO, formato="Serviço ou Produto",
                   exemplo="Serviço"),
            Coluna("Código", "codigo", max_len=50, exemplo="CONS-EST",
                   ajuda="Com código, a linha atualiza o produto que já tem esse código."),
            Coluna("Unidade", "unidade", max_len=30, exemplo="projeto"),
            Coluna("Preço de referência", "preco_referencia", "decimal", formato="1.234,56", exemplo="24.000,00",
                   minimo=Decimal("0")),
            Coluna("Recorrente", "recorrente", "sim_nao", opcoes=SIM_NAO, formato="Sim ou Não", exemplo="Não"),
            Coluna("Descrição", "descricao", exemplo="Projeto de consultoria estratégica."),
        )
    if objeto == "categorias":
        return (
            Coluna("Nome", "nome", obrigatoria=True, max_len=120, exemplo="Serviços prestados"),
            Coluna("Natureza", "natureza", "opcao", obrigatoria=True, opcoes=NATUREZAS, formato="Receita ou Despesa",
                   exemplo="Receita", ajuda="Nome + natureza identificam a categoria (atualiza em vez de duplicar)."),
            Coluna("Categoria superior", "superior", max_len=120, exemplo="",
                   ajuda="Nome de uma categoria da mesma natureza (já cadastrada ou numa linha acima)."),
        )
    if objeto == "centros-custo":
        return (
            Coluna("Código", "codigo", obrigatoria=True, max_len=20, exemplo="OP",
                   ajuda="Identifica o centro (atualiza em vez de duplicar)."),
            Coluna("Nome", "nome", obrigatoria=True, max_len=120, exemplo="Operação"),
            Coluna("Responsável", "responsavel", max_len=60, exemplo="francine", formato="Login do usuário"),
        )
    if objeto == "contas":
        return (
            Coluna("Nome", "nome", obrigatoria=True, max_len=120, exemplo="Conta operacional",
                   ajuda="Identifica a conta (atualiza em vez de duplicar)."),
            Coluna("Instituição", "instituicao", max_len=120, exemplo="Banco do Brasil"),
            Coluna("Saldo inicial", "saldo_inicial", "decimal", obrigatoria=True, formato="1.234,56 (pode ser negativo)",
                   exemplo="25.000,00", ajuda="Com movimento (baixas ou transferências), não pode mais mudar."),
            Coluna("Data-base", "data_base", "data", obrigatoria=True, formato="DD/MM/AAAA", exemplo="01/11/2026",
                   ajuda="Data do saldo inicial. Com movimento, não pode mais mudar."),
        )
    raise KeyError(objeto)


OBJETOS: dict[str, dict] = {
    "empresas": {"rotulo": "Empresas e clientes", "entidade": "empresa", "custom": "empresa"},
    "fornecedores": {"rotulo": "Fornecedores", "entidade": "empresa", "custom": None},
    "pessoas": {"rotulo": "Pessoas e contatos", "entidade": "pessoa", "custom": "pessoa"},
    "produtos": {"rotulo": "Produtos e serviços", "entidade": "produto", "custom": None},
    "categorias": {"rotulo": "Categorias", "entidade": "categoria", "custom": None},
    "centros-custo": {"rotulo": "Centros de custo", "entidade": "centro_custo", "custom": None},
    "contas": {"rotulo": "Contas financeiras", "entidade": "conta_financeira", "custom": None},
}

_FORMATO_CUSTOM = {"texto": "Texto", "numero": "Número", "moeda": "1.234,56", "data": "DD/MM/AAAA",
                   "sim_nao": "Sim ou Não", "lista": "Uma das opções", "multipla": "Uma ou mais, separadas por ;",
                   "link": "https://endereco.com.br"}


def colunas(db: Session, objeto: str) -> list[Coluna]:
    """Colunas fixas + uma por campo personalizado ativo do objeto (cabeçalho = nome do campo)."""
    fixas = list(_colunas_fixas(objeto))
    alvo = OBJETOS[objeto]["custom"]
    if alvo:
        usados = {cel.chave_cabecalho(c.cabecalho) for c in fixas}
        for c in db.scalars(select(CampoCustom).where(CampoCustom.objeto == alvo, CampoCustom.arquivado.is_(False))
                            .order_by(CampoCustom.ordem, CampoCustom.id)):
            cab = c.nome if cel.chave_cabecalho(c.nome) not in usados else f"{c.nome} (personalizado)"
            d = DefCampo(slug=c.slug, nome=c.nome, tipo=c.tipo, opcoes=tuple(c.opcoes or ()),
                         obrigatorio=c.obrigatorio)
            opcoes = tuple((o, o) for o in c.opcoes or ()) if c.tipo in ("lista", "multipla") else (
                SIM_NAO if c.tipo == "sim_nao" else ())
            fixas.append(Coluna(cab, f"campos_custom.{c.slug}", "custom", obrigatoria=c.obrigatorio, opcoes=opcoes,
                                formato=_FORMATO_CUSTOM.get(c.tipo, "Texto"),
                                exemplo=(c.opcoes or [""])[0] if c.tipo in ("lista", "multipla") else "",
                                ajuda="Campo personalizado.", campo_custom=d))
    return fixas


# ================================================================================================= modelo .xlsx
def gerar_modelo(db: Session, objeto: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    cols = colunas(db, objeto)
    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"
    cabecalho_fill = PatternFill("solid", fgColor="0B1020")
    for i, c in enumerate(cols, 1):
        cel_ = ws.cell(row=1, column=i, value=f"{c.cabecalho} *" if c.obrigatoria else c.cabecalho)
        cel_.font = Font(bold=True, color="FFFFFF")
        cel_.fill = cabecalho_fill
        cel_.alignment = Alignment(vertical="center")
        exemplo = c.exemplo
        if i == 1:
            exemplo = f"{cel.MARCA_EXEMPLO}: {exemplo}" if exemplo else cel.MARCA_EXEMPLO
        ex = ws.cell(row=2, column=i, value=exemplo if exemplo != "" else None)
        ex.font = Font(italic=True, color="8A93A3")
        ex.fill = PatternFill("solid", fgColor="EEF1F6")
        letra = get_column_letter(i)
        ws.column_dimensions[letra].width = max(14, min(40, len(c.cabecalho) + 6, len(str(c.exemplo)) + 4))
        if c.tipo in ("documento", "cep", "texto") or c.campo in ("telefone",):
            for linha in range(2, 202):  # texto: o Excel não come zero à esquerda (o importador completa de todo jeito)
                ws.cell(row=linha, column=i).number_format = "@"
        if c.opcoes:
            itens = [r for r, _ in c.opcoes]
            formula = '"' + ",".join(itens) + '"'
            if len(formula) <= 255 and not any("," in x or '"' in x for x in itens):
                dv = DataValidation(type="list", formula1=formula, allow_blank=True)
                if c.tipo in ("papeis", "multipla") or (c.campo_custom and c.campo_custom.tipo == "multipla"):
                    # aceita vários na mesma célula: a lista só sugere, não recusa
                    dv.showErrorMessage = False
                else:
                    dv.error, dv.errorTitle = "Escolha uma das opções da lista.", "Valor inválido"
                    dv.showErrorMessage = True
                dv.prompt, dv.promptTitle, dv.showInputMessage = c.formato, c.cabecalho, True
                ws.add_data_validation(dv)
                dv.add(f"{letra}3:{letra}{LINHAS_COM_VALIDACAO + 2}")
    ws.freeze_panes = "A2"

    inst = wb.create_sheet("Instruções")
    rotulo = OBJETOS[objeto]["rotulo"]
    topo = [
        f"Modelo de importação — {rotulo}",
        "Preencha a aba “Dados” a partir da linha 3. A linha 2 (cinza, marcada EXEMPLO) é ignorada.",
        "Colunas com * são obrigatórias para criar um registro. Célula vazia não apaga nada no cadastro existente.",
        f"Até {LIMITE_LINHAS} linhas e 5 MB por arquivo. Também aceita .csv (separado por ; ou ,) em UTF-8.",
        "Envie primeiro para simular: nada é gravado até você confirmar, e com qualquer erro nada é gravado.",
        "Chave para atualizar em vez de duplicar: " + _CHAVES[objeto],
    ]
    for n, t in enumerate(topo, 1):
        inst.cell(row=n, column=1, value=t).font = Font(bold=(n == 1), size=13 if n == 1 else 11)
    linha0 = len(topo) + 2
    for i, t in enumerate(("Coluna", "Obrigatória", "Formato", "Exemplo", "Observação"), 1):
        c_ = inst.cell(row=linha0, column=i, value=t)
        c_.font, c_.fill = Font(bold=True, color="FFFFFF"), cabecalho_fill
    for n, c in enumerate(cols, linha0 + 1):
        opcoes = f" Opções: {', '.join(r for r, _ in c.opcoes)}." if c.opcoes and c.tipo != "uf" else ""
        valores = (c.cabecalho, "Sim, para criar" if c.obrigatoria else "Não", c.formato, str(c.exemplo or ""),
                   (c.ajuda + opcoes).strip())
        for i, v in enumerate(valores, 1):
            inst.cell(row=n, column=i, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    for letra, larg in zip("ABCDE", (26, 16, 30, 28, 70), strict=True):
        inst.column_dimensions[letra].width = larg
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


_CHAVES = {
    "empresas": "CNPJ/CPF; sem documento, o nome (sem acento e sem diferenciar maiúsculas).",
    "fornecedores": "CNPJ/CPF; sem documento, o nome (sem acento e sem diferenciar maiúsculas).",
    "pessoas": "e-mail; sem e-mail, nome + empresa.",
    "produtos": "código; sem código, o nome.",
    "categorias": "nome + natureza.",
    "centros-custo": "código.",
    "contas": "nome.",
}


# cada tupla é um grupo: o cabeçalho precisa de ao menos uma coluna de cada grupo
_COLUNAS_CHAVE: dict[str, list[tuple[str, ...]]] = {
    "empresas": [("nome", "documento")],
    "fornecedores": [("nome", "documento")],
    "pessoas": [("nome", "email")],
    "produtos": [("nome", "codigo")],
    "categorias": [("nome",), ("natureza",)],
    "centros-custo": [("codigo",)],
    "contas": [("nome",)],
}


# ================================================================================================= leitura do arquivo
def ler_arquivo(nome: str | None, conteudo: bytes) -> tuple[list[Any], list[tuple[int, list[Any]]]]:
    """(cabeçalho, [(número da linha na planilha, valores)]). Ignora linhas vazias e a de EXEMPLO."""
    if len(conteudo) > LIMITE_BYTES:
        raise RegraViolada("Arquivo maior que 5 MB. Divida a planilha em partes menores.")
    if not conteudo:
        raise RegraViolada("O arquivo está vazio.")
    nome = (nome or "").lower()
    if conteudo[:2] == b"PK" or nome.endswith((".xlsx", ".xlsm")):
        linhas = _ler_xlsx(conteudo)
    elif nome.endswith((".csv", ".txt")) or not nome:
        linhas = _ler_csv(conteudo)
    else:
        raise RegraViolada("Envie a planilha em .xlsx (o modelo) ou .csv.")
    linhas = iter(linhas)
    cabecalho: list[Any] = []
    for _n, valores in linhas:
        if any(not cel.vazia(v) for v in valores):
            cabecalho = list(valores)
            break
    if not cabecalho:
        raise RegraViolada("A planilha não tem cabeçalho. Baixe o modelo e preencha a aba “Dados”.")
    dados = []
    for n, valores in linhas:
        if all(cel.vazia(v) for v in valores) or (valores and cel.linha_de_exemplo(valores[0])):
            continue
        dados.append((n, list(valores)))
        if len(dados) > LIMITE_LINHAS:
            raise RegraViolada(f"A planilha passa de {LIMITE_LINHAS} linhas. Divida em partes menores.")
    return cabecalho, dados


def _ler_xlsx(conteudo: bytes) -> Iterator[tuple[int, list[Any]]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception:  # arquivo corrompido ou não é xlsx de verdade
        raise RegraViolada("Não foi possível ler a planilha. Salve como .xlsx (ou .csv) e envie de novo.") from None
    ws = wb["Dados"] if "Dados" in wb.sheetnames else wb.worksheets[0]
    linhas = [(n, list(v)) for n, v in enumerate(ws.iter_rows(values_only=True), 1)]
    wb.close()
    return iter(linhas)


def _ler_csv(conteudo: bytes) -> Iterator[tuple[int, list[Any]]]:
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("cp1252", errors="replace")  # CSV salvo pelo Excel em PT-BR
    primeira = texto.split("\n", 1)[0]
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=sep)
    return ((n, v) for n, v in enumerate(leitor, 1))


# ================================================================================================= importação
class ErroLinha(Exception):
    def __init__(self, coluna: str | None, mensagem: str) -> None:
        super().__init__(mensagem)
        self.coluna, self.mensagem = coluna, mensagem


@contextmanager
def _na_coluna(coluna: str | None):
    """RegraViolada levantada dentro do bloco vira erro da linha nesta coluna."""
    try:
        yield
    except RegraViolada as e:
        raise ErroLinha(coluna, e.mensagem) from None


def _converter(c: Coluna, valor: Any) -> Any:
    if cel.vazia(valor):
        return None
    t = c.tipo
    if t == "texto":
        return cel.texto(valor, max_len=c.max_len)
    if t == "email":
        s = cel.texto(valor, max_len=c.max_len)
        if s and ("@" not in s or " " in s):
            raise RegraViolada("E-mail inválido.")
        return s.lower() if s else None
    if t == "documento":
        return validar_documento(cel.digitos(valor, tamanhos=(11, 14)))
    if t == "cep":
        return validar_cep(cel.digitos(valor, tamanhos=(8,)))
    if t == "uf":
        return validar_uf(cel.texto(valor))
    if t == "decimal":
        return cel.decimal(valor, minimo=c.minimo)
    if t == "data":
        return cel.data(valor)
    if t == "sim_nao":
        return cel.sim_nao(valor)
    if t == "opcao":
        return cel.opcao(valor, c.mapa_opcoes)
    if t == "papeis":
        return cel.lista(valor, c.mapa_opcoes)
    if t == "multipla":
        return cel.lista(valor, c.mapa_opcoes, separadores=SEPARADOR_MULTIPLA)
    if t == "custom":
        d = c.campo_custom
        if d.tipo in ("numero", "moeda"):
            valor = str(cel.decimal(valor))
        elif d.tipo == "data":
            valor = cel.data(valor).isoformat()
        elif d.tipo == "sim_nao":
            valor = cel.sim_nao(valor)
        elif d.tipo == "multipla":  # sem acento/maiúsculas, separadas por ";"
            valor = cel.lista(valor, {o: o for o in d.opcoes}, separadores=SEPARADOR_MULTIPLA)
        elif isinstance(valor, float | int | datetime | date):
            valor = cel.texto(valor)
        return normalizar_valor(d, valor)
    raise ValueError(t)  # pragma: no cover


@dataclass
class Relatorio:
    total: int = 0
    criar: int = 0
    atualizar: int = 0
    ignorar: int = 0
    erros: list[dict] = field(default_factory=list)
    previa: list[dict] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {"total": self.total, "criar": self.criar, "atualizar": self.atualizar, "ignorar": self.ignorar,
                "erros": self.erros, "previa": self.previa}


Auditar = Callable[..., None]


def importar(db: Session, objeto: str, nome_arquivo: str | None, conteudo: bytes, *, usuario_id: int,
             auditar: Auditar) -> Relatorio:
    """Aplica a planilha na sessão (sem commit) e devolve o relatório. Ver o topo do módulo."""
    cols = colunas(db, objeto)
    cabecalho, linhas = ler_arquivo(nome_arquivo, conteudo)
    por_chave = {cel.chave_cabecalho(c.cabecalho): c for c in cols}
    indice: dict[int, Coluna] = {}
    for i, h in enumerate(cabecalho):
        c = por_chave.get(cel.chave_cabecalho(h))
        if c is not None and c not in indice.values():
            indice[i] = c
    rel = Relatorio(total=len(linhas))
    # o cabeçalho precisa da coluna que identifica o registro; as outras obrigatórias só valem ao CRIAR (linha a linha),
    # assim uma planilha só de atualização (ex.: Nome + Telefone) é aceita.
    presentes = {c.campo for c in indice.values()}
    for grupo in _COLUNAS_CHAVE[objeto]:
        if not presentes & set(grupo):
            rotulos = [c.cabecalho for c in cols if c.campo in grupo]
            rel.erros.append({"linha": 1, "coluna": rotulos[0],
                              "mensagem": f"Coluna obrigatória ausente: {' ou '.join(rotulos)}. Baixe o modelo de novo."})
    if rel.erros:
        return rel
    imp = _Importador(db, objeto, usuario_id, auditar)
    for n, valores in linhas:
        dados: dict[str, Any] = {}
        erros_linha = []
        for i, c in indice.items():
            bruto = valores[i] if i < len(valores) else None
            try:
                v = _converter(c, bruto)
            except RegraViolada as e:
                erros_linha.append({"linha": n, "coluna": c.cabecalho, "mensagem": e.mensagem})
                continue
            if v is not None:
                dados[c.campo] = v
        if erros_linha:
            rel.erros.extend(erros_linha)
            continue
        try:
            acao, nome = imp.linha(n, dados)
        except ErroLinha as e:
            rel.erros.append({"linha": n, "coluna": e.coluna, "mensagem": e.mensagem})
            continue
        except RegraViolada as e:
            rel.erros.append({"linha": n, "coluna": None, "mensagem": e.mensagem})
            continue
        setattr(rel, acao, getattr(rel, acao) + 1)
        if len(rel.previa) < LIMITE_PREVIA:
            rel.previa.append({"linha": n, "acao": acao, "nome": nome})
    return rel


def _separar_custom(dados: dict) -> dict:
    custom = {k.removeprefix("campos_custom."): dados.pop(k) for k in list(dados) if k.startswith("campos_custom.")}
    return custom


def _mudancas(obj, valores: dict) -> dict:
    return {k: v for k, v in valores.items() if getattr(obj, k) != v}


class _Importador:
    def __init__(self, db: Session, objeto: str, usuario_id: int, auditar: Auditar) -> None:
        self.db, self.objeto, self.usuario_id, self._auditar = db, objeto, usuario_id, auditar
        self.entidade = OBJETOS[objeto]["entidade"]
        self._por_doc: dict[str, Empresa] | None = None

    # ------------------------------------------------------------------------------------------- utilitários
    def linha(self, n: int, dados: dict) -> tuple[str, str]:
        return getattr(self, "_" + self.objeto.replace("-", "_"))(n, dados)

    def auditar_linha(self, n: int, acao: str, obj, nome: str, antes: dict | None, depois: dict | None) -> None:
        self._auditar(f"importacao.{self.objeto}", self.entidade if not isinstance(obj, Pessoa) else "pessoa", obj.id,
                      descricao=f"Linha {n}: {'criou' if acao == 'criar' else 'atualizou'} {nome}", antes=antes,
                      depois=depois)

    def _gravar(self, n: int, obj, valores: dict, nome: str, *, novo: bool) -> str:
        """Aplica `valores` (já validados) e audita. Devolve a ação."""
        if novo:
            self.db.add(obj)
            self.db.flush()
            self.auditar_linha(n, "criar", obj, nome, None, audit.snapshot(obj))
            return "criar"
        antes = audit.snapshot(obj)
        for k, v in valores.items():
            setattr(obj, k, v)
        self.db.flush()
        a, d = audit.diff(antes, audit.snapshot(obj))
        if not (a or d):
            return "ignorar"
        self.auditar_linha(n, "atualizar", obj, nome, a, d)
        return "atualizar"

    def por_documento(self) -> dict[str, Empresa]:
        if self._por_doc is None:
            self._por_doc = {so_digitos(e.documento): e for e in self.db.scalars(
                select(Empresa).where(Empresa.documento.is_not(None)).order_by(Empresa.id.desc())) if e.documento}
        return self._por_doc

    def propagar(self, e: Empresa) -> None:
        for p, a, d in servico.propagar_endereco_empresa(self.db, e):
            self._auditar("pessoa.endereco_da_empresa", "pessoa", p.id,
                          descricao=f"{p.nome}: endereço atualizado com o de {e.nome} (importação)", antes=a, depois=d)

    # ------------------------------------------------------------------------------------------- empresas
    def _empresa(self, n: int, dados: dict, *, fornecedor: bool) -> tuple[str, str]:
        db = self.db
        custom = _separar_custom(dados)
        papeis = dados.pop("papeis", None) or []
        contato = dados.pop("contato", None)
        cat_nome = dados.pop("categoria_padrao", None)
        nome, doc = dados.get("nome"), dados.get("documento")
        alvo = self.por_documento().get(so_digitos(doc)) if doc else None
        if alvo is None and nome:
            alvo = servico.empresa_com_nome(db, nome)
        if alvo is None and not nome:
            raise ErroLinha("Nome", "Informe o nome da empresa.")
        if cat_nome:
            cat = db.scalar(select(Categoria).where(func.lower(Categoria.nome) == cat_nome.lower(),
                                                    Categoria.natureza == "despesa").order_by(Categoria.id))
            if cat is None:
                raise ErroLinha("Categoria padrão", f"Categoria de despesa “{cat_nome}” não encontrada. "
                                                    "Cadastre-a (ou importe as categorias) antes.")
            dados["categoria_padrao_id"] = cat.id
        if fornecedor:
            papeis = [*papeis, "fornecedor"]
        if doc:
            outra = self.por_documento().get(so_digitos(doc))
            if outra is not None and alvo is not None and outra.id != alvo.id:
                raise ErroLinha("CNPJ/CPF", f"Este documento já é de outra empresa: {outra.nome}.")
        if alvo is None:
            with _na_coluna("Nome"):
                dados["nome"] = servico.garantir_nome_livre(db, nome)
            with _na_coluna(None):
                custom = servico.validar_campos_custom(db, "empresa", custom, None)
            e = Empresa(responsavel_id=self.usuario_id, campos_custom=custom, **dados)
            e.papeis = [p for p in PAPEIS_EMPRESA if p in (papeis or ["prospect"])]
            acao = self._gravar(n, e, {}, e.nome, novo=True)
        else:
            e = alvo
            if "nome" in dados:
                if chave_de_nome(dados["nome"]) == e.nome_chave:
                    dados.pop("nome")
                else:
                    with _na_coluna("Nome"):
                        dados["nome"] = servico.garantir_nome_livre(db, dados["nome"], exceto_id=e.id)
            if custom:
                with _na_coluna(None):
                    dados["campos_custom"] = servico.validar_campos_custom(db, "empresa", custom, e.campos_custom)
            novos_papeis = set(e.papeis) | set(papeis)
            if novos_papeis != set(e.papeis):
                for p in PAPEIS_EMPRESA:
                    dados[f"papel_{p}"] = p in novos_papeis
            endereco_antes = endereco_de(e)
            acao = self._gravar(n, e, _mudancas(e, dados), e.nome, novo=False)
            if endereco_de(e) != endereco_antes:
                self.propagar(e)
        if e.documento:
            self.por_documento()[so_digitos(e.documento)] = e
        if contato:
            self._contato(e, contato, dados.get("email_financeiro"), dados.get("telefone"))
        return acao, e.nome

    def _contato(self, e: Empresa, nome: str, email: str | None, telefone: str | None) -> None:
        ja = self.db.scalar(select(Pessoa).where(Pessoa.empresa_id == e.id, func.lower(Pessoa.nome) == nome.lower()))
        if ja is None:
            p = Pessoa(nome=nome, empresa_id=e.id, email=email, telefone=telefone, responsavel_id=self.usuario_id,
                       campos_custom={}, usa_endereco_da_empresa=True, **endereco_de(e))
            self.db.add(p)
            self.db.flush()
            self._auditar("pessoa.criar", "pessoa", p.id, descricao=f"{nome} (contato do fornecedor {e.nome}, importação)",
                          depois=audit.snapshot(p))

    def _empresas(self, n: int, dados: dict) -> tuple[str, str]:
        return self._empresa(n, dados, fornecedor=False)

    def _fornecedores(self, n: int, dados: dict) -> tuple[str, str]:
        return self._empresa(n, dados, fornecedor=True)

    # ------------------------------------------------------------------------------------------- pessoas
    def _pessoas(self, n: int, dados: dict) -> tuple[str, str]:
        db = self.db
        custom = _separar_custom(dados)
        emp_nome = dados.pop("empresa", None)
        marca = dados.pop("usa_endereco_da_empresa", None)
        endereco = {k: dados.pop(k) for k in CAMPOS_ENDERECO if k in dados}
        if "permissoes_comunicacao" in dados:
            with _na_coluna("Permissão de comunicação"):
                dados["permissoes_comunicacao"] = validar_permissoes_comunicacao(dados["permissoes_comunicacao"])
        empresa = None
        if emp_nome:
            empresa = servico.empresa_com_nome(db, emp_nome)
            if empresa is None:
                with _na_coluna("Empresa"):
                    empresa, _ = servico.obter_ou_criar_empresa(db, emp_nome, responsavel_id=self.usuario_id)
                self._auditar("empresa.criar", "empresa", empresa.id,
                              descricao=f"{empresa.nome} (citada na importação de pessoas, linha {n})",
                              depois=audit.snapshot(empresa))
        alvo = None
        if dados.get("email"):
            alvo = db.scalar(select(Pessoa).where(func.lower(Pessoa.email) == dados["email"]).order_by(Pessoa.id))
        if alvo is None and dados.get("nome"):
            q = select(Pessoa).where(func.lower(Pessoa.nome) == dados["nome"].lower())
            q = q.where(Pessoa.empresa_id == empresa.id) if empresa else q.where(Pessoa.empresa_id.is_(None))
            alvo = db.scalar(q.order_by(Pessoa.id))
        if alvo is None:
            with _na_coluna("Nome"):
                dados["nome"] = validar_nome(dados.get("nome"), o_que="o nome da pessoa")
            with _na_coluna(None):
                custom = servico.validar_campos_custom(db, "pessoa", custom, None)
            m, end = resolver_endereco_pessoa(marca_atual=True, endereco_atual={}, enviado=endereco, marca_enviada=marca,
                                              endereco_empresa=endereco_de(empresa) if empresa else None)
            p = Pessoa(empresa_id=empresa.id if empresa else None, responsavel_id=self.usuario_id, campos_custom=custom,
                       usa_endereco_da_empresa=m, **end, **dados)
            return self._gravar(n, p, {}, p.nome, novo=True), p.nome
        p = alvo
        if empresa is not None:
            dados["empresa_id"] = empresa.id
        if custom:
            with _na_coluna(None):
                dados["campos_custom"] = servico.validar_campos_custom(db, "pessoa", custom, p.campos_custom)
        emp_final = empresa or (db.get(Empresa, p.empresa_id) if p.empresa_id else None)
        if endereco or marca is not None or empresa is not None:
            m, end = resolver_endereco_pessoa(marca_atual=p.usa_endereco_da_empresa, endereco_atual=endereco_de(p),
                                              enviado=endereco, marca_enviada=marca,
                                              endereco_empresa=endereco_de(emp_final) if emp_final else None)
            dados.update(end, usa_endereco_da_empresa=m)
        return self._gravar(n, p, _mudancas(p, dados), p.nome, novo=False), p.nome

    # ------------------------------------------------------------------------------------------- produtos
    def _produtos(self, n: int, dados: dict) -> tuple[str, str]:
        db = self.db
        alvo = db.scalar(select(Produto).where(Produto.codigo == dados["codigo"])) if dados.get("codigo") else None
        if alvo is None and dados.get("nome"):
            alvo = db.scalar(select(Produto).where(func.lower(Produto.nome) == dados["nome"].lower()))
        if alvo is None:
            with _na_coluna("Nome"):
                dados["nome"] = validar_nome(dados.get("nome"), o_que="o nome do produto ou serviço")
            if not dados.get("tipo"):
                raise ErroLinha("Tipo", "Informe o tipo (Serviço ou Produto).")
        if dados.get("nome"):
            q = select(Produto.id).where(func.lower(Produto.nome) == dados["nome"].lower())
            if alvo is not None:
                q = q.where(Produto.id != alvo.id)
            if db.scalar(q):
                raise ErroLinha("Nome", "Já existe produto ou serviço com este nome (e outro código).")
        if dados.get("codigo") and alvo is not None and alvo.codigo != dados["codigo"]:
            if db.scalar(select(Produto.id).where(Produto.codigo == dados["codigo"], Produto.id != alvo.id)):
                raise ErroLinha("Código", "Já existe produto ou serviço com este código.")
        if alvo is None:
            p = Produto(recorrente=bool(dados.pop("recorrente", False)), **dados)
            return self._gravar(n, p, {}, p.nome, novo=True), p.nome
        return self._gravar(n, alvo, _mudancas(alvo, dados), alvo.nome, novo=False), alvo.nome

    # ------------------------------------------------------------------------------------------- categorias
    def _categorias(self, n: int, dados: dict) -> tuple[str, str]:
        db = self.db
        with _na_coluna("Nome"):
            nome = validar_nome(dados.get("nome"), o_que="o nome da categoria")
        natureza = dados.get("natureza")
        if not natureza:
            raise ErroLinha("Natureza", "Informe a natureza (Receita ou Despesa).")
        alvo = db.scalar(select(Categoria).where(func.lower(Categoria.nome) == nome.lower(),
                                                 Categoria.natureza == natureza).order_by(Categoria.id))
        valores: dict[str, Any] = {"nome": nome, "natureza": natureza}
        sup_nome = dados.get("superior")
        if sup_nome:
            sup = db.scalar(select(Categoria).where(func.lower(Categoria.nome) == sup_nome.lower(),
                                                    Categoria.natureza == natureza).order_by(Categoria.id))
            if sup is None:
                raise ErroLinha("Categoria superior", f"Categoria superior “{sup_nome}” ({natureza}) não encontrada. "
                                                      "Cadastre-a antes ou coloque-a numa linha acima.")
            atual, vistos = sup, set()
            while atual is not None and atual.id not in vistos:
                if alvo is not None and atual.id == alvo.id:
                    raise ErroLinha("Categoria superior", "Uma categoria não pode ficar abaixo dela mesma.")
                vistos.add(atual.id)
                atual = db.get(Categoria, atual.superior_id) if atual.superior_id else None
            valores["superior_id"] = sup.id
        if alvo is None:
            c = Categoria(**valores)
            return self._gravar(n, c, {}, c.nome, novo=True), c.nome
        valores.pop("nome")  # a chave é o nome: só a caixa poderia mudar, e isso não é alteração
        return self._gravar(n, alvo, _mudancas(alvo, valores), alvo.nome, novo=False), alvo.nome

    # ------------------------------------------------------------------------------------------- centros de custo
    def _centros_custo(self, n: int, dados: dict) -> tuple[str, str]:
        db = self.db
        codigo = (dados.get("codigo") or "").strip().upper()
        if not codigo:
            raise ErroLinha("Código", "Informe o código do centro de custo.")
        valores: dict[str, Any] = {"codigo": codigo}
        if dados.get("nome"):
            valores["nome"] = dados["nome"]
        login = dados.get("responsavel")
        if login:
            uid = db.scalar(select(Usuario.id).where(or_(func.lower(Usuario.login) == login.lower(),
                                                         func.lower(Usuario.email) == login.lower())))
            if uid is None:
                raise ErroLinha("Responsável", f"Usuário “{login}” não encontrado. Informe o login.")
            valores["responsavel_id"] = uid
        alvo = db.scalar(select(CentroCusto).where(func.upper(CentroCusto.codigo) == codigo))
        if alvo is None:
            if not valores.get("nome"):
                raise ErroLinha("Nome", "Informe o nome do centro de custo.")
            c = CentroCusto(**valores)
            return self._gravar(n, c, {}, f"{c.codigo} · {c.nome}", novo=True), f"{c.codigo} · {c.nome}"
        valores.pop("codigo")
        rot = f"{alvo.codigo} · {valores.get('nome', alvo.nome)}"
        return self._gravar(n, alvo, _mudancas(alvo, valores), rot, novo=False), rot

    # ------------------------------------------------------------------------------------------- contas
    def _contas(self, n: int, dados: dict) -> tuple[str, str]:
        db = self.db
        with _na_coluna("Nome"):
            nome = validar_nome(dados.get("nome"), o_que="o nome da conta")
        dados["nome"] = nome
        alvo = db.scalar(select(ContaFinanceira).where(func.lower(ContaFinanceira.nome) == nome.lower()))
        if alvo is None:
            if dados.get("saldo_inicial") is None:
                raise ErroLinha("Saldo inicial", "Informe o saldo inicial.")
            if dados.get("data_base") is None:
                raise ErroLinha("Data-base", "Informe a data-base do saldo.")
            c = ContaFinanceira(**dados)
            return self._gravar(n, c, {}, c.nome, novo=True), c.nome
        dados.pop("nome")
        muda = _mudancas(alvo, dados)
        muda_saldo, muda_data = "saldo_inicial" in muda, "data_base" in muda
        if muda_saldo or muda_data:
            from app.modules.financeiro.models import Baixa, Transferencia

            tem = bool(db.scalar(select(Baixa.id).where(Baixa.conta_id == alvo.id, Baixa.estornada.is_(False)).limit(1))
                       or db.scalar(select(Transferencia.id).where(or_(Transferencia.conta_origem_id == alvo.id,
                                                                       Transferencia.conta_destino_id == alvo.id))
                                    .limit(1)))
            with _na_coluna("Saldo inicial" if muda_saldo else "Data-base"):
                validar_edicao_conta(tem_movimento=tem, muda_saldo_inicial=muda_saldo, muda_data_base=muda_data)
        return self._gravar(n, alvo, muda, alvo.nome, novo=False), alvo.nome
