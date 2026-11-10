"""Ferramentas de LEITURA por domínio. Cada uma checa a permissão `*.ver` do usuário antes de devolver dado e respeita
o escopo "só meus registros" — a IA nunca amplia acesso. Sem permissão a ferramenta não roda e entra em `negadas`
(vira um limite na resposta: "Sem acesso pelo seu perfil: …").

| nome           | dados                                                         | permissão                   |
|----------------|---------------------------------------------------------------|-----------------------------|
| oportunidades  | oportunidades (etapa, valor, próxima ação, dias na etapa)     | comercial.oportunidades.ver |
| atividades     | atividades pendentes/recentes (prazo, status, origem)         | comercial.atividades.ver    |
| comunicacoes   | conversas vinculadas (conteúdo entra como DADO importado)     | comercial.comunicacoes.ver  |
| titulos        | títulos a receber/pagar (saldo, vencimento, cobrança)         | financeiro.titulos.ver      |
| baixas         | baixas dos últimos 60 dias (recebimentos/pagamentos)          | financeiro.baixas.ver       |
| caixa          | saldo gerencial e projeção (fórmula visível)                  | financeiro.caixa.ver        |
| cadastros      | empresas e pessoas (papéis, responsável)                      | nucleo.cadastros.ver        |
| desempenho     | conversão, ticket médio, ciclo mediano (fórmulas do domínio)  | comercial.desempenho.ver    |

Cada ferramenta também preenche os resumos de `app.domain.leitura` (para a leitura por regras sem IA).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select

from app.domain import leitura as lei
from app.domain.caixa import Conta, Movimento, Projecao, TituloAberto, TransferenciaInfo, projecao, saldo_gerencial
from app.domain.dinheiro import formatar_brl
from app.domain.funil import dias_na_etapa
from app.domain.indicadores import FORMULAS, ciclo_mediano, conversao, ticket_medio
from app.domain.titulos import status_exibido
from app.modules.comercial.models import Atividade, Comunicacao, Etapa, Oportunidade
from app.modules.financeiro.models import Baixa, Cobranca, Titulo, Transferencia
from app.modules.nucleo.models import ContaFinanceira, Empresa, Pessoa

LIMITE_ITENS = 40
LIMITE_CONTEUDO = 1500


@dataclass
class Foco:
    """Filtro do escopo "Este registro" (None = sem filtro)."""
    tipo: str
    id: int
    rotulo: str = ""
    oportunidade_id: int | None = None
    empresa_id: int | None = None
    titulo_id: int | None = None
    atividade_id: int | None = None
    comunicacao_id: int | None = None


@dataclass
class Coleta:
    hoje: date
    ferramentas: list[str] = field(default_factory=list)  # rótulos consultados
    negadas: list[str] = field(default_factory=list)  # rótulos sem permissão
    dados: dict[str, Any] = field(default_factory=dict)  # nome → itens (vai para o prompt como dado)
    importado: list[dict[str, str]] = field(default_factory=list)  # {fonte, texto} — conteúdo de terceiros
    titulos: list[lei.TituloResumo] = field(default_factory=list)
    oportunidades: list[lei.OportunidadeResumo] = field(default_factory=list)
    atividades: list[lei.AtividadeResumo] = field(default_factory=list)


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    rotulo: str
    permissao: str
    fn: Callable[[Any, Foco | None, Coleta], None]


def _empresas(ctx, ids: set[int]) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(ctx.db.execute(select(Empresa.id, Empresa.nome).where(Empresa.id.in_(ids))).all())


# ------------------------------------------------------------------------------------------------ comercial
def _oportunidades(ctx, foco: Foco | None, c: Coleta) -> None:
    q = ctx.filtrar_meus(select(Oportunidade), Oportunidade.responsavel_id)
    if foco and foco.oportunidade_id:
        q = q.where(Oportunidade.id == foco.oportunidade_id)
    elif foco and foco.empresa_id:
        q = q.where(Oportunidade.empresa_id == foco.empresa_id)
    q = q.order_by((Oportunidade.resultado != "aberta"), Oportunidade.valor_unico.desc(), Oportunidade.id)
    opps = list(ctx.db.scalars(q.limit(LIMITE_ITENS)))
    etapas = {e.id: e for e in ctx.db.scalars(select(Etapa).where(Etapa.id.in_({o.etapa_id for o in opps if o.etapa_id})))}
    emp = _empresas(ctx, {o.empresa_id for o in opps})
    itens = []
    for o in opps:
        etapa = etapas.get(o.etapa_id)
        itens.append({
            "fonte": f"Comercial › Oportunidades › #{o.id}", "id": o.id, "titulo": o.titulo,
            "empresa": emp.get(o.empresa_id), "etapa": etapa.nome if etapa else None, "resultado": o.resultado,
            "valor_unico": formatar_brl(o.valor_unico), "mrr": formatar_brl(o.valor_recorrente_mensal),
            "probabilidade_etapa": etapa.probabilidade if etapa else None,
            "dias_na_etapa": dias_na_etapa(o.entrou_etapa_em, c.hoje) if o.entrou_etapa_em else None,
            "limite_dias_etapa": etapa.limite_dias if etapa else None,
            "proxima_acao": o.proxima_acao, "proxima_acao_prazo": o.proxima_acao_prazo,
            "previsao_fechamento": o.previsao_fechamento, "necessidade": o.necessidade, "decisor": o.decisor,
            "campos_personalizados": o.campos_custom or {}, "motivo_perda": o.motivo_perda,
        })
        c.oportunidades.append(lei.OportunidadeResumo(
            o.id, o.titulo, emp.get(o.empresa_id), etapa.nome if etapa else None, o.valor_unico, o.proxima_acao,
            o.entrou_etapa_em, etapa.limite_dias if etapa else None, o.resultado))
    c.dados["oportunidades"] = itens


def _atividades(ctx, foco: Foco | None, c: Coleta) -> None:
    q = ctx.filtrar_meus(select(Atividade), Atividade.responsavel_id)
    if foco and foco.atividade_id:
        q = q.where(Atividade.id == foco.atividade_id)
    elif foco and foco.oportunidade_id:
        q = q.where(Atividade.oportunidade_id == foco.oportunidade_id)
    elif foco and foco.empresa_id:
        q = q.where(Atividade.empresa_id == foco.empresa_id)
    else:
        q = q.where(or_(Atividade.status == "pendente", Atividade.prazo >= c.hoje - timedelta(days=14)))
    atividades = list(ctx.db.scalars(q.order_by(Atividade.status.desc(), Atividade.prazo, Atividade.id).limit(LIMITE_ITENS)))
    emp = _empresas(ctx, {a.empresa_id for a in atividades})
    c.dados["atividades"] = [{
        "fonte": f"Comercial › Atividades › #{a.id}", "id": a.id, "assunto": a.assunto, "tipo": a.tipo,
        "status": a.status, "prazo": a.prazo, "atrasada": a.status == "pendente" and a.prazo < c.hoje,
        "empresa": emp.get(a.empresa_id), "oportunidade_id": a.oportunidade_id, "objetivo": a.objetivo,
        "resultado": a.resultado, "origem": a.origem} for a in atividades]
    c.atividades.extend(lei.AtividadeResumo(a.id, a.assunto, a.prazo, a.status, emp.get(a.empresa_id)) for a in atividades)


def _comunicacoes(ctx, foco: Foco | None, c: Coleta) -> None:
    q = select(Comunicacao)
    if ctx.somente_meus_registros():  # comunicação herda o responsável da oportunidade vinculada
        minhas = ctx.filtrar_meus(select(Oportunidade.id), Oportunidade.responsavel_id)
        q = q.where(Comunicacao.oportunidade_id.in_(minhas))
    if foco and foco.comunicacao_id:
        q = q.where(Comunicacao.id == foco.comunicacao_id)
    elif foco and foco.oportunidade_id:
        q = q.where(Comunicacao.oportunidade_id == foco.oportunidade_id)
    elif foco and foco.empresa_id:
        q = q.where(Comunicacao.empresa_id == foco.empresa_id)
    comunicacoes = list(ctx.db.scalars(q.order_by(Comunicacao.data.desc(), Comunicacao.id.desc()).limit(15)))
    emp = _empresas(ctx, {x.empresa_id for x in comunicacoes})
    itens = []
    for x in comunicacoes:
        fonte = f"Comercial › Comunicações › #{x.id} ({x.canal}{', ' + x.data.strftime('%d/%m') if x.data else ''})"
        itens.append({"fonte": fonte, "id": x.id, "canal": x.canal, "titulo": x.titulo, "data": x.data,
                      "empresa": emp.get(x.empresa_id), "oportunidade_id": x.oportunidade_id,
                      "analise_registrada": x.analise})
        c.importado.append({"fonte": fonte, "texto": (x.conteudo or "")[:LIMITE_CONTEUDO]})
    c.dados["comunicacoes"] = itens


def _desempenho(ctx, foco: Foco | None, c: Coleta) -> None:
    q = ctx.filtrar_meus(select(Oportunidade), Oportunidade.responsavel_id).where(Oportunidade.resultado != "aberta")
    encerradas = list(ctx.db.scalars(q))
    ganhas = [o for o in encerradas if o.resultado == "ganha"]
    receita = sum((o.valor_unico for o in ganhas), Decimal("0"))
    pares = [(o.criado_em.date(), o.ganha_em) for o in ganhas if o.ganha_em and o.criado_em]
    conv, tick, ciclo = conversao(len(ganhas), len(encerradas) - len(ganhas)), ticket_medio(receita, len(ganhas)), \
        ciclo_mediano(pares)
    c.dados["desempenho"] = {
        "fonte": "Comercial › Desempenho (calculado em código)", "ganhas": len(ganhas),
        "perdidas": len(encerradas) - len(ganhas), "receita_ganha": formatar_brl(receita),
        "conversao_pct": str(conv) if conv is not None else None, "ticket_medio": formatar_brl(tick) if tick else None,
        "ciclo_mediano_dias": str(ciclo) if ciclo is not None else None, "formulas": FORMULAS,
        "observacao": "Sem ranking de pessoas; indicadores do escopo do seu perfil."}


# ------------------------------------------------------------------------------------------------ financeiro
def _titulos(ctx, foco: Foco | None, c: Coleta) -> None:
    q = ctx.filtrar_meus(select(Titulo), Titulo.responsavel_id)
    if foco and foco.titulo_id:
        q = q.where(Titulo.id == foco.titulo_id)
    elif foco and foco.oportunidade_id:
        q = q.where(Titulo.origem_oportunidade_id == foco.oportunidade_id)
    elif foco and foco.empresa_id:
        q = q.where(Titulo.empresa_id == foco.empresa_id)
    else:
        q = q.where(Titulo.status.in_(("rascunho", "aberto", "parcial")))
    titulos = list(ctx.db.scalars(q.order_by(Titulo.vencimento, Titulo.id).limit(LIMITE_ITENS)))
    emp = _empresas(ctx, {t.empresa_id for t in titulos})
    cobrancas: dict[int, str] = {}
    if titulos and ctx.pode("financeiro.cobrancas.ver"):
        for tid, situacao in ctx.db.execute(select(Cobranca.titulo_id, Cobranca.situacao).where(
                Cobranca.titulo_id.in_([t.id for t in titulos]))):
            cobrancas[tid] = situacao
    rotulo = {"receber": "A receber", "pagar": "A pagar"}
    c.dados["titulos"] = [{
        "fonte": f"Financeiro › {rotulo[t.direcao]} › título #{t.id}", "id": t.id, "direcao": t.direcao,
        "empresa": emp.get(t.empresa_id), "descricao": t.descricao, "vencimento": t.vencimento,
        "valor_original": formatar_brl(t.valor_original), "saldo": formatar_brl(t.saldo),
        "situacao": status_exibido(t.status, t.vencimento, c.hoje), "aprovacao": t.aprovacao,
        "origem_oportunidade_id": t.origem_oportunidade_id, "cobranca": cobrancas.get(t.id)} for t in titulos]
    c.titulos.extend(lei.TituloResumo(t.id, emp.get(t.empresa_id) or "—", t.descricao, t.direcao, t.status,
                                      t.vencimento, t.saldo) for t in titulos)


def _baixas(ctx, foco: Foco | None, c: Coleta) -> None:
    q = select(Baixa, Titulo).join(Titulo, Titulo.id == Baixa.titulo_id)
    q = ctx.filtrar_meus(q, Titulo.responsavel_id)
    if foco and foco.titulo_id:
        q = q.where(Baixa.titulo_id == foco.titulo_id)
    elif foco and foco.empresa_id:
        q = q.where(Titulo.empresa_id == foco.empresa_id)
    else:
        q = q.where(Baixa.data >= c.hoje - timedelta(days=60))
    linhas = ctx.db.execute(q.order_by(Baixa.data.desc(), Baixa.id.desc()).limit(LIMITE_ITENS)).all()
    emp = _empresas(ctx, {t.empresa_id for _, t in linhas})
    c.dados["baixas"] = [{
        "fonte": f"Financeiro › Baixas e estornos › baixa #{b.id}", "titulo_id": t.id, "empresa": emp.get(t.empresa_id),
        "tipo": "recebimento" if t.direcao == "receber" else "pagamento", "valor": formatar_brl(b.valor),
        "data": b.data, "estornada": b.estornada} for b, t in linhas]


def calcular_caixa(db) -> Projecao:
    """Saldo gerencial (contas + baixas não estornadas + transferências) e projeção com os títulos abertos.
    Usado pela ferramenta `caixa` e pelo gatilho "Saldo projetado abaixo do limite"."""
    contas = [Conta(x.id, x.saldo_inicial, x.data_base) for x in db.scalars(select(ContaFinanceira))]
    movimentos = [Movimento(b.conta_id, t.direcao, b.valor, b.estornada)
                  for b, t in db.execute(select(Baixa, Titulo).join(Titulo, Titulo.id == Baixa.titulo_id))]
    transf = [TransferenciaInfo(t.conta_origem_id, t.conta_destino_id, t.valor) for t in db.scalars(select(Transferencia))]
    abertos = [TituloAberto(t.direcao, t.status, t.saldo) for t in db.scalars(
        select(Titulo).where(Titulo.status.in_(("aberto", "parcial"))))]
    return projecao(saldo_gerencial(contas, movimentos, transf), abertos)


def _caixa(ctx, foco: Foco | None, c: Coleta) -> None:
    p = calcular_caixa(ctx.db)
    c.dados["caixa"] = {"fonte": "Financeiro › Caixa", "saldo_gerencial": formatar_brl(p.saldo_atual),
                        "entradas_abertas": formatar_brl(p.entradas_abertas), "saidas_abertas": formatar_brl(p.saidas_abertas),
                        "saldo_projetado": formatar_brl(p.saldo_projetado), "formula": p.formula,
                        "limite": "Sem conciliação bancária: saldo gerencial pelas baixas registradas."}


# ------------------------------------------------------------------------------------------------ cadastros
def _cadastros(ctx, foco: Foco | None, c: Coleta) -> None:
    q = select(Empresa).where(Empresa.ativo.is_(True))
    if foco and foco.empresa_id:
        q = select(Empresa).where(Empresa.id == foco.empresa_id)
    empresas = list(ctx.db.scalars(q.order_by(Empresa.nome).limit(LIMITE_ITENS)))
    total = ctx.db.scalar(select(func.count(Empresa.id)).where(Empresa.ativo.is_(True)))
    pessoas: dict[int, list[str]] = {}
    for p in ctx.db.scalars(select(Pessoa).where(Pessoa.empresa_id.in_([e.id for e in empresas]), Pessoa.ativo.is_(True))):
        pessoas.setdefault(p.empresa_id, []).append(f"{p.nome}{' (' + p.cargo + ')' if p.cargo else ''}")
    c.dados["cadastros"] = {"fonte": "Núcleo › Cadastros mestres", "empresas_ativas": total, "empresas": [{
        "fonte": f"Núcleo › Empresas › #{e.id}", "id": e.id, "nome": e.nome, "papeis": e.papeis,
        "segmento": e.segmento, "contatos": pessoas.get(e.id, [])} for e in empresas]}


FERRAMENTAS: dict[str, Ferramenta] = {f.nome: f for f in [
    Ferramenta("oportunidades", "Oportunidades", "comercial.oportunidades.ver", _oportunidades),
    Ferramenta("atividades", "Atividades", "comercial.atividades.ver", _atividades),
    Ferramenta("comunicacoes", "Comunicações", "comercial.comunicacoes.ver", _comunicacoes),
    Ferramenta("desempenho", "Desempenho", "comercial.desempenho.ver", _desempenho),
    Ferramenta("titulos", "Títulos a receber e a pagar", "financeiro.titulos.ver", _titulos),
    Ferramenta("baixas", "Baixas", "financeiro.baixas.ver", _baixas),
    Ferramenta("caixa", "Caixa", "financeiro.caixa.ver", _caixa),
    Ferramenta("cadastros", "Cadastros", "nucleo.cadastros.ver", _cadastros),
]}


def coletar(ctx, nomes: list[str], foco: Foco | None, hoje: date) -> Coleta:
    """Roda as ferramentas pedidas, SÓ as permitidas ao usuário."""
    c = Coleta(hoje=hoje)
    for nome in nomes:
        f = FERRAMENTAS[nome]
        if not ctx.pode(f.permissao):
            c.negadas.append(f.rotulo)
            continue
        f.fn(ctx, foco, c)
        c.ferramentas.append(f.rotulo)
    return c
