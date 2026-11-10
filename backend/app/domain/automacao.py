"""Automações: catálogo (gatilhos, ações, modelos prontos), validação e AVALIAÇÃO pura dos gatilhos.

O motor (app/modules/orquestracao/motor.py) fotografa o estado do banco em dataclasses (`Estado`) e chama
`ocorrencias(regra, estado, hoje)`. Esta função NÃO lê relógio nem banco: devolve a lista de ocorrências elegíveis, cada
uma com uma `ocorrencia` estável — a chave de idempotência é `automacao:registro:ocorrencia` (rodar duas vezes não
duplica). Varre o ESTADO (não depende de chamadas dos outros módulos).

Regras que não se negociam aqui:
- Criar atividade ≠ enviar mensagem: ações "enviar_*" só ativam com o canal conectado; ao rodar, ficam "pendente de
  conector" (nenhum envio real nesta fase).
- Cobrança respeita "em contestação" e título recebido/cancelado (só aberto/parcial com saldo > 0 dispara).
- Prevenção de ciclo: atividade criada por uma automação não dispara a MESMA automação; "atualizar campo" não pode
  alterar o campo que dispara a própria automação.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain import RegraViolada
from app.domain.atividade import TIPOS as TIPOS_ATIVIDADE
from app.domain.dinheiro import dinheiro, formatar_brl
from app.domain.recorrencia import competencias_a_gerar
from app.domain.titulos import EM_ABERTO

AREAS = ("comercial", "financeiro")
ESTADOS = ("rascunho", "ativa", "pausada")
MAX_TENTATIVAS = 3

GATILHOS: dict[str, dict[str, str]] = {
    "comercial": {
        "oportunidade_criada": "Oportunidade criada",
        "oportunidade_etapa": "Oportunidade movida de etapa",
        "oportunidade_ganha": "Oportunidade ganha",
        "oportunidade_perdida": "Oportunidade perdida",
        "campo_alterado": "Campo personalizado alterado",
        "sem_interacao": "Sem interação por período",
        "atividade_atrasada": "Atividade atrasada",
        "fechamento_proximo": "Data de fechamento próxima",
        "reuniao_encerrada": "Reunião encerrada",
    },
    "financeiro": {
        "recebivel_confirmado": "Recebível confirmado",
        "vencimento_proximo": "Vencimento próximo",
        "titulo_vencido": "Título vencido",
        "recebimento_parcial": "Recebimento parcial registrado",
        "recebimento_total": "Recebimento total registrado",
        "pagamento_proximo": "Pagamento próximo",
        "recorrencia_a_gerar": "Recorrência a gerar",
        "recorrencia_a_renovar": "Recorrência a renovar",
        "campo_alterado": "Campo personalizado alterado",
        "saldo_abaixo_limite": "Saldo projetado abaixo do limite",
    },
}

# eventos da oportunidade (tabela oportunidade_evento, gravada pelo Comercial) → gatilho
EVENTO_DO_GATILHO = {"oportunidade_criada": "criada", "oportunidade_etapa": "etapa", "oportunidade_ganha": "ganha",
                     "oportunidade_perdida": "perdida"}
# gatilhos por evento: o prazo (dias) é o prazo da atividade criada; nos temporais, é a janela/limite do gatilho
GATILHOS_DE_EVENTO = {*EVENTO_DO_GATILHO, "reuniao_encerrada", "recebivel_confirmado", "recebimento_parcial",
                      "recebimento_total", "campo_alterado"}

ACOES = {
    "criar_atividade": "Criar atividade",
    "enviar_email": "Enviar e-mail",
    "enviar_whatsapp": "Enviar mensagem de WhatsApp",
    "atualizar_campo": "Atualizar campo",
    "notificar": "Notificar responsável",
}
CANAL_DA_ACAO = {"enviar_email": "email", "enviar_whatsapp": "whatsapp"}
MSG_CANAL = "Conecte o canal autorizado antes de ativar envios"

OPERADORES = {"igual": "Igual a", "diferente": "Diferente de", "maior": "Maior que", "menor": "Menor que",
              "preenchido": "Preenchido"}
TIPOS_ATIVIDADE_ROTULO = {"tarefa": "Tarefa", "email": "E-mail", "ligacao": "Ligação", "whatsapp": "WhatsApp",
                          "reuniao": "Reunião"}
RESPONSAVEL_DO_REGISTRO = "responsavel_do_registro"
VARIAVEIS = ["{{empresa.nome}}", "{{contato.nome}}", "{{oportunidade.titulo}}", "{{titulo.valor}}",
             "{{titulo.vencimento}}"]
# campos que "atualizar campo" pode alterar (além dos campos personalizados da oportunidade)
CAMPOS_ATUALIZAVEIS = {"oportunidade": {"proxima_acao"}, "titulo": {"observacoes"}}


# ---------------------------------------------------------------------------------------------- modelos prontos
def _m(chave, area, nome, gatilho, acao, tipo, descricao, prazo=None, campo=None, operador=None, valor=None,
       etapa=None, conteudo=None, destinatario=None) -> dict[str, Any]:
    return {"chave": chave, "area": area, "nome": nome, "gatilho": gatilho, "acao": acao, "tipo_atividade": tipo,
            "descricao": descricao, "prazo_dias": prazo, "campo": campo, "operador": operador, "valor_esperado": valor,
            "etapa_destino_nome": etapa, "conteudo": conteudo or descricao, "destinatario": destinatario,
            "responsavel_regra": RESPONSAVEL_DO_REGISTRO}


MODELOS: list[dict[str, Any]] = [
    # Comercial (8)
    _m("boas_vindas", "comercial", "Boas-vindas e primeiro contato", "oportunidade_criada", "criar_atividade", "ligacao",
       "Atribuir responsável e agendar primeiro contato.", prazo=1,
       conteudo="Primeiro contato com {{empresa.nome}} sobre {{oportunidade.titulo}}"),
    _m("follow_up_proposta", "comercial", "Follow-up de proposta", "oportunidade_etapa", "criar_atividade", "email",
       "Ao entrar em Proposta, retornar em 2 dias úteis.", prazo=2, etapa="Proposta",
       conteudo="Retornar sobre a proposta de {{oportunidade.titulo}} ({{empresa.nome}})"),
    _m("retomar_sem_interacao", "comercial", "Retomar negociação sem interação", "sem_interacao", "criar_atividade",
       "whatsapp", "Após 5 dias sem interação válida, criar retorno.", prazo=5,
       conteudo="Retomar conversa com {{contato.nome}} · {{oportunidade.titulo}}"),
    _m("reuniao_diagnostico", "comercial", "Reunião de diagnóstico", "oportunidade_etapa", "criar_atividade", "reuniao",
       "Ao entrar em Discovery, preparar diagnóstico.", prazo=2, etapa="Discovery",
       conteudo="Diagnóstico com {{empresa.nome}} · {{oportunidade.titulo}}"),
    _m("nutricao_email", "comercial", "Nutrição por e-mail", "campo_alterado", "enviar_email", "email",
       "Interesse = Alto; usar modelo e destinatário revisados.", campo="interesse", operador="igual", valor="Alto",
       destinatario="contato_principal", conteudo="Olá {{contato.nome}}, seguem materiais sobre {{oportunidade.titulo}}."),
    _m("acompanhamento_whatsapp", "comercial", "Mensagem de acompanhamento", "oportunidade_etapa", "enviar_whatsapp",
       "whatsapp", "Mensagem com modelo aprovado e conexão autorizada.", destinatario="contato_principal",
       conteudo="Olá {{contato.nome}}, passando para acompanhar {{oportunidade.titulo}}."),
    _m("handoff_ganha", "comercial", "Handoff de venda ganha", "oportunidade_ganha", "criar_atividade", "tarefa",
       "Revisar condição comercial e recebíveis em rascunho.", prazo=1,
       conteudo="Handoff: revisar condição e recebíveis em rascunho de {{oportunidade.titulo}}"),
    _m("revisao_perda", "comercial", "Revisão de perda", "oportunidade_perdida", "criar_atividade", "tarefa",
       "Revisar motivo, concorrente e possibilidade de retomada.", prazo=2,
       conteudo="Revisar perda de {{oportunidade.titulo}} ({{empresa.nome}})"),
    # Financeiro (7)
    _m("lembrete_vencimento", "financeiro", "Lembrete antes do vencimento", "vencimento_proximo", "enviar_email", "email",
       "3 dias antes; somente saldo aberto.", prazo=3, destinatario="contato_principal",
       conteudo="Lembrete: {{titulo.valor}} vence em {{titulo.vencimento}} ({{empresa.nome}})."),
    _m("cobranca_vencido", "financeiro", "Cobrança após vencimento", "titulo_vencido", "enviar_whatsapp", "whatsapp",
       "2 dias após; suspender ao receber, cancelar ou contestar.", prazo=2, destinatario="contato_principal",
       conteudo="Olá, identificamos {{titulo.valor}} vencido em {{titulo.vencimento}}. Podemos ajudar?"),
    _m("recebimento_parcial", "financeiro", "Tratar recebimento parcial", "recebimento_parcial", "criar_atividade",
       "ligacao", "Confirmar saldo e acordo com o cliente.", prazo=1,
       conteudo="Confirmar saldo e acordo com {{empresa.nome}} ({{titulo.valor}})"),
    _m("preparar_pagamento", "financeiro", "Preparar pagamento", "pagamento_proximo", "criar_atividade", "tarefa",
       "Conferir documento, conta e aprovação. Sem execução bancária.", prazo=2,
       conteudo="Preparar pagamento a {{empresa.nome}}: {{titulo.valor}} em {{titulo.vencimento}}"),
    _m("revisar_renovacao", "financeiro", "Revisar renovação", "recorrencia_a_renovar", "criar_atividade", "reuniao",
       "30 dias antes do fim; revisar continuidade.", prazo=30,
       conteudo="Revisar renovação com {{empresa.nome}}"),
    _m("alerta_caixa", "financeiro", "Alerta de caixa", "saldo_abaixo_limite", "notificar", "tarefa",
       "Avisar gestor com composição do saldo.", valor="0",
       conteudo="Saldo projetado abaixo do limite: {{caixa.saldo_projetado}} ({{caixa.formula}})"),
    _m("conferir_recorrencia", "financeiro", "Conferir recorrência", "recorrencia_a_gerar", "criar_atividade", "tarefa",
       "Conferir competência antes de gerar título.", prazo=5,
       conteudo="Conferir competência {{recorrencia.competencia}} de {{empresa.nome}} antes de gerar o título"),
]


def modelos_da_area(area: str) -> list[dict[str, Any]]:
    return [m for m in MODELOS if m["area"] == area]


# ---------------------------------------------------------------------------------------------- validação
@dataclass
class Configuracao:
    area: str
    nome: str
    gatilho: str
    acao: str
    conteudo: str
    funil_id: int | None = None
    etapa_destino_id: int | None = None
    campo: str | None = None
    operador: str | None = None
    valor_esperado: str | None = None
    prazo_dias: int | None = None
    tipo_atividade: str | None = None
    responsavel_regra: str | None = None
    destinatario: str | None = None


def _limpo(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def chave_campo(nome: str) -> str:
    """"Interesse" → "interesse"; "Data de retomada" → "data_de_retomada" (slug de campo personalizado)."""
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def parse_atualizacao(conteudo: str) -> tuple[str, str]:
    """"interesse = Alto" → ("interesse", "Alto"). Para a ação Atualizar campo."""
    if "=" not in (conteudo or ""):
        raise RegraViolada("Para atualizar campo, escreva no modelo: campo = valor (ex.: interesse = Alto).")
    campo, valor = conteudo.split("=", 1)
    campo, valor = chave_campo(campo), valor.strip()
    if not campo or not valor:
        raise RegraViolada("Para atualizar campo, escreva no modelo: campo = valor (ex.: interesse = Alto).")
    return campo, valor


def validar_configuracao(c: Configuracao) -> Configuracao:
    if c.area not in AREAS:
        raise RegraViolada("Escolha a área: Comercial ou Financeiro.")
    c.nome = (c.nome or "").strip()
    if not c.nome:
        raise RegraViolada("Informe o nome da automação.")
    if c.gatilho not in GATILHOS[c.area]:
        raise RegraViolada("Gatilho não disponível nesta área.")
    if c.acao not in ACOES:
        raise RegraViolada("Ação inválida.")
    c.conteudo = (c.conteudo or "").strip()
    if not c.conteudo:
        raise RegraViolada("Informe o modelo ou a instrução da automação.")
    c.campo, c.valor_esperado = _limpo(c.campo), _limpo(c.valor_esperado)
    c.operador = _limpo(c.operador)
    if c.campo:
        c.campo = chave_campo(c.campo)
        if c.operador not in OPERADORES:
            raise RegraViolada("Escolha o operador da condição.")
        if c.operador != "preenchido" and c.valor_esperado is None:
            raise RegraViolada("Informe o valor esperado da condição.")
    else:
        c.operador = None
    if c.gatilho == "campo_alterado" and not c.campo:
        raise RegraViolada("Escolha o campo monitorado para o gatilho \"Campo personalizado alterado\".")
    if c.gatilho == "saldo_abaixo_limite":
        limite = _num(c.valor_esperado or "")
        if limite is None:
            raise RegraViolada("Informe o limite de saldo (R$) no valor esperado.")
        c.valor_esperado = str(limite)
    if c.prazo_dias is not None and not 0 <= c.prazo_dias <= 365:
        raise RegraViolada("Prazo deve ficar entre 0 e 365 dias.")
    if c.acao == "criar_atividade":
        c.tipo_atividade = c.tipo_atividade or "tarefa"
        if c.tipo_atividade not in TIPOS_ATIVIDADE:
            raise RegraViolada("Tipo de atividade inválido.")
    if c.acao in CANAL_DA_ACAO and not _limpo(c.destinatario):
        raise RegraViolada("Escolha o destinatário do envio.")
    if c.acao == "atualizar_campo":
        alvo, _ = parse_atualizacao(c.conteudo)
        if c.gatilho == "campo_alterado" and alvo == c.campo:
            raise RegraViolada("A ação não pode alterar o campo que dispara a própria automação (evita ciclo).")
    c.responsavel_regra = _limpo(c.responsavel_regra) or RESPONSAVEL_DO_REGISTRO
    if c.responsavel_regra != RESPONSAVEL_DO_REGISTRO and not re.fullmatch(r"usuario:\d+", c.responsavel_regra):
        raise RegraViolada("Responsável inválido.")
    if c.area != "comercial":
        c.funil_id = c.etapa_destino_id = None
    return c


def validar_ativacao(acao: str, canais_conectados: set[str]) -> None:
    """Envio só ativa com o canal autorizado conectado (Integrações)."""
    canal = CANAL_DA_ACAO.get(acao)
    if canal and canal not in canais_conectados:
        raise RegraViolada(MSG_CANAL)


# ---------------------------------------------------------------------------------------------- estado (fotos)
@dataclass(frozen=True)
class Regra:
    id: int
    area: str
    gatilho: str
    funil_id: int | None = None
    etapa_destino_id: int | None = None
    campo: str | None = None
    operador: str | None = None
    valor_esperado: str | None = None
    prazo_dias: int | None = None
    ativada_em: datetime | None = None  # eventos anteriores à ativação não disparam


@dataclass(frozen=True)
class OportunidadeFoto:
    id: int
    titulo: str
    funil_id: int
    etapa_id: int | None
    etapa: str | None
    resultado: str
    responsavel_id: int
    valor: Decimal
    empresa_id: int | None = None
    empresa: str | None = None
    contato: str | None = None
    previsao_fechamento: date | None = None
    proxima_acao: str | None = None
    campos_custom: dict[str, Any] = field(default_factory=dict)
    ultima_interacao: date | None = None  # max(criação, eventos, atividades concluídas, comunicações)


@dataclass(frozen=True)
class EventoFoto:
    id: int
    oportunidade_id: int
    tipo: str
    quando: datetime


@dataclass(frozen=True)
class AtividadeFoto:
    id: int
    assunto: str
    tipo: str
    status: str
    prazo: date
    responsavel_id: int
    oportunidade_id: int | None = None
    empresa_id: int | None = None
    empresa: str | None = None
    concluida_em: datetime | None = None
    criada_por_automacoes: frozenset[int] = frozenset()  # automações que criaram esta atividade (ciclo)


@dataclass(frozen=True)
class TituloFoto:
    id: int
    direcao: str
    status: str
    vencimento: date
    valor_original: Decimal
    saldo: Decimal
    responsavel_id: int
    descricao: str = ""
    empresa_id: int | None = None
    empresa: str | None = None
    em_contestacao: bool = False
    confirmado_em: datetime | None = None
    ultima_baixa_em: datetime | None = None  # criação da baixa ativa mais recente
    observacoes: str | None = None


@dataclass(frozen=True)
class RecorrenciaFoto:
    id: int
    descricao: str
    situacao: str
    inicio: date
    fim: date
    frequencia: str
    responsavel_id: int | None = None
    empresa_id: int | None = None
    empresa: str | None = None
    competencias_existentes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CaixaFoto:
    saldo_projetado: Decimal
    formula: str = "saldo gerencial + entradas abertas − saídas abertas"


@dataclass
class Estado:
    oportunidades: list[OportunidadeFoto] = field(default_factory=list)
    eventos: list[EventoFoto] = field(default_factory=list)
    atividades: list[AtividadeFoto] = field(default_factory=list)
    titulos: list[TituloFoto] = field(default_factory=list)
    recorrencias: list[RecorrenciaFoto] = field(default_factory=list)
    caixa: CaixaFoto | None = None


@dataclass(frozen=True)
class Ocorrencia:
    registro_tipo: str  # oportunidade | atividade | titulo | recorrencia | caixa
    registro_id: int
    ocorrencia: str  # parte estável da chave de idempotência
    rotulo: str
    responsavel_id: int | None = None
    oportunidade_id: int | None = None
    empresa_id: int | None = None
    variaveis: dict[str, str] = field(default_factory=dict)

    @property
    def registro(self) -> str:
        return f"{self.registro_tipo}:{self.registro_id}"


def chave_idempotencia(automacao_id: int, oc: Ocorrencia) -> str:
    return f"{automacao_id}:{oc.registro}:{oc.ocorrencia}"[:200]


# ---------------------------------------------------------------------------------------------- condição
def _num(v: Any) -> Decimal | None:
    """Número de um valor de campo/condição: aceita 1500, "1500.50", "R$ 1.500,50"."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int | Decimal):
        return Decimal(v)
    s = str(v).replace("R$", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _norm(v: Any) -> str:
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def condicao_ok(dados: dict[str, Any], campo: str | None, operador: str | None, valor: str | None) -> bool:
    """Campo/operador/valor. Sem campo = sem condição adicional. Números comparam como números; texto sem
    diferenciar maiúsculas/acentos."""
    if not campo:
        return True
    atual = dados.get(campo)
    if operador == "preenchido":
        return atual not in (None, "", [], {})
    if atual in (None, ""):
        return operador == "diferente" and valor not in (None, "")
    if operador in ("maior", "menor"):
        a, b = _num(atual), _num(valor)
        if a is None or b is None:
            return False
        return a > b if operador == "maior" else a < b
    a, b = _num(atual), _num(valor)
    igual = (a == b) if (a is not None and b is not None) else _norm(atual) == _norm(valor)
    return igual if operador == "igual" else (not igual if operador == "diferente" else False)


def _dados_oportunidade(o: OportunidadeFoto) -> dict[str, Any]:
    d: dict[str, Any] = {chave_campo(k): v for k, v in (o.campos_custom or {}).items()}
    d.update({"valor": o.valor, "valor_unico": o.valor, "etapa": o.etapa, "resultado": o.resultado,
              "proxima_acao": o.proxima_acao, "empresa": o.empresa})
    return d


def _dados_titulo(t: TituloFoto) -> dict[str, Any]:
    return {"saldo": t.saldo, "saldo_em_aberto": t.saldo, "valor": t.valor_original, "valor_original": t.valor_original,
            "status": t.status, "empresa": t.empresa, "descricao": t.descricao, "direcao": t.direcao}


# ---------------------------------------------------------------------------------------------- variáveis
def _br(d: date | None) -> str:
    return f"{d:%d/%m/%Y}" if d else "—"


def variaveis_oportunidade(o: OportunidadeFoto) -> dict[str, str]:
    v = {"empresa.nome": o.empresa or "—", "contato.nome": o.contato or "—", "oportunidade.titulo": o.titulo,
         "oportunidade.valor": formatar_brl(o.valor), "oportunidade.etapa": o.etapa or "—"}
    for k, val in (o.campos_custom or {}).items():
        v[f"oportunidade.{chave_campo(k)}"] = str(val)
    return v


def variaveis_titulo(t: TituloFoto) -> dict[str, str]:
    return {"empresa.nome": t.empresa or "—", "titulo.valor": formatar_brl(t.saldo), "titulo.vencimento": _br(t.vencimento),
            "titulo.descricao": t.descricao}


def renderizar(texto: str, variaveis: dict[str, str]) -> str:
    """Troca {{variavel}}; variável desconhecida vira "—" (nunca deixa chaves cruas numa tarefa)."""
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", lambda m: variaveis.get(m.group(1), "—"), texto or "")


# ---------------------------------------------------------------------------------------------- avaliação
def _depois_da_ativacao(quando: datetime | None, regra: Regra) -> bool:
    if quando is None:
        return False
    if regra.ativada_em is None:
        return True
    return quando >= regra.ativada_em


def _janela(regra: Regra, padrao: int) -> int:
    return regra.prazo_dias if regra.prazo_dias is not None else padrao


def _oc_oportunidade(o: OportunidadeFoto, ocorrencia: str, rotulo: str) -> Ocorrencia:
    return Ocorrencia("oportunidade", o.id, ocorrencia, rotulo, o.responsavel_id, o.id, o.empresa_id,
                      variaveis_oportunidade(o))


def _oc_titulo(t: TituloFoto, ocorrencia: str, rotulo: str) -> Ocorrencia:
    return Ocorrencia("titulo", t.id, ocorrencia, rotulo, t.responsavel_id, None, t.empresa_id, variaveis_titulo(t))


def _cobravel(t: TituloFoto) -> bool:
    """Recebível que ainda pode ser cobrado: aberto/parcial, saldo > 0 e SEM contestação."""
    return t.direcao == "receber" and t.status in EM_ABERTO and dinheiro(t.saldo) > 0 and not t.em_contestacao


def _comercial(regra: Regra, e: Estado, hoje: date) -> list[Ocorrencia]:
    opps = {o.id: o for o in e.oportunidades if regra.funil_id is None or o.funil_id == regra.funil_id}
    g, out = regra.gatilho, []
    if g in EVENTO_DO_GATILHO:
        tipo = EVENTO_DO_GATILHO[g]
        for ev in e.eventos:
            o = opps.get(ev.oportunidade_id)
            if o is None or ev.tipo != tipo or not _depois_da_ativacao(ev.quando, regra):
                continue
            if g == "oportunidade_etapa" and regra.etapa_destino_id and o.etapa_id != regra.etapa_destino_id:
                continue
            if condicao_ok(_dados_oportunidade(o), regra.campo, regra.operador, regra.valor_esperado):
                out.append(_oc_oportunidade(o, f"evento:{ev.id}", f"{o.titulo} · {tipo}"))
    elif g == "campo_alterado":
        for o in opps.values():
            if o.resultado != "aberta" or not regra.campo:
                continue
            dados = _dados_oportunidade(o)
            if condicao_ok(dados, regra.campo, regra.operador, regra.valor_esperado):
                out.append(_oc_oportunidade(o, f"campo:{regra.campo}={_norm(dados.get(regra.campo))}",
                                            f"{o.titulo} · {regra.campo} = {dados.get(regra.campo)}"))
    elif g == "sem_interacao":
        n = _janela(regra, 5)
        for o in opps.values():
            if o.resultado != "aberta" or o.ultima_interacao is None:
                continue
            if (hoje - o.ultima_interacao).days >= n and condicao_ok(_dados_oportunidade(o), regra.campo,
                                                                     regra.operador, regra.valor_esperado):
                out.append(_oc_oportunidade(o, f"sem_interacao:{o.ultima_interacao.isoformat()}",
                                            f"{o.titulo} · sem interação há {(hoje - o.ultima_interacao).days} dia(s)"))
    elif g == "fechamento_proximo":
        n = _janela(regra, 7)
        for o in opps.values():
            if o.resultado != "aberta" or o.previsao_fechamento is None:
                continue
            if 0 <= (o.previsao_fechamento - hoje).days <= n and condicao_ok(
                    _dados_oportunidade(o), regra.campo, regra.operador, regra.valor_esperado):
                out.append(_oc_oportunidade(o, f"fechamento:{o.previsao_fechamento.isoformat()}",
                                            f"{o.titulo} · fechamento previsto {_br(o.previsao_fechamento)}"))
    elif g in ("atividade_atrasada", "reuniao_encerrada"):
        n = _janela(regra, 1)
        todas = {o.id: o for o in e.oportunidades}
        for a in e.atividades:
            if regra.id in a.criada_por_automacoes:  # prevenção de ciclo
                continue
            if regra.funil_id is not None and (a.oportunidade_id is None or a.oportunidade_id not in opps):
                continue
            o = todas.get(a.oportunidade_id) if a.oportunidade_id else None
            if g == "atividade_atrasada":
                if not (a.status == "pendente" and (hoje - a.prazo).days >= max(n, 1)):
                    continue
                ocorrencia, rotulo = f"atraso:{a.prazo.isoformat()}", f"{a.assunto} · atrasada desde {_br(a.prazo)}"
            else:
                if not (a.tipo == "reuniao" and a.status == "concluida" and _depois_da_ativacao(a.concluida_em, regra)):
                    continue
                ocorrencia, rotulo = "encerrada", f"{a.assunto} · reunião encerrada"
            if o is not None and not condicao_ok(_dados_oportunidade(o), regra.campo, regra.operador,
                                                 regra.valor_esperado):
                continue
            variaveis = variaveis_oportunidade(o) if o else {"empresa.nome": a.empresa or "—"}
            variaveis["atividade.assunto"] = a.assunto
            out.append(Ocorrencia("atividade", a.id, ocorrencia, rotulo, a.responsavel_id, a.oportunidade_id,
                                  a.empresa_id, variaveis))
    return out


def _financeiro(regra: Regra, e: Estado, hoje: date) -> list[Ocorrencia]:
    g, out = regra.gatilho, []

    def cond(t: TituloFoto) -> bool:
        return condicao_ok(_dados_titulo(t), regra.campo, regra.operador, regra.valor_esperado)

    for t in e.titulos:
        if g == "recebivel_confirmado":
            if t.direcao == "receber" and t.status != "rascunho" and t.status != "cancelado" \
                    and _depois_da_ativacao(t.confirmado_em, regra) and cond(t):
                out.append(_oc_titulo(t, "confirmado", f"{t.empresa or ''} · {t.descricao} confirmado"))
        elif g == "vencimento_proximo":
            dias = (t.vencimento - hoje).days
            if _cobravel(t) and 0 <= dias <= _janela(regra, 3) and cond(t):
                out.append(_oc_titulo(t, f"vence:{t.vencimento.isoformat()}",
                                      f"{t.empresa or ''} · {t.descricao} vence em {dias} dia(s)"))
        elif g == "titulo_vencido":
            atraso = (hoje - t.vencimento).days
            if _cobravel(t) and atraso >= max(_janela(regra, 1), 1) and cond(t):
                out.append(_oc_titulo(t, f"vencido:{t.vencimento.isoformat()}",
                                      f"{t.empresa or ''} · {t.descricao} vencido há {atraso} dia(s)"))
        elif g == "recebimento_parcial":
            if t.direcao == "receber" and t.status == "parcial" and _depois_da_ativacao(t.ultima_baixa_em, regra) \
                    and cond(t):
                out.append(_oc_titulo(t, f"parcial:{dinheiro(t.saldo)}",
                                      f"{t.empresa or ''} · {t.descricao}: saldo {formatar_brl(t.saldo)}"))
        elif g == "recebimento_total":
            if t.direcao == "receber" and t.status == "liquidado" and _depois_da_ativacao(t.ultima_baixa_em, regra) \
                    and cond(t):
                out.append(_oc_titulo(t, "liquidado", f"{t.empresa or ''} · {t.descricao} recebido"))
        elif g == "pagamento_proximo":
            dias = (t.vencimento - hoje).days
            if t.direcao == "pagar" and t.status in EM_ABERTO and dinheiro(t.saldo) > 0 \
                    and 0 <= dias <= _janela(regra, 3) and cond(t):
                out.append(_oc_titulo(t, f"pagar:{t.vencimento.isoformat()}",
                                      f"{t.empresa or ''} · {t.descricao} a pagar em {dias} dia(s)"))
        elif g == "campo_alterado":
            if t.status not in ("cancelado",) and regra.campo:
                dados = _dados_titulo(t)
                if cond(t):
                    out.append(_oc_titulo(t, f"campo:{regra.campo}={_norm(dados.get(regra.campo))}",
                                          f"{t.empresa or ''} · {t.descricao}"))
    for r in e.recorrencias:
        base = {"empresa.nome": r.empresa or "—", "recorrencia.descricao": r.descricao}
        if g == "recorrencia_a_gerar":
            ate = hoje + timedelta(days=_janela(regra, 5))
            for comp in competencias_a_gerar(situacao=r.situacao, inicio=r.inicio, fim=r.fim, frequencia=r.frequencia,
                                             ate=ate, existentes=set(r.competencias_existentes)):
                out.append(Ocorrencia("recorrencia", r.id, f"competencia:{comp}", f"{r.descricao} · competência {comp}",
                                      r.responsavel_id, None, r.empresa_id, {**base, "recorrencia.competencia": comp}))
        elif g == "recorrencia_a_renovar":
            dias = (r.fim - hoje).days
            if r.situacao == "ativa" and 0 <= dias <= _janela(regra, 30):
                out.append(Ocorrencia("recorrencia", r.id, f"renovar:{r.fim.isoformat()}",
                                      f"{r.descricao} · termina em {_br(r.fim)}", r.responsavel_id, None, r.empresa_id,
                                      {**base, "recorrencia.fim": _br(r.fim)}))
    if g == "saldo_abaixo_limite" and e.caixa is not None:
        limite = dinheiro(_num(regra.valor_esperado or "0") or 0)
        if dinheiro(e.caixa.saldo_projetado) < limite:
            out.append(Ocorrencia("caixa", 0, f"saldo:{hoje.isoformat()}",
                                  f"Saldo projetado {formatar_brl(e.caixa.saldo_projetado)} abaixo de {formatar_brl(limite)}",
                                  None, None, None,
                                  {"caixa.saldo_projetado": formatar_brl(e.caixa.saldo_projetado),
                                   "caixa.limite": formatar_brl(limite), "caixa.formula": e.caixa.formula}))
    return out


def ocorrencias(regra: Regra, estado: Estado, hoje: date) -> list[Ocorrencia]:
    """Ocorrências elegíveis HOJE (ordem estável por registro). Pura: mesmo estado → mesma lista."""
    if regra.gatilho not in GATILHOS.get(regra.area, {}):
        return []
    lista = _comercial(regra, estado, hoje) if regra.area == "comercial" else _financeiro(regra, estado, hoje)
    vistos, out = set(), []
    for oc in sorted(lista, key=lambda o: (o.registro_tipo, o.registro_id, o.ocorrencia)):
        if (oc.registro, oc.ocorrencia) not in vistos:
            vistos.add((oc.registro, oc.ocorrencia))
            out.append(oc)
    return out


# ---------------------------------------------------------------------------------------------- execução (decisões)
def somar_dias_uteis(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def prazo_da_atividade(gatilho: str, prazo_dias: int | None, hoje: date) -> date:
    """Gatilho de evento: prazo = hoje + N dias úteis ("retornar em 2 dias úteis"). Gatilho temporal: o prazo do
    gatilho é a janela, então a atividade vence hoje."""
    if gatilho in GATILHOS_DE_EVENTO and prazo_dias:
        return somar_dias_uteis(hoje, prazo_dias)
    return hoje


def responsavel(regra_responsavel: str | None, do_registro: int | None) -> int | None:
    if regra_responsavel and regra_responsavel.startswith("usuario:"):
        return int(regra_responsavel.split(":", 1)[1])
    return do_registro


def decidir_retentativa(resultado_anterior: str | None, tentativas: int) -> bool:
    """Execução já existente: só repete se falhou e ainda há tentativas (limite MAX_TENTATIVAS)."""
    return resultado_anterior == "falhou" and tentativas < MAX_TENTATIVAS
