"""Motor REAL das automações: fotografa o estado do banco, avalia os gatilhos (puro, `app.domain.automacao`) e executa.

Garantias:
- **Idempotência**: cada execução tem `chave_idempotencia` ÚNICA = automação:registro:ocorrência. Rodar duas vezes
  (ou dois workers ao mesmo tempo) não duplica: a UNIQUE do banco decide.
- **Retentativas limitadas**: execução que falhou repete até `MAX_TENTATIVAS`; depois fica "falhou" no histórico.
- **Prevenção de ciclo**: atividade criada por uma automação não dispara a mesma automação (via `registro_criado`).
- **Criar atividade ≠ enviar**: ações de envio ficam "pendente_conector" (nenhuma mensagem sai nesta fase).
- **Cobrança**: só títulos aberto/parcial com saldo e sem contestação (as regras estão no domínio).

Não depende de chamadas dos outros módulos: lê as tabelas (oportunidade_evento, atividade, titulo, baixa, cobranca…).
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import agora
from app.core.models import PerfilAcesso, Usuario
from app.domain import RegraViolada
from app.domain import automacao as dom
from app.domain.atividade import validar_atividade
from app.modules.comercial.models import Atividade, Comunicacao, Etapa, Oportunidade, OportunidadeEvento
from app.modules.financeiro.models import Baixa, Cobranca, Recorrencia, Titulo
from app.modules.nucleo.models import CampoCustom, Empresa, Pessoa
from app.modules.orquestracao.ia.ferramentas import calcular_caixa
from app.modules.orquestracao.models import Automacao, AutomacaoExecucao

log = logging.getLogger(__name__)
JANELA_EVENTOS_DIAS = 30


def _data(v: datetime | date | None) -> date | None:
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v


def regra_de(a: Automacao, *, ativada_em: datetime | None = None) -> dom.Regra:
    return dom.Regra(a.id, a.area, a.gatilho, a.funil_id, a.etapa_destino_id, a.campo, a.operador, a.valor_esperado,
                     a.prazo_dias, ativada_em if ativada_em is not None else a.ativada_em)


# ------------------------------------------------------------------------------------------------ foto do estado
def fotografar(db: Session, hoje: date, areas: set[str] | None = None) -> dom.Estado:
    areas = areas or {"comercial", "financeiro"}
    desde = agora() - timedelta(days=JANELA_EVENTOS_DIAS)
    e = dom.Estado()
    empresas = dict(db.execute(select(Empresa.id, Empresa.nome)).all())
    if "comercial" in areas:
        etapas = {x.id: x for x in db.scalars(select(Etapa))}
        contatos = dict(db.execute(select(Pessoa.id, Pessoa.nome)).all())
        interacao: dict[int, date] = {}

        def marcar(oid: int | None, d: date | None) -> None:
            if oid and d and (oid not in interacao or d > interacao[oid]):
                interacao[oid] = d

        for oid, q in db.execute(select(OportunidadeEvento.oportunidade_id, func.max(OportunidadeEvento.quando))
                                 .group_by(OportunidadeEvento.oportunidade_id)):
            marcar(oid, _data(q))
        for oid, q in db.execute(select(Atividade.oportunidade_id, func.max(Atividade.concluida_em))
                                 .where(Atividade.status == "concluida").group_by(Atividade.oportunidade_id)):
            marcar(oid, _data(q))
        for oid, d in db.execute(select(Comunicacao.oportunidade_id, func.max(Comunicacao.data))
                                 .group_by(Comunicacao.oportunidade_id)):
            marcar(oid, _data(d))
        for o in db.scalars(select(Oportunidade)):
            marcar(o.id, _data(o.criado_em))
            et = etapas.get(o.etapa_id)
            e.oportunidades.append(dom.OportunidadeFoto(
                o.id, o.titulo, o.funil_id, o.etapa_id, et.nome if et else None, o.resultado, o.responsavel_id,
                o.valor_unico, o.empresa_id, empresas.get(o.empresa_id), contatos.get(o.contato_id),
                o.previsao_fechamento, o.proxima_acao, o.campos_custom or {}, interacao.get(o.id)))
        e.eventos = [dom.EventoFoto(x.id, x.oportunidade_id, x.tipo, x.quando)
                     for x in db.scalars(select(OportunidadeEvento).where(OportunidadeEvento.quando >= desde))]
        criadas: dict[int, set[int]] = {}
        for aid, reg in db.execute(select(AutomacaoExecucao.automacao_id, AutomacaoExecucao.registro_criado)
                                   .where(AutomacaoExecucao.registro_criado.like("atividade:%"))):
            criadas.setdefault(int(reg.split(":", 1)[1]), set()).add(aid)
        for a in db.scalars(select(Atividade).where(or_(
                Atividade.status == "pendente", Atividade.concluida_em >= desde))):
            e.atividades.append(dom.AtividadeFoto(
                a.id, a.assunto, a.tipo, a.status, a.prazo, a.responsavel_id, a.oportunidade_id, a.empresa_id,
                empresas.get(a.empresa_id), a.concluida_em, frozenset(criadas.get(a.id, set())), a.origem))
    if "financeiro" in areas:
        contestados = set(db.scalars(select(Cobranca.titulo_id).where(Cobranca.situacao == "em_contestacao")))
        ultima_baixa = dict(db.execute(select(Baixa.titulo_id, func.max(Baixa.criado_em))
                                       .where(Baixa.estornada.is_(False)).group_by(Baixa.titulo_id)).all())
        for t in db.scalars(select(Titulo).where(Titulo.status != "cancelado", or_(
                Titulo.status.in_(("aberto", "parcial")), Titulo.atualizado_em >= desde))):
            e.titulos.append(dom.TituloFoto(
                t.id, t.direcao, t.status, t.vencimento, t.valor_original, t.saldo, t.responsavel_id, t.descricao,
                t.empresa_id, empresas.get(t.empresa_id), t.id in contestados, t.confirmado_em, ultima_baixa.get(t.id),
                t.observacoes))
        geradas: dict[int, set[str]] = {}
        for rid, comp in db.execute(select(Titulo.origem_recorrencia_id, Titulo.competencia)
                                    .where(Titulo.origem_recorrencia_id.is_not(None))):
            if comp:
                geradas.setdefault(rid, set()).add(comp)
        for r in db.scalars(select(Recorrencia).where(Recorrencia.situacao == "ativa")):
            e.recorrencias.append(dom.RecorrenciaFoto(
                r.id, r.descricao, r.situacao, r.inicio, r.fim, r.frequencia, r.responsavel_id, r.empresa_id,
                empresas.get(r.empresa_id), frozenset(geradas.get(r.id, set()))))
        p = calcular_caixa(db)
        e.caixa = dom.CaixaFoto(p.saldo_projetado, p.formula)
    return e


# ------------------------------------------------------------------------------------------------ ações
def _gestor_padrao(db: Session) -> int | None:
    return db.scalar(select(Usuario.id).join(PerfilAcesso, PerfilAcesso.id == Usuario.perfil_acesso_id)
                     .where(PerfilAcesso.administrador.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))


def _responsavel(db: Session, a: Automacao, oc: dom.Ocorrencia) -> int:
    uid = dom.responsavel(a.responsavel_regra, oc.responsavel_id)
    if uid is not None and db.get(Usuario, uid) is not None:
        return uid
    uid = _gestor_padrao(db)
    if uid is None:
        raise RegraViolada("Nenhum responsável disponível para a automação.")
    return uid


def _criar_atividade(db: Session, a: Automacao, oc: dom.Ocorrencia, hoje: date, texto: str) -> tuple[str, str, str]:
    tipo = a.tipo_atividade or "tarefa"
    inicio, fim = (time(9, 0), time(10, 0)) if tipo == "reuniao" else (None, None)
    prazo = dom.prazo_da_atividade(a.gatilho, a.prazo_dias, hoje)
    assunto = (texto.splitlines()[0] if texto else a.nome)[:200]
    validar_atividade(assunto=assunto, tipo=tipo, prazo=prazo, hora_inicio=inicio, hora_fim=fim)
    objetivo = f"Automação \"{a.nome}\" · {oc.rotulo}\n{texto}"
    if tipo == "reuniao":
        objetivo += "\nHorário sugerido (09:00–10:00): ajuste antes de convidar. Convite depende de agenda conectada."
    at = Atividade(assunto=assunto, tipo=tipo, responsavel_id=_responsavel(db, a, oc), empresa_id=oc.empresa_id,
                   oportunidade_id=oc.oportunidade_id, prazo=prazo, hora_inicio=inicio, hora_fim=fim, objetivo=objetivo,
                   origem="automacao")
    db.add(at)
    db.flush()
    audit.registrar(db, usuario=None, acao="atividade.criar", entidade="atividade", entidade_id=at.id,
                    descricao=f"Criada pela automação #{a.id} · {a.nome}", depois=audit.snapshot(at))
    return "executada", f"atividade:{at.id}", f"Atividade criada: {assunto}"


def _atualizar_campo(db: Session, a: Automacao, oc: dom.Ocorrencia) -> tuple[str, str | None, str]:
    campo, valor = dom.parse_atualizacao(a.conteudo)
    if oc.registro_tipo == "oportunidade":
        o = db.get(Oportunidade, oc.registro_id)
        if o is None:
            raise RegraViolada("Oportunidade não encontrada.")
        antes = audit.snapshot(o)
        if campo in dom.CAMPOS_ATUALIZAVEIS["oportunidade"]:
            setattr(o, campo, valor[:300])
        else:
            existe = db.scalar(select(CampoCustom.id).where(CampoCustom.objeto == "oportunidade", CampoCustom.slug == campo,
                                                           CampoCustom.arquivado.is_(False)))
            if existe is None:
                raise RegraViolada(f"Campo \"{campo}\" não existe na oportunidade.")
            o.campos_custom = {**(o.campos_custom or {}), campo: valor}
        db.flush()
        x, y = audit.diff(antes, audit.snapshot(o))
        audit.registrar(db, usuario=None, acao="oportunidade.alterar", entidade="oportunidade", entidade_id=o.id,
                        descricao=f"Automação #{a.id} · {a.nome}", antes=x, depois=y)
        return "executada", None, f"{campo} = {valor} em {oc.rotulo}"
    if oc.registro_tipo == "titulo" and campo in dom.CAMPOS_ATUALIZAVEIS["titulo"]:
        t = db.get(Titulo, oc.registro_id)
        if t is None:
            raise RegraViolada("Título não encontrado.")
        antes = audit.snapshot(t)
        t.observacoes = ((t.observacoes + "\n") if t.observacoes else "") + valor
        db.flush()
        x, y = audit.diff(antes, audit.snapshot(t))
        audit.registrar(db, usuario=None, acao="titulo.alterar", entidade="titulo", entidade_id=t.id,
                        descricao=f"Automação #{a.id} · {a.nome}", antes=x, depois=y)
        return "executada", None, f"observações atualizadas em {oc.rotulo}"
    raise RegraViolada("Atualizar campo não se aplica a este registro.")


def aplicar_acao(db: Session, a: Automacao, oc: dom.Ocorrencia, hoje: date) -> tuple[str, str | None, str]:
    """(resultado, registro_criado, detalhe). Levanta RegraViolada quando não dá para executar."""
    texto = dom.renderizar(a.conteudo, oc.variaveis)
    if a.acao == "criar_atividade":
        return _criar_atividade(db, a, oc, hoje, texto)
    if a.acao == "notificar":
        uid = _responsavel(db, a, oc)
        return "notificado", f"usuario:{uid}", texto[:2000]
    if a.acao == "atualizar_campo":
        return _atualizar_campo(db, a, oc)
    if a.acao in dom.CANAL_DA_ACAO:
        return ("pendente_conector", None,
                f"Envio preparado ({dom.ACOES[a.acao]} · {a.destinatario}); aguardando conector autorizado. "
                f"Nenhuma mensagem foi enviada. Texto: {texto[:500]}")
    raise RegraViolada("Ação inválida.")


# ------------------------------------------------------------------------------------------------ execução
def _execucao(db: Session, chave: str) -> AutomacaoExecucao | None:
    return db.scalar(select(AutomacaoExecucao).where(AutomacaoExecucao.chave_idempotencia == chave))


def executar_ocorrencia(db: Session, a: Automacao, oc: dom.Ocorrencia, hoje: date) -> str:
    """Executa UMA ocorrência com idempotência. Devolve: executada | notificado | pendente_conector | falhou | repetida."""
    chave = dom.chave_idempotencia(a.id, oc)
    ex = _execucao(db, chave)
    if ex is not None and not dom.decidir_retentativa(ex.resultado, ex.tentativas):
        return "repetida"
    try:
        with db.begin_nested():
            if ex is None:
                ex = AutomacaoExecucao(automacao_id=a.id, chave_idempotencia=chave, registro=oc.registro, tentativas=0,
                                       simulacao=False, resultado="em_execucao")
                db.add(ex)
                db.flush()  # a UNIQUE decide se outra execução chegou antes
            resultado, criado, detalhe = aplicar_acao(db, a, oc, hoje)
            ex.tentativas += 1
            ex.quando, ex.resultado, ex.registro_criado, ex.detalhe, ex.erro = agora(), resultado, criado, detalhe, None
        db.commit()
        return resultado
    except IntegrityError:
        db.rollback()
        return "repetida"
    except Exception as e:  # noqa: BLE001 — falha da ação vira histórico, não derruba o motor
        db.rollback()
        msg = e.mensagem if isinstance(e, RegraViolada) else f"{type(e).__name__}: {e}"
        if not isinstance(e, RegraViolada):
            log.exception("Automação #%s falhou em %s", a.id, oc.registro)
        ex = _execucao(db, chave)
        if ex is None:
            ex = AutomacaoExecucao(automacao_id=a.id, chave_idempotencia=chave, registro=oc.registro, tentativas=0,
                                   simulacao=False)
            db.add(ex)
        ex.tentativas += 1
        ex.quando, ex.resultado, ex.erro, ex.detalhe = agora(), "falhou", msg[:2000], oc.rotulo
        db.commit()
        return "falhou"


def executar(db: Session, hoje: date) -> dict[str, int]:
    """Uma volta do motor sobre as automações ATIVAS. Devolve a contagem por resultado."""
    ativas = list(db.scalars(select(Automacao).where(Automacao.estado == "ativa").order_by(Automacao.id)))
    contagem: dict[str, int] = {}
    if not ativas:
        return contagem
    estado = fotografar(db, hoje, {a.area for a in ativas})
    for a in ativas:
        for oc in dom.ocorrencias(regra_de(a), estado, hoje):
            r = executar_ocorrencia(db, a, oc, hoje)
            contagem[r] = contagem.get(r, 0) + 1
    return contagem


def testar(db: Session, a: Automacao, hoje: date) -> dict[str, Any]:
    """Prévia de elegibilidade SEM executar: quantos registros casam hoje (eventos: últimos 7 dias se a automação
    ainda não foi ativada). Grava uma linha "simulada" no histórico; não cria atividade nem envia nada."""
    ativada = a.ativada_em if a.estado == "ativa" and a.ativada_em else agora() - timedelta(days=7)
    ocs = dom.ocorrencias(regra_de(a, ativada_em=ativada), fotografar(db, hoje, {a.area}), hoje)
    chaves = {dom.chave_idempotencia(a.id, oc) for oc in ocs}
    ja = set(db.scalars(select(AutomacaoExecucao.chave_idempotencia).where(
        AutomacaoExecucao.chave_idempotencia.in_(chaves)))) if chaves else set()
    novas = [oc for oc in ocs if dom.chave_idempotencia(a.id, oc) not in ja]
    acao = dom.ACOES[a.acao] + (f" / {dom.TIPOS_ATIVIDADE_ROTULO.get(a.tipo_atividade or '', '')}"
                                if a.acao == "criar_atividade" else "")
    resumo = f"{len(novas)} registro(s) elegível(is) hoje; {len(ja)} já executado(s) antes (não repetem)."
    observacao = "Prévia de elegibilidade: não cria tarefas e não envia mensagens."
    if a.gatilho in dom.GATILHOS_DE_EVENTO and a.estado != "ativa":
        observacao += " Gatilhos de evento consideram os últimos 7 dias; ao ativar, só eventos novos disparam."
    if a.acao in dom.CANAL_DA_ACAO:
        observacao += " Envios ficam pendentes de conector autorizado."
    db.add(AutomacaoExecucao(automacao_id=a.id, chave_idempotencia=f"teste:{a.id}:{uuid4().hex}"[:200],
                             registro=f"{len(novas)} registro(s)", resultado="simulada", simulacao=True,
                             tentativas=0, detalhe=resumo))
    return {"elegiveis": len(novas), "ja_executadas": len(ja), "amostra": [oc.rotulo for oc in novas[:10]],
            "acao": acao, "resumo": resumo, "observacao": observacao}
