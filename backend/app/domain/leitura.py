"""Leitura do momento DETERMINÍSTICA (funciona sem IA configurada).

Prioridades, nesta ordem (desempate estável: maior valor/atraso primeiro, depois id):
  1. recebíveis vencidos (a receber, aberto/parcial, vencimento < hoje)
  2. oportunidades abertas sem próxima ação
  3. oportunidades abertas além do limite de dias da etapa
  4. atividades pendentes com prazo vencido

Resposta no FORMATO ÚNICO da IA unificada (o mesmo de POST /api/orquestracao/ia/perguntar):
    {titulo, analise, proxima_acao, evidencias: [{fonte, trecho, registro}], limites: [],
     acoes_sugeridas: [{tipo, rotulo, payload}], origem: "regras", ferramentas: []}
`evidencias[].texto` (= trecho) e `acoes_sugeridas[].registro` continuam presentes por compatibilidade.
Ações sugeridas nascem PROPOSTAS: só viram registro após o clique do usuário (POST /api/orquestracao/acoes/executar
aceita só `criar_atividade`; as demais são atalhos de navegação para o registro).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.domain.dinheiro import ZERO, dinheiro, formatar_brl
from app.domain.funil import alem_do_limite, dias_na_etapa
from app.domain.titulos import EM_ABERTO

LIMITE_IA_DESLIGADA = "Leitura calculada por regras (IA desligada): prioriza prazos e valores, sem interpretar conversas."
LIMITE_SEM_CONCILIACAO = "Baseada nos registros do FlicSales; não há conciliação bancária nem captura automática de canais."


@dataclass(frozen=True)
class TituloResumo:
    id: int
    empresa: str
    descricao: str
    direcao: str
    status: str
    vencimento: date
    saldo: Decimal


@dataclass(frozen=True)
class OportunidadeResumo:
    id: int
    titulo: str
    empresa: str | None
    etapa: str | None
    valor: Decimal
    proxima_acao: str | None = None
    entrou_etapa_em: date | None = None
    limite_dias: int | None = None
    resultado: str = "aberta"


@dataclass(frozen=True)
class AtividadeResumo:
    id: int
    assunto: str
    prazo: date
    status: str = "pendente"
    empresa: str | None = None


@dataclass
class Achado:
    prioridade: int
    peso: Decimal
    registro_id: int
    tipo: str  # titulo | oportunidade | atividade
    texto: str
    fonte: str
    acao: dict[str, Any] = field(default_factory=dict)


def _acao(acao_tipo: str, rotulo: str, registro_tipo: str, registro_id: int, **payload: Any) -> dict[str, Any]:
    registro = {"tipo": registro_tipo, "id": registro_id}
    return {"tipo": acao_tipo, "rotulo": rotulo, "payload": {"registro": registro, **payload}, "registro": registro}


def _achados(hoje: date, titulos: list[TituloResumo], oportunidades: list[OportunidadeResumo],
             atividades: list[AtividadeResumo]) -> list[Achado]:
    out: list[Achado] = []
    for t in titulos:
        if t.direcao == "receber" and t.status in EM_ABERTO and t.vencimento < hoje and dinheiro(t.saldo) > 0:
            dias = (hoje - t.vencimento).days
            out.append(Achado(1, dinheiro(t.saldo), t.id, "titulo",
                              f"{t.empresa} · {t.descricao}: {formatar_brl(t.saldo)} vencido há {dias} dia(s)",
                              f"Financeiro › A receber › título #{t.id}",
                              _acao("abrir_registro", f"Abrir cobrança de {t.empresa}", "titulo", t.id)))
    abertas = [o for o in oportunidades if o.resultado == "aberta"]
    for o in abertas:
        if not (o.proxima_acao or "").strip():
            out.append(Achado(2, dinheiro(o.valor), o.id, "oportunidade",
                              f"{o.titulo}{f' ({o.empresa})' if o.empresa else ''} em {o.etapa or 'aberto'}: "
                              f"{formatar_brl(o.valor)} sem próxima ação",
                              f"Comercial › Oportunidades › #{o.id}",
                              _acao("criar_atividade", f"Definir próxima ação para {o.titulo}", "oportunidade", o.id,
                                    assunto=f"Definir próxima ação: {o.titulo}", tipo="tarefa", prazo=hoje.isoformat(),
                                    oportunidade_id=o.id)))
    for o in abertas:
        if alem_do_limite(o.entrou_etapa_em, o.limite_dias, hoje):
            dias = dias_na_etapa(o.entrou_etapa_em, hoje)
            out.append(Achado(3, Decimal(dias), o.id, "oportunidade",
                              f"{o.titulo} está há {dias} dias em {o.etapa} (limite de {o.limite_dias} dias)",
                              f"Comercial › Oportunidades › #{o.id}",
                              _acao("abrir_registro", f"Revisar etapa de {o.titulo}", "oportunidade", o.id)))
    for a in atividades:
        if a.status == "pendente" and a.prazo < hoje:
            dias = (hoje - a.prazo).days
            out.append(Achado(4, Decimal(dias), a.id, "atividade",
                              f"Atividade atrasada há {dias} dia(s): {a.assunto}"
                              + (f" ({a.empresa})" if a.empresa else ""),
                              f"Comercial › Atividades › #{a.id}",
                              _acao("abrir_registro", f"Concluir ou remarcar: {a.assunto}", "atividade", a.id)))
    out.sort(key=lambda x: (x.prioridade, -x.peso, x.registro_id))
    return out


def ler_momento(*, hoje: date, titulos: list[TituloResumo] = (), oportunidades: list[OportunidadeResumo] = (),
                atividades: list[AtividadeResumo] = (), ia_ligada: bool = False, max_evidencias: int = 5) -> dict[str, Any]:
    achados = _achados(hoje, list(titulos), list(oportunidades), list(atividades))
    limites = [LIMITE_SEM_CONCILIACAO] + ([] if ia_ligada else [LIMITE_IA_DESLIGADA])
    if not achados:
        return {"titulo": "Tudo em dia", "analise": "Nenhum vencido, nenhuma oportunidade sem próxima ação e nenhuma "
                "atividade atrasada.", "proxima_acao": "Revise o funil e planeje as próximas conversas.",
                "evidencias": [], "limites": limites, "acoes_sugeridas": [], "origem": "regras",
                "ferramentas": []}
    principal = achados[0]
    contagem = {p: sum(1 for a in achados if a.prioridade == p) for p in (1, 2, 3, 4)}
    vencido_total = sum((a.peso for a in achados if a.prioridade == 1), ZERO)
    partes = []
    if contagem[1]:
        partes.append(f"{contagem[1]} recebível(is) vencido(s) somando {formatar_brl(vencido_total)}")
    if contagem[2]:
        partes.append(f"{contagem[2]} oportunidade(s) sem próxima ação")
    if contagem[3]:
        partes.append(f"{contagem[3]} oportunidade(s) além do limite da etapa")
    if contagem[4]:
        partes.append(f"{contagem[4]} atividade(s) atrasada(s)")
    titulos_por_prioridade = {1: "Recebível vencido pede ação", 2: "Negociação sem próxima ação",
                              3: "Oportunidade parada na etapa", 4: "Atividades atrasadas"}
    return {
        "titulo": titulos_por_prioridade[principal.prioridade],
        "analise": "Pontos de atenção agora: " + "; ".join(partes) + ".",
        "proxima_acao": principal.acao["rotulo"],
        "evidencias": [{"fonte": a.fonte, "trecho": a.texto, "texto": a.texto,
                        "registro": {"tipo": a.tipo, "id": a.registro_id}} for a in achados[:max_evidencias]],
        "limites": limites,
        "acoes_sugeridas": [a.acao for a in achados[:3]],
        "origem": "regras",
        "ferramentas": [],
    }
