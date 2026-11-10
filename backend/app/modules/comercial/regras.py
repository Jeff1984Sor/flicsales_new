"""Regras puras do Comercial que não estão em app/domain (o domínio compartilhado é da Fundação).

Funções sem banco e sem relógio: recebem tudo por parâmetro e levantam `RegraViolada` com a mensagem da tela.
"""

import re
from datetime import date
from decimal import Decimal

from app.domain import RegraViolada

# Tipos do histórico compartilhado (`oportunidade_evento.tipo`). O motor de automações (Orquestração) lê esta tabela.
TIPOS_EVENTO = ("criada", "etapa", "ganha", "perdida", "reaberta", "proxima_acao", "proposta", "reuniao", "nota")

CANAIS_COMUNICACAO = ("reuniao", "email", "whatsapp", "notas")
CANAIS_MODELO = ("email", "whatsapp", "ligacao", "reuniao")
FINALIDADES_MODELO = ("prospeccao", "follow_up", "proposta", "cobranca", "renovacao")
STATUS_MODELO = ("rascunho", "revisado")
INDICADORES_META = ("receita_unica_ganha", "mrr_novo", "vendas_ganhas", "atividades_concluidas")
METRICAS_INDICADOR = ("soma_valor_unico", "quantidade")
CONDICOES_PROPOSTA = ("À vista", "2 parcelas", "3 parcelas", "Recorrente mensal")

VARIAVEIS_MODELO = ("empresa.nome", "contato.nome", "oportunidade.titulo", "titulo.valor", "titulo.vencimento")
_VAR = re.compile(r"\{\{\s*([a-zA-Z_][\w.]*)\s*\}\}")


def probabilidades_padrao(n: int) -> list[int]:
    """Funil novo: probabilidade crescente até 80% (parâmetro editável, não previsão). Ex.: 5 etapas → 16, 32, 48, 64, 80."""
    return [round((i + 1) * 80 / n) for i in range(n)]


def validar_tipo_evento(tipo: str) -> str:
    if tipo not in TIPOS_EVENTO:
        raise ValueError(f"Tipo de evento desconhecido: {tipo}")
    return tipo


def validar_periodo(inicio: date | None, fim: date | None) -> None:
    if inicio is None or fim is None:
        raise RegraViolada("Informe o início e o fim.")
    if fim < inicio:
        raise RegraViolada("A data final deve ser igual ou posterior ao início")


def validar_meta(*, nome: str | None, responsavel_tipo: str, responsavel_id: int | None, equipe: str | None,
                 inicio: date | None, fim: date | None, indicador: str, alvo) -> None:
    if not (nome or "").strip():
        raise RegraViolada("Informe o nome da meta.")
    if responsavel_tipo not in ("pessoa", "equipe"):
        raise RegraViolada("Responsável da meta: pessoa ou equipe.")
    if responsavel_tipo == "pessoa" and not responsavel_id:
        raise RegraViolada("Escolha a pessoa responsável pela meta.")
    if responsavel_tipo == "equipe" and not (equipe or "").strip():
        raise RegraViolada("Informe o nome da equipe.")
    validar_periodo(inicio, fim)
    if indicador not in INDICADORES_META:
        raise RegraViolada("Indicador de meta desconhecido.")
    if alvo is None or Decimal(str(alvo)) <= 0:
        raise RegraViolada("A meta numérica deve ser positiva.")


def validar_modelo(*, nome: str | None, canal: str, finalidade: str, conteudo: str | None, status: str) -> None:
    if not (nome or "").strip():
        raise RegraViolada("Informe o nome do modelo.")
    if canal not in CANAIS_MODELO:
        raise RegraViolada("Canal do modelo inválido.")
    if finalidade not in FINALIDADES_MODELO:
        raise RegraViolada("Finalidade do modelo inválida.")
    if not (conteudo or "").strip():
        raise RegraViolada("Informe o conteúdo ou roteiro do modelo.")
    if status not in STATUS_MODELO:
        raise RegraViolada("Status do modelo inválido.")


def validar_playbook(*, nome: str | None, objetivo: str | None, criterios_avanco: str | None) -> None:
    if not (nome or "").strip():
        raise RegraViolada("Informe o nome do playbook.")
    if not (objetivo or "").strip():
        raise RegraViolada("Informe o objetivo do playbook.")
    if not (criterios_avanco or "").strip():
        raise RegraViolada("Informe os critérios para avançar.")


def variaveis_do_texto(texto: str | None) -> list[str]:
    return list(dict.fromkeys(m.group(1) for m in _VAR.finditer(texto or "")))


def renderizar_modelo(texto: str | None, valores: dict[str, str | None]) -> tuple[str, list[str]]:
    """Troca {{variavel}} pelos valores conhecidos. Devolve (texto, variáveis sem valor) — as sem valor ficam como estão
    para a pessoa completar (nada é enviado: é um rascunho)."""
    faltando: list[str] = []

    def troca(m: re.Match) -> str:
        chave = m.group(1)
        v = valores.get(chave)
        if v in (None, ""):
            if chave not in faltando:
                faltando.append(chave)
            return m.group(0)
        return str(v)

    return _VAR.sub(troca, texto or ""), faltando


def validar_analise(analise: dict) -> dict:
    """Formato guardado em `comunicacao.analise`: listas de textos + citações {trecho, fonte} + limites."""
    if not isinstance(analise, dict):
        raise RegraViolada("Análise em formato inválido.")
    out: dict = {}
    for chave in ("necessidades", "objecoes", "compromissos", "limites"):
        v = analise.get(chave) or []
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise RegraViolada("Análise em formato inválido.")
        out[chave] = [x.strip() for x in v if x and x.strip()]
    citacoes = analise.get("citacoes") or []
    if not isinstance(citacoes, list):
        raise RegraViolada("Análise em formato inválido.")
    out["citacoes"] = []
    for c in citacoes:
        if isinstance(c, str):
            out["citacoes"].append({"trecho": c, "fonte": None})
        elif isinstance(c, dict) and c.get("trecho"):
            out["citacoes"].append({"trecho": str(c["trecho"]), "fonte": c.get("fonte")})
    for extra in ("origem", "resumo", "tarefa_sugerida"):
        if analise.get(extra) is not None:
            out[extra] = analise[extra]
    return out


def rascunho_resposta(*, contato: str | None, analise: dict | None) -> str:
    """Resposta em RASCUNHO a partir da análise (sem IA, sem envio). A pessoa revisa e envia pelo canal autorizado."""
    saudacao = f"Olá, {contato.split()[0]}!" if contato else "Olá!"
    a = analise or {}
    partes = [saudacao]
    if a.get("compromissos"):
        partes.append(f"Conforme combinamos: {a['compromissos'][0].rstrip('.')}.")
    if a.get("objecoes"):
        partes.append(f"Sobre o ponto levantado ({a['objecoes'][0].rstrip('.').lower()}), "
                      "preparei os detalhes para validarmos juntos.")
    elif a.get("necessidades"):
        partes.append(f"Para atender à necessidade de {a['necessidades'][0].rstrip('.').lower()}, "
                      "detalho a proposta de próximos passos.")
    else:
        partes.append("Retomo nossa conversa para alinharmos os próximos passos.")
    partes.append("Podemos conversar nesta semana?")
    return " ".join(partes)


def gargalo_do_vendedor(*, sem_proxima_acao: int, atividades_atrasadas: int, alem_do_limite: int,
                        encerradas: int) -> tuple[str, str]:
    """(gargalo observado, ação sugerida) a partir de contagens verificáveis. Não é nota nem ranking."""
    if sem_proxima_acao:
        return ("Há negócios sem próxima ação: podem perder continuidade. Isso indica uma lacuna no registro; "
                "não prova ausência de contato com o cliente.",
                "Revisar semanalmente as oportunidades abertas e registrar responsável, prazo e próximo passo.")
    if atividades_atrasadas:
        return ("Há atividades com prazo vencido: o plano de contato está atrasado em relação ao combinado.",
                "Concluir ou remarcar as atividades atrasadas, registrando o resultado de cada contato.")
    if alem_do_limite:
        return ("Há oportunidades paradas além do limite da etapa.",
                "Revisar os critérios de avanço e decidir avançar, encerrar ou combinar novo prazo.")
    if encerradas == 0:
        return ("Sem oportunidades encerradas no período: a amostra não permite medir conversão.",
                "Acompanhar o período seguinte antes de tirar conclusões.")
    return ("Nenhum gargalo evidente nos registros do período.",
            "Manter a cadência de próximas ações e registrar os resultados das conversas.")
