"""Análise de comunicação POR REGRAS (sem IA): frases com marcadores simples. Pura e determinística.

- necessidade: "precisamos", "precisa", "necessário", "queremos", "gostaríamos", "o objetivo é"
- objeção:     "antes de", "porém", "mas ", "caro", "preocupa", "dúvida", "não temos orçamento", "concorrente"
- compromisso: "até dd/mm", datas dd/mm, "vou ", "vamos ", "enviará", "enviar", "retornar" (quem = nome no início)
- citação:     a frase literal que sustentou cada item

`limites` sempre diz que é heurística — não substitui a leitura da conversa.
"""

import re

LIMITE_HEURISTICA = ("Análise heurística por palavras-chave (IA desligada): pode deixar passar nuances e não "
                     "interpreta contexto.")
LIMITE_SEM_AUDIO = "Sem transcrição de áudio nem análise de emoções."

_NECESSIDADE = re.compile(r"\b(precisamos|precisa|precisam|necess[áa]ri[oa]|queremos|gostar[íi]amos|o objetivo [ée])\b",
                          re.IGNORECASE)
_OBJECAO = re.compile(r"(\bantes de\b|\bpor[ée]m\b|\bmas\b|\bcaro\b|\bpreocupa|\bd[úu]vida|\bn[ãa]o temos or[çc]amento|"
                      r"\bconcorrente\b|\bsem verba\b)", re.IGNORECASE)
_DATA = re.compile(r"\b(?:at[ée]\s+)?(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b", re.IGNORECASE)
_COMPROMISSO = re.compile(r"(\bvou\b|\bvamos\b|\benviar[áa]?\b|\bretornar[áa]?\b|\bmandar[áa]?\b|\bficou de\b|"
                          r"\bcombinamos\b|\bagendar\b)", re.IGNORECASE)
_QUEM = re.compile(r"^\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+)\s+(?:vai|vou|enviar|enviará|ficou|retorna|retornará|"
                   r"mandará|vamos)", re.UNICODE)


def _frases(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?])\s+|\n+", texto or "")
    return [p.strip(" -•\t") for p in partes if p and p.strip(" -•\t")]


def analisar(conteudo: str) -> dict:
    necessidades, objecoes, compromissos, citacoes = [], [], [], []
    for f in _frases(conteudo):
        achou = False
        if _NECESSIDADE.search(f):
            necessidades.append(f)
            achou = True
        if _OBJECAO.search(f):
            objecoes.append(f)
            achou = True
        data = _DATA.search(f)
        if data or _COMPROMISSO.search(f):
            quem = _QUEM.match(f)
            compromissos.append({"quem": quem.group(1) if quem else "Não identificado", "o_que": f,
                                 "quando": data.group(1) if data else None})
            achou = True
        if achou:
            citacoes.append(f)
    return {"necessidades": necessidades[:10], "objecoes": objecoes[:10], "compromissos": compromissos[:10],
            "citacoes": list(dict.fromkeys(citacoes))[:10], "limites": [LIMITE_HEURISTICA, LIMITE_SEM_AUDIO]}
