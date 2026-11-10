"""Serviços da IA unificada: perguntar, leitura do momento e análise de comunicação.

Fluxo comum: coletar (ferramentas com permissão) → IA ligada? → prompt anti-injeção → JSON validado por Pydantic
(1 nova tentativa se vier fora do formato) → saneamento. Sem IA, ou se a IA falhar, o mesmo formato sai das regras
determinísticas (`app.domain.leitura`, `heuristica`) e a resposta diz o porquê em `limites`.
"""

import logging
from datetime import date
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.core import audit
from app.core import ia as core_ia
from app.core.db import agora
from app.domain import leitura as lei
from app.modules.comercial.models import Comunicacao, Oportunidade
from app.modules.orquestracao.ia import contexto as cx
from app.modules.orquestracao.ia import formato, gateway, heuristica
from app.modules.orquestracao.ia.ferramentas import Foco, coletar
from app.modules.orquestracao.models import IaConversa, IaMensagem

log = logging.getLogger(__name__)

AVISO_RETENTATIVA = ("\n\nATENÇÃO: a resposta anterior veio fora do formato ({erro}). Responda de novo APENAS com o JSON "
                     "no formato pedido.")


class FormatoInvalido(Exception):
    pass


def gerar_validado(db, sistema: str, usuario: str, modelo: type[BaseModel]) -> BaseModel:
    """Chama a IA e valida com Pydantic; se vier fora do formato, UMA nova tentativa. Depois, FormatoInvalido.
    Erros do provedor sobem como `core_ia.IAIndisponivel` (mensagem pronta)."""
    erro = ""
    for tentativa in range(2):
        bruto = gateway.gerar(db, sistema, usuario if tentativa == 0 else usuario + AVISO_RETENTATIVA.format(erro=erro))
        try:
            if not isinstance(bruto, dict):
                raise TypeError("não é um objeto JSON")
            return modelo.model_validate(bruto)
        except ValidationError as e:
            erro = formato.resumo_erro(e)
        except TypeError as e:
            erro = str(e)
        log.info("IA fora do formato (tentativa %d): %s", tentativa + 1, erro)
    raise FormatoInvalido(erro)


def _limites_permissao(negadas: list[str]) -> list[str]:
    return [f"Sem acesso pelo seu perfil: {', '.join(negadas)} (não consultado)."] if negadas else []


def _regras(coleta, *, ia_ligada: bool, motivo: str | None = None, pergunta: str | None = None) -> dict[str, Any]:
    r = lei.ler_momento(hoje=coleta.hoje, titulos=coleta.titulos, oportunidades=coleta.oportunidades,
                        atividades=coleta.atividades, ia_ligada=False)
    extras = []
    if motivo:
        extras.append(motivo)
    if pergunta:
        extras.append("A leitura por regras não interpreta a pergunta em texto livre: mostra as prioridades do escopo.")
    r["limites"] = list(dict.fromkeys([*r["limites"], *extras, *_limites_permissao(coleta.negadas)]))
    r["ferramentas"] = coleta.ferramentas
    r["ia_ligada"] = ia_ligada
    return r


def responder(ctx, *, pergunta: str, escopo: str, modulo: str | None, tela: str | None, foco: Foco | None,
              hoje: date, nomes: list[str] | None = None) -> tuple[dict[str, Any], str | None]:
    """(resposta no formato único, erro técnico para registrar)."""
    coleta = coletar(ctx, nomes or cx.ferramentas_do_escopo(escopo, modulo, foco), foco, hoje)
    if not gateway.ligada(ctx.db):
        return _regras(coleta, ia_ligada=False, pergunta=pergunta), None
    usuario = cx.prompt_usuario(pergunta=pergunta, escopo=escopo, modulo=modulo, tela=tela, foco=foco, coleta=coleta)
    try:
        r = gerar_validado(ctx.db, cx.SISTEMA, usuario, formato.RespostaModelo)
    except core_ia.IAIndisponivel as e:
        return _regras(coleta, ia_ligada=True, motivo=f"IA indisponível agora ({e}); leitura por regras."), str(e)
    except FormatoInvalido as e:
        return _regras(coleta, ia_ligada=True,
                       motivo="A IA respondeu fora do formato duas vezes; leitura por regras."), f"formato: {e}"
    resposta = formato.sanear_resposta(r, origem="ia", ferramentas=coleta.ferramentas,
                                       limites_extra=_limites_permissao(coleta.negadas))
    resposta["ia_ligada"] = True
    return resposta, None


def perguntar(ctx, *, pergunta: str, escopo: str, modulo: str | None, tela: str | None,
              registro: tuple[str, int] | None, conversa_id: int | None, hoje: date) -> dict[str, Any]:
    foco = cx.resolver_foco(ctx, *registro) if escopo == "registro" and registro else None
    if escopo == "registro" and foco is None:
        raise HTTPException(400, "Escolha um registro para conversar sobre \"Este registro\".")
    resposta, erro = responder(ctx, pergunta=pergunta, escopo=escopo, modulo=modulo, tela=tela, foco=foco, hoje=hoje)
    conversa = ctx.db.get(IaConversa, conversa_id) if conversa_id else None
    if conversa is None or conversa.usuario_id != ctx.usuario.id:
        conversa = IaConversa(usuario_id=ctx.usuario.id, escopo=escopo, modulo=modulo, tela=(tela or "")[:60] or None,
                              registro_tipo=foco.tipo if foco else None, registro_id=foco.id if foco else None,
                              titulo=pergunta[:200])
        ctx.db.add(conversa)
        ctx.db.flush()
    provedor, modelo = gateway.descricao(ctx.db) if resposta["origem"] == "ia" else (None, None)
    msg = IaMensagem(conversa_id=conversa.id, pergunta=pergunta, resposta=resposta, ferramentas=resposta["ferramentas"],
                     origem=resposta["origem"], provedor=provedor, modelo=modelo, erro=erro)
    ctx.db.add(msg)
    ctx.db.commit()
    return {**resposta, "conversa_id": conversa.id, "mensagem_id": msg.id}


def leitura_do_momento(ctx, modulo: str, hoje: date) -> dict[str, Any]:
    pergunta = ("Qual é a leitura do momento desta área? Priorize vencidos, negociações sem próxima ação, oportunidades "
                "paradas além do limite da etapa e atividades atrasadas.")
    resposta, _ = responder(ctx, pergunta=pergunta, escopo="modulo", modulo=modulo, tela="Hoje", foco=None, hoje=hoje,
                            nomes=cx.FERRAMENTAS_DA_LEITURA[modulo])
    if resposta["origem"] == "regras":
        # a leitura de abertura de tela não é resposta a uma pergunta: tira o aviso de texto livre
        resposta["limites"] = [x for x in resposta["limites"] if "texto livre" not in x]
    return resposta


def analisar_comunicacao(ctx, comunicacao_id: int) -> dict[str, Any]:
    x = ctx.db.get(Comunicacao, comunicacao_id)
    if x is None:
        raise HTTPException(404, "Comunicação não encontrada.")
    if x.oportunidade_id:
        o = ctx.db.get(Oportunidade, x.oportunidade_id)
        if o is not None and not ctx.pode_acessar(o.responsavel_id):
            raise HTTPException(404, "Comunicação não encontrada.")
    fonte = f"Comercial › Comunicações › #{x.id} ({x.canal}{', ' + x.data.strftime('%d/%m/%Y') if x.data else ''})"
    origem, erro = "regras", None
    analise = heuristica.analisar(x.conteudo)
    if gateway.ligada(ctx.db):
        try:
            a = gerar_validado(ctx.db, cx.SISTEMA_ANALISE, cx.prompt_analise(x.conteudo, fonte), formato.AnaliseModelo)
            analise, origem = formato.sanear_analise(a, x.conteudo), "ia"
        except core_ia.IAIndisponivel as e:
            erro = str(e)
            analise["limites"].insert(0, f"IA indisponível agora ({e}); análise por regras.")
        except FormatoInvalido:
            erro = "formato"
            analise["limites"].insert(0, "A IA respondeu fora do formato duas vezes; análise por regras.")
    analise["fonte"] = fonte
    analise["origem"] = origem
    antes = audit.snapshot(x)
    x.analise = analise
    x.analisada_em = agora()
    ctx.db.flush()
    a_, d_ = audit.diff(antes, audit.snapshot(x))
    ctx.auditar("comunicacao.analisar", "comunicacao", x.id, descricao=f"Análise ({origem})", antes=a_, depois=d_)
    ctx.db.commit()
    return {"comunicacao_id": x.id, "analise": analise, "analisada_em": x.analisada_em, "origem": origem, "erro": erro}
