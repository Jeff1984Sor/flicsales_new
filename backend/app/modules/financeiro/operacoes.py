"""Operações do Financeiro que tocam o banco (a regra mora em app/domain; aqui só carrega, chama o domínio e grava).

Usadas pelas rotas, pelo worker (tarefas.py) e pelos testes. Nenhuma função daqui faz commit: quem chama decide.

Concorrência da baixa: o débito do saldo é um UPDATE CONDICIONAL (`saldo >= valor` e título em aberto) feito no
banco, não "ler, subtrair e gravar". Duas baixas simultâneas que juntas estourariam o saldo: a segunda não casa a
condição (rowcount 0) e é recusada com a mensagem de saldo. Além disso a leitura usa `SELECT … FOR UPDATE` (no
Postgres trava a linha; no SQLite é ignorado) e o CHECK `saldo >= 0` do banco é a última barreira.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import agora
from app.core.models import Usuario
from app.domain import RegraViolada
from app.domain import caixa as dom_caixa
from app.domain import titulos as dom
from app.domain.cobranca import ROTULOS_SITUACAO
from app.domain.dinheiro import ZERO, dinheiro, formatar_brl
from app.domain.recorrencia import competencia_de, titulo_da_competencia
from app.modules.financeiro.models import Baixa, Cobranca, Recorrencia, Titulo, Transferencia
from app.modules.nucleo.models import Categoria, CentroCusto, ContaFinanceira, Empresa

LIMITE_BAIXA = "Baixas são gerenciais. Nenhuma operação bancária é executada."
LIMITE_CAIXA = ("Sem conciliação bancária. Saldo baseado em informações fornecidas. A projeção soma todos os títulos "
                "abertos e não representa disponibilidade garantida em uma data. Pipeline e transferências internas "
                "não são receita.")
LIMITE_OPERACAO = "Operação gerencial. Sem emissão fiscal, execução bancária ou acesso a contas reais."
LIMITE_AGING = "Saldo aberto de títulos confirmados (aberto/parcial). Rascunhos e previsão comercial ficam fora."


# ---------------------------------------------------------------- nomes (sem N+1)
def _nomes(db: Session, modelo, ids: set[int | None], coluna="nome") -> dict[int, str]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    col = getattr(modelo, coluna)
    return {i: n for i, n in db.execute(select(modelo.id, col).where(modelo.id.in_(ids)))}


def baixas_ativas_por_titulo(db: Session, ids: set[int]) -> set[int]:
    if not ids:
        return set()
    return set(db.scalars(select(Baixa.titulo_id).where(Baixa.titulo_id.in_(ids), Baixa.estornada.is_(False))))


def titulos_em_contestacao(db: Session, ids: set[int] | None = None) -> set[int]:
    q = select(Cobranca.titulo_id).where(Cobranca.situacao == "em_contestacao")
    if ids is not None:
        if not ids:
            return set()
        q = q.where(Cobranca.titulo_id.in_(ids))
    return set(db.scalars(q))


def titulos_para_saida(db: Session, titulos: list[Titulo], hoje: date) -> list[dict]:
    ids = {t.id for t in titulos}
    empresas = _nomes(db, Empresa, {t.empresa_id for t in titulos})
    categorias = _nomes(db, Categoria, {t.categoria_id for t in titulos})
    centros = _nomes(db, CentroCusto, {t.centro_custo_id for t in titulos})
    contas = _nomes(db, ContaFinanceira, {t.conta_prevista_id for t in titulos})
    usuarios = _nomes(db, Usuario, {t.responsavel_id for t in titulos} | {t.aprovado_por_id for t in titulos})
    ativas = baixas_ativas_por_titulo(db, ids)
    contestados = titulos_em_contestacao(db, ids)
    out = []
    for t in titulos:
        out.append({
            **{c: getattr(t, c) for c in (
                "id", "direcao", "empresa_id", "descricao", "documento", "emissao", "competencia", "vencimento",
                "valor_original", "saldo", "categoria_id", "centro_custo_id", "conta_prevista_id", "forma",
                "responsavel_id", "observacoes", "status", "aprovacao", "aprovado_em", "motivo_cancelamento",
                "cancelado_em", "confirmado_em", "origem_oportunidade_id", "origem_recorrencia_id", "parcela",
                "parcelas_total", "criado_em")},
            "empresa_nome": empresas.get(t.empresa_id, "—"),
            "categoria_nome": categorias.get(t.categoria_id),
            "centro_custo_nome": centros.get(t.centro_custo_id),
            "conta_prevista_nome": contas.get(t.conta_prevista_id),
            "responsavel_nome": usuarios.get(t.responsavel_id),
            "aprovado_por_nome": usuarios.get(t.aprovado_por_id),
            "estado": dom.status_exibido(t.status, t.vencimento, hoje),
            "dias_atraso": dom.dias_em_atraso(t.status, t.vencimento, hoje),
            "tem_baixa_ativa": t.id in ativas,
            "em_contestacao": t.id in contestados,
        })
    return out


def baixas_para_saida(db: Session, baixas: list[Baixa]) -> list[dict]:
    titulos = {t.id: t for t in db.scalars(select(Titulo).where(Titulo.id.in_({b.titulo_id for b in baixas})))} \
        if baixas else {}
    empresas = _nomes(db, Empresa, {t.empresa_id for t in titulos.values()})
    contas = _nomes(db, ContaFinanceira, {b.conta_id for b in baixas})
    usuarios = _nomes(db, Usuario, {b.registrada_por_id for b in baixas} | {b.estornada_por_id for b in baixas})
    out = []
    for b in baixas:
        t = titulos[b.titulo_id]
        out.append({
            **{c: getattr(b, c) for c in (
                "id", "titulo_id", "valor", "data", "conta_id", "forma", "referencia_comprovante", "observacao",
                "estornada", "estorno_motivo", "estornada_em", "criado_em")},
            "direcao": t.direcao, "empresa_nome": empresas.get(t.empresa_id, "—"), "titulo_descricao": t.descricao,
            "conta_nome": contas.get(b.conta_id, "—"), "registrada_por_nome": usuarios.get(b.registrada_por_id),
            "estornada_por_nome": usuarios.get(b.estornada_por_id),
        })
    return out


def cobrancas_para_saida(db: Session, cobrancas: list[Cobranca], hoje: date) -> list[dict]:
    titulos = {t.id: t for t in db.scalars(select(Titulo).where(Titulo.id.in_({c.titulo_id for c in cobrancas})))} \
        if cobrancas else {}
    empresas = _nomes(db, Empresa, {t.empresa_id for t in titulos.values()})
    usuarios = _nomes(db, Usuario, {c.responsavel_id for c in cobrancas})
    out = []
    for c in cobrancas:
        t = titulos[c.titulo_id]
        out.append({
            **{k: getattr(c, k) for k in (
                "id", "assunto", "titulo_id", "responsavel_id", "canal", "situacao", "data_prometida",
                "valor_prometido", "proximo_contato", "historico", "criado_em")},
            "titulo_descricao": t.descricao, "empresa_nome": empresas.get(t.empresa_id, "—"), "titulo_saldo": t.saldo,
            "titulo_estado": dom.status_exibido(t.status, t.vencimento, hoje),
            "responsavel_nome": usuarios.get(c.responsavel_id),
        })
    return out


def origem_do_titulo(db: Session, t: Titulo) -> dict:
    """"Oportunidade #n — título" (leitura do Comercial), "Recorrência #n — descrição" ou "Lançamento manual"."""
    if t.origem_oportunidade_id:
        from app.modules.comercial.models import Oportunidade

        op = db.get(Oportunidade, t.origem_oportunidade_id)
        nome = f" — {op.titulo}" if op else ""
        return {"tipo": "oportunidade", "id": t.origem_oportunidade_id,
                "rotulo": f"Oportunidade #{t.origem_oportunidade_id}{nome}"}
    if t.origem_recorrencia_id:
        rec = db.get(Recorrencia, t.origem_recorrencia_id)
        nome = f" — {rec.descricao}" if rec else ""
        return {"tipo": "recorrencia", "id": t.origem_recorrencia_id,
                "rotulo": f"Recorrência #{t.origem_recorrencia_id}{nome} · competência {t.competencia or '—'}"}
    return {"tipo": "manual", "id": None, "rotulo": "Lançamento manual"}


# ---------------------------------------------------------------- baixa e estorno
def conta_ativa(db: Session, conta_id: int | None) -> ContaFinanceira | None:
    conta = db.get(ContaFinanceira, conta_id) if conta_id else None
    return conta if conta is not None and conta.ativo else None


def debitar_saldo(db: Session, titulo_id: int, valor: Decimal) -> bool:
    """UPDATE condicional: só debita se ainda houver saldo e o título estiver em aberto. False = outra baixa venceu."""
    r = db.execute(
        update(Titulo)
        .where(Titulo.id == titulo_id, Titulo.saldo >= valor, Titulo.status.in_(dom.EM_ABERTO))
        .values(saldo=Titulo.saldo - valor)
        .execution_options(synchronize_session=False))
    return r.rowcount == 1


def registrar_baixa(db: Session, *, titulo: Titulo, valor, data: date, conta_id: int, forma: str,
                    referencia_comprovante: str | None, observacao: str | None, usuario: Usuario | None,
                    hoje: date) -> Baixa:
    conta = conta_ativa(db, conta_id)
    v = dom.validar_baixa(direcao=titulo.direcao, status=titulo.status, aprovacao=titulo.aprovacao,
                          saldo=titulo.saldo, valor=valor, data=data,
                          data_base_conta=conta.data_base if conta else None, hoje=hoje)
    if not debitar_saldo(db, titulo.id, v):
        db.rollback()
        raise RegraViolada(dom.MSG_BAIXA_VALOR)
    db.refresh(titulo)
    antes_status = titulo.status
    titulo.status = dom.status_por_saldo(titulo.status, titulo.valor_original, dinheiro(titulo.saldo))
    b = Baixa(titulo_id=titulo.id, valor=v, data=data, conta_id=conta.id, forma=forma,
              referencia_comprovante=referencia_comprovante, observacao=observacao,
              registrada_por_id=usuario.id if usuario else None)
    db.add(b)
    db.flush()
    tipo = "Recebimento" if titulo.direcao == "receber" else "Pagamento"
    audit.registrar(db, usuario=usuario, acao="baixa.registrar", entidade="baixa", entidade_id=b.id,
                    descricao=f"{tipo} de {formatar_brl(v)} no título #{titulo.id} ({titulo.descricao})",
                    antes={"titulo_id": titulo.id, "status": antes_status},
                    depois={"titulo_id": titulo.id, "status": titulo.status, "saldo": str(titulo.saldo),
                            "valor": str(v), "conta_id": conta.id, "data": data.isoformat()})
    return b


def estornar_baixa(db: Session, *, baixa: Baixa, motivo: str | None, usuario: Usuario | None) -> Titulo:
    titulo = db.get(Titulo, baixa.titulo_id, with_for_update=True)
    dom.aplicar_estorno(valor_original=titulo.valor_original, saldo=titulo.saldo, status=titulo.status,
                        valor_baixa=baixa.valor, ja_estornada=baixa.estornada, motivo=motivo)
    # marca a baixa só se ainda não estiver estornada (dois estornos simultâneos: só um vale)
    r = db.execute(update(Baixa).where(Baixa.id == baixa.id, Baixa.estornada.is_(False))
                   .values(estornada=True, estorno_motivo=motivo.strip(), estornada_em=agora(),
                           estornada_por_id=usuario.id if usuario else None)
                   .execution_options(synchronize_session=False))
    if r.rowcount != 1:
        db.rollback()
        raise RegraViolada("Esta baixa já foi estornada.")
    r = db.execute(update(Titulo).where(Titulo.id == titulo.id, Titulo.saldo + baixa.valor <= Titulo.valor_original)
                   .values(saldo=Titulo.saldo + baixa.valor).execution_options(synchronize_session=False))
    if r.rowcount != 1:
        db.rollback()
        raise RegraViolada("O estorno não pode deixar o saldo acima do valor original.")
    db.refresh(titulo)
    db.refresh(baixa)
    antes_status = titulo.status
    titulo.status = dom.status_por_saldo(titulo.status, titulo.valor_original, dinheiro(titulo.saldo))
    audit.registrar(db, usuario=usuario, acao="baixa.estornar", entidade="baixa", entidade_id=baixa.id,
                    descricao=f"Estorno de {formatar_brl(baixa.valor)} no título #{titulo.id}: {motivo.strip()}",
                    antes={"estornada": False, "titulo_status": antes_status},
                    depois={"estornada": True, "titulo_status": titulo.status, "saldo": str(titulo.saldo)})
    return titulo


# ---------------------------------------------------------------- recorrência → título em rascunho
def competencias_geradas(db: Session, recorrencia_id: int) -> set[str]:
    return {c for c in db.scalars(select(Titulo.competencia).where(Titulo.origem_recorrencia_id == recorrencia_id))
            if c}


def gerar_competencia(db: Session, rec: Recorrencia, competencia: str, usuario: Usuario | None) -> Titulo:
    """Um título em RASCUNHO para a competência (sem duplicar: domínio + UNIQUE do banco)."""
    existentes = competencias_geradas(db, rec.id)
    p = titulo_da_competencia(recorrencia_id=rec.id, situacao=rec.situacao, inicio=rec.inicio, fim=rec.fim,
                              frequencia=rec.frequencia, dia_vencimento=rec.dia_vencimento,
                              valor_ciclo=rec.valor_ciclo, competencia=competencia, existentes=existentes)
    responsavel = rec.responsavel_id or (usuario.id if usuario else None) or db.scalar(
        select(Usuario.id).where(Usuario.ativo.is_(True)).order_by(Usuario.id))
    ano, mes = competencia.split("-")
    t = Titulo(direcao=rec.direcao, empresa_id=rec.empresa_id, descricao=f"{rec.descricao} • {mes}/{ano}",
               competencia=competencia, vencimento=p.vencimento, valor_original=p.valor, saldo=p.valor,
               categoria_id=rec.categoria_id, centro_custo_id=rec.centro_custo_id, responsavel_id=responsavel,
               status="rascunho", aprovacao=dom.aprovacao_inicial(rec.direcao), origem_recorrencia_id=rec.id)
    db.add(t)
    db.flush()
    audit.registrar(db, usuario=usuario, acao="recorrencia.gerar_competencia", entidade="titulo", entidade_id=t.id,
                    descricao=f"{rec.descricao} / {competencia} (rascunho)", depois=audit.snapshot(t))
    return t


def proxima_competencia(rec: Recorrencia, existentes: set[str], hoje: date) -> str | None:
    """Primeira competência alinhada, na vigência, sem título, a partir do mês atual (para a tela)."""
    from app.domain.recorrencia import competencias_a_gerar

    candidatas = competencias_a_gerar(situacao=rec.situacao, inicio=rec.inicio, fim=rec.fim,
                                      frequencia=rec.frequencia, ate=rec.fim, existentes=existentes)
    atual = competencia_de(hoje)
    futuras = [c for c in candidatas if c >= atual]
    return futuras[0] if futuras else None


# ---------------------------------------------------------------- caixa
@dataclass
class Caixa:
    contas: list[ContaFinanceira]
    saldos: dict[int, Decimal]
    projecao: dom_caixa.Projecao


def calcular_caixa(db: Session) -> Caixa:
    contas = list(db.scalars(select(ContaFinanceira).order_by(ContaFinanceira.nome)))
    movimentos = [dom_caixa.Movimento(conta_id=c, direcao=d, valor=v, estornada=e) for c, d, v, e in db.execute(
        select(Baixa.conta_id, Titulo.direcao, Baixa.valor, Baixa.estornada).join(Titulo, Titulo.id == Baixa.titulo_id))]
    transferencias = [dom_caixa.TransferenciaInfo(o, d, v) for o, d, v in db.execute(
        select(Transferencia.conta_origem_id, Transferencia.conta_destino_id, Transferencia.valor))]
    infos = [dom_caixa.Conta(c.id, c.saldo_inicial, c.data_base) for c in contas]
    saldos = dom_caixa.saldo_por_conta(infos, movimentos, transferencias)
    total = sum(saldos.values(), ZERO)
    abertos = [dom_caixa.TituloAberto(d, s, v) for d, s, v in db.execute(
        select(Titulo.direcao, Titulo.status, Titulo.saldo).where(Titulo.status.in_(dom.EM_ABERTO)))]
    return Caixa(contas, saldos, dom_caixa.projecao(total, abertos))


def titulos_aging(db: Session) -> list[dom.TituloAging]:
    return [dom.TituloAging(d, s, v, sa) for d, s, v, sa in db.execute(
        select(Titulo.direcao, Titulo.status, Titulo.vencimento, Titulo.saldo).where(Titulo.status.in_(dom.EM_ABERTO)))]


def vencidos_a_receber(db: Session, hoje: date) -> list[Titulo]:
    return list(db.scalars(select(Titulo).where(
        Titulo.direcao == "receber", Titulo.status.in_(dom.EM_ABERTO), Titulo.vencimento < hoje, Titulo.saldo > 0)
        .order_by(Titulo.vencimento, Titulo.id)))


def aprovacoes_pendentes(db: Session) -> int:
    return db.scalar(select(func.count(Titulo.id)).where(
        Titulo.direcao == "pagar", Titulo.status != "cancelado",
        or_(Titulo.aprovacao.is_(None), Titulo.aprovacao != "aprovado"))) or 0


def rotulo_situacao(s: str) -> str:
    return ROTULOS_SITUACAO.get(s, s)


__all__ = [
    "LIMITE_AGING", "LIMITE_BAIXA", "LIMITE_CAIXA", "LIMITE_OPERACAO", "aprovacoes_pendentes", "baixas_para_saida",
    "calcular_caixa", "cobrancas_para_saida", "conta_ativa", "debitar_saldo", "estornar_baixa", "gerar_competencia",
    "origem_do_titulo", "proxima_competencia", "registrar_baixa", "titulos_aging", "titulos_em_contestacao",
    "titulos_para_saida", "vencidos_a_receber",
]
