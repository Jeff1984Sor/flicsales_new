"""Formato ÚNICO de resposta (IA e regras) e saneamento do que a IA devolve.

    {titulo, analise, proxima_acao, evidencias: [{fonte, trecho}], limites: [], acoes_sugeridas: [{tipo, rotulo, payload}],
     origem: "ia" | "regras", ferramentas: []}

A IA SUGERE; as regras decidem: só `criar_atividade` sobrevive em `acoes_sugeridas` (nunca ganhar/perder, mudar etapa,
baixar título ou enviar mensagem), e o payload passa por uma lista fechada de campos.
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

TIPOS_ACAO_PERMITIDOS = {"criar_atividade"}
CAMPOS_PAYLOAD = {"assunto", "tipo", "prazo", "oportunidade_id", "empresa_id", "objetivo", "hora_inicio", "hora_fim"}
LIMITE_SEM_EVIDENCIA = "A IA não citou evidências dos registros: trate a leitura como hipótese."
LIMITE_PADRAO_IA = "A IA interpreta só os registros consultados dentro das suas permissões; não vê canais desconectados."


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Evidencia(_Base):
    fonte: str = Field(min_length=1, max_length=300)
    trecho: str = Field(min_length=1, max_length=1000)


class AcaoSugerida(_Base):
    tipo: str = Field(min_length=1, max_length=40)
    rotulo: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


class RespostaModelo(_Base):
    titulo: str = Field(min_length=1, max_length=200)
    analise: str = Field(min_length=1, max_length=4000)
    proxima_acao: str = Field(default="", max_length=600)
    evidencias: list[Evidencia] = Field(default_factory=list, max_length=12)
    limites: list[str] = Field(default_factory=list, max_length=10)
    acoes_sugeridas: list[AcaoSugerida] = Field(default_factory=list, max_length=10)


class Compromisso(_Base):
    quem: str = Field(default="Não identificado", max_length=200)
    o_que: str = Field(min_length=1, max_length=500)
    quando: str | None = Field(default=None, max_length=60)


class AnaliseModelo(_Base):
    necessidades: list[str] = Field(default_factory=list, max_length=20)
    objecoes: list[str] = Field(default_factory=list, max_length=20)
    compromissos: list[Compromisso] = Field(default_factory=list, max_length=20)
    citacoes: list[str] = Field(default_factory=list, max_length=20)
    limites: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("necessidades", "objecoes", "citacoes", "limites")
    @classmethod
    def _sem_vazios(cls, v: list[str]) -> list[str]:
        return [x.strip() for x in v if isinstance(x, str) and x.strip()]


FORMATO_RESPOSTA = (
    '{"titulo": "frase curta", "analise": "texto", "proxima_acao": "texto", '
    '"evidencias": [{"fonte": "Módulo › Tela › registro #id", "trecho": "o dado que sustenta"}], '
    '"limites": ["o que não se sabe"], '
    '"acoes_sugeridas": [{"tipo": "criar_atividade", "rotulo": "Criar tarefa após revisão", '
    '"payload": {"assunto": "...", "tipo": "tarefa", "prazo": "AAAA-MM-DD", "oportunidade_id": 1}}]}'
)
FORMATO_ANALISE = (
    '{"necessidades": ["..."], "objecoes": ["..."], "compromissos": [{"quem": "...", "o_que": "...", '
    '"quando": "dd/mm ou null"}], "citacoes": ["trecho LITERAL do conteúdo"], "limites": ["..."]}'
)


def resumo_erro(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()[:5])


def sanear_resposta(r: RespostaModelo, *, origem: str, ferramentas: list[str], limites_extra: list[str]) -> dict:
    acoes = []
    for a in r.acoes_sugeridas:
        if a.tipo not in TIPOS_ACAO_PERMITIDOS:
            continue  # ex.: "marcar_ganha" vindo de uma injeção — descartado
        payload = {k: v for k, v in a.payload.items() if k in CAMPOS_PAYLOAD}
        if not str(payload.get("assunto") or "").strip():
            payload["assunto"] = a.rotulo
        acoes.append({"tipo": a.tipo, "rotulo": a.rotulo, "payload": payload})
    limites = list(dict.fromkeys([*r.limites, *limites_extra]))
    if not r.evidencias:
        limites.append(LIMITE_SEM_EVIDENCIA)
    if not limites:
        limites.append(LIMITE_PADRAO_IA)
    return {"titulo": r.titulo, "analise": r.analise, "proxima_acao": r.proxima_acao,
            "evidencias": [e.model_dump() for e in r.evidencias], "limites": limites, "acoes_sugeridas": acoes[:3],
            "origem": origem, "ferramentas": ferramentas}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().strip("\"“”'").strip().lower()


def sanear_analise(a: AnaliseModelo, conteudo: str) -> dict:
    """Citação só vale se for LITERAL do conteúdo (a IA não inventa fala do cliente)."""
    base = _norm(conteudo)
    citacoes = [c for c in a.citacoes if _norm(c) and _norm(c) in base]
    limites = list(a.limites)
    if len(citacoes) < len(a.citacoes):
        limites.append("Citações que não aparecem literalmente no conteúdo foram descartadas.")
    limites.append("Sem transcrição de áudio nem análise de emoções.")
    return {"necessidades": a.necessidades, "objecoes": a.objecoes,
            "compromissos": [c.model_dump() for c in a.compromissos], "citacoes": citacoes,
            "limites": list(dict.fromkeys(limites))}
