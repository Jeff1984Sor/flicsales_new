"""Perfis de acesso: catálogo de permissões e o mapa rota -> permissão aplicado no servidor.

Cada permissão é "<recurso>.<acao>", e o recurso pode ter pontos (ex.: "comercial.oportunidades.ver"): a AÇÃO é sempre
o último segmento. Níveis: "ver" e "editar" (criar, alterar, encerrar, estornar). Nada é excluído no FlicSales — o
DELETE de uma rota conta como "editar" (inativar/arquivar). O perfil administrador (Gestor) pode tudo.

O catálogo já traz TODOS os recursos dos módulos (núcleo, comercial, financeiro, orquestração): os agentes de módulo
NÃO editam este arquivo; registram as regras das suas rotas com `adicionar_regras` (no `routes.py` do módulo).

NEGAR POR PADRÃO: toda rota protegida passa por `deps.get_contexto`, que consulta `permissao_da_rota`.
Rota que não casa com nenhuma regra recebe 403. O teste `tests/test_cobertura_rotas.py` enumera todas as rotas do app e
falha se alguma ficar de fora.
"""

import re

ROTULO_ACAO = {
    "ver": "Ver",
    "editar": "Criar e editar",
}

VER_EDITAR = ["ver", "editar"]

CATALOGO: list[dict] = [
    {"grupo": "Núcleo", "recursos": [
        {"id": "nucleo.cadastros", "nome": "Cadastros mestres (empresas, pessoas, produtos e serviços)", "acoes": VER_EDITAR},
        {"id": "nucleo.campos", "nome": "Campos personalizados", "acoes": VER_EDITAR},
        {"id": "nucleo.administracao", "nome": "Administração (usuários, perfis de acesso, qualidade dos dados)",
         "acoes": VER_EDITAR},
        {"id": "auditoria", "nome": "Histórico de ações (auditoria)", "acoes": ["ver"]},
        {"id": "configuracoes", "nome": "Configurações (identidade, e-mail, IA)", "acoes": VER_EDITAR},
    ]},
    {"grupo": "Comercial", "recursos": [
        {"id": "comercial.oportunidades", "nome": "Oportunidades e funis (kanban, ganho, perda)", "acoes": VER_EDITAR},
        {"id": "comercial.atividades", "nome": "Atividades (tarefas, ligações, reuniões)", "acoes": VER_EDITAR},
        {"id": "comercial.comunicacoes", "nome": "Comunicações (conversas vinculadas e análise)", "acoes": VER_EDITAR},
        {"id": "comercial.propostas", "nome": "Propostas", "acoes": VER_EDITAR},
        {"id": "comercial.metas", "nome": "Metas e forecast", "acoes": VER_EDITAR},
        {"id": "comercial.desempenho", "nome": "Desempenho e dashboards comerciais", "acoes": VER_EDITAR},
        {"id": "comercial.recursos", "nome": "Playbooks e modelos de comunicação", "acoes": VER_EDITAR},
    ]},
    {"grupo": "Financeiro", "recursos": [
        {"id": "financeiro.titulos", "nome": "Títulos a receber e a pagar", "acoes": VER_EDITAR},
        {"id": "financeiro.baixas", "nome": "Baixas e estornos (recebimentos e pagamentos)", "acoes": VER_EDITAR},
        {"id": "financeiro.aprovacoes", "nome": "Aprovações (alçada de contas a pagar e descontos)", "acoes": VER_EDITAR},
        {"id": "financeiro.caixa", "nome": "Caixa, transferências e dashboards financeiros", "acoes": VER_EDITAR},
        {"id": "financeiro.cobrancas", "nome": "Cobranças e acordos", "acoes": VER_EDITAR},
        {"id": "financeiro.recorrencias", "nome": "Recorrências", "acoes": VER_EDITAR},
        {"id": "financeiro.cadastros", "nome": "Cadastros financeiros (categorias, centros de custo, contas, fornecedores)",
         "acoes": VER_EDITAR},
    ]},
    {"grupo": "Orquestração", "recursos": [
        {"id": "orquestracao.ia", "nome": "Assistente de IA (perguntar; criar ações sugeridas após revisão)",
         "acoes": VER_EDITAR},
        {"id": "orquestracao.automacoes", "nome": "Automações", "acoes": VER_EDITAR},
        {"id": "orquestracao.integracoes", "nome": "Integrações (agenda, e-mail, WhatsApp)", "acoes": VER_EDITAR},
    ]},
]

RECURSOS = {r["id"] for g in CATALOGO for r in g["recursos"]}
TODAS = {f"{r['id']}.{a}" for g in CATALOGO for r in g["recursos"] for a in r["acoes"]}


def separar(permissao: str) -> tuple[str, str]:
    """("comercial.oportunidades", "ver") de "comercial.oportunidades.ver"."""
    rec, _, acao = permissao.rpartition(".")
    return rec, acao


def _todas_de(*prefixos: str, acoes: tuple[str, ...] | None = None) -> set[str]:
    """Permissões dos recursos que são um dos `prefixos` ou começam por `prefixo.`."""
    out = set()
    for p in TODAS:
        rec, acao = separar(p)
        if any(rec == x or rec.startswith(x + ".") for x in prefixos) and (acoes is None or acao in acoes):
            out.add(p)
    return out


_COMERCIAL = (
    _todas_de("comercial")
    # a tela Comercial tem Empresas, Pessoas e Produtos (e a empresa pode nascer dentro da oportunidade)
    | _todas_de("nucleo.cadastros")
    | {"nucleo.campos.ver", "financeiro.titulos.ver", "orquestracao.ia.ver", "orquestracao.ia.editar",
       "orquestracao.automacoes.ver", "orquestracao.integracoes.ver"}
)
_FINANCEIRO = (
    _todas_de("financeiro") - {"financeiro.aprovacoes.editar"}  # alçada: só o Gestor aprova
    | _todas_de("nucleo.cadastros")  # a tela Financeiro tem Empresas e clientes e Fornecedores
    | {"nucleo.campos.ver", "comercial.oportunidades.ver", "comercial.propostas.ver", "orquestracao.ia.ver",
       "orquestracao.ia.editar", "orquestracao.automacoes.ver", "orquestracao.integracoes.ver"}
)
_SOMENTE_LEITURA = _todas_de("nucleo.cadastros", "nucleo.campos", "comercial", "financeiro", acoes=("ver",)) | {
    "orquestracao.ia.ver"}

# Perfis criados de saída. "Gestor" é o administrador (não excluível). Os demais o Gestor edita na matriz.
PERFIS_PADRAO: list[dict] = [
    {"nome": "Gestor", "descricao": "Acesso total: módulos, aprovações, administração, configurações e auditoria.",
     "cor": "#0B1020", "administrador": True, "sistema": True, "somente_meus_registros": False, "permissoes": []},
    {"nome": "Comercial", "descricao": "Módulo Comercial completo, cadastros compartilhados e leitura dos recebíveis.",
     "cor": "#0057D9", "administrador": False, "sistema": False, "somente_meus_registros": False,
     "permissoes": sorted(_COMERCIAL)},
    {"nome": "Financeiro", "descricao": "Módulo Financeiro (sem aprovar pagamentos), cadastros compartilhados e leitura da origem comercial.",
     "cor": "#00A89B", "administrador": False, "sistema": False, "somente_meus_registros": False,
     "permissoes": sorted(_FINANCEIRO)},
    {"nome": "Somente leitura", "descricao": "Vê cadastros, Comercial e Financeiro; não altera nada.",
     "cor": "#596579", "administrador": False, "sistema": False, "somente_meus_registros": False,
     "permissoes": sorted(_SOMENTE_LEITURA)},
]

# ------------------------------------------------------------------------------------------------- rota -> permissão
LIVRE = None  # basta estar logado (a própria conta, dados que todo usuário vê)
A = "/api"

# Rotas SEM login (cada uma é aceita de propósito). (método ou "*", regex do caminho completo).
PUBLICAS: list[tuple[str, str]] = [
    ("GET", r"/api/health$"),
    ("POST", r"/api/auth/(login|refresh|forgot|reset|forgot-codigo|reset-codigo)$"),
    ("*", r"/api/auth/primeiro-acesso$"),  # link de boas-vindas de organização nova (token assinado com prazo)
    ("GET", r"/api/public/(identidade|logo)$"),
    ("GET", r"/api/arquivos-publicos/[^/]+$"),  # link assinado com prazo
    ("*", r"/api/(docs|openapi\.json|redoc).*"),  # só existem com DEBUG (ver main.py)
]

# Rotas com autenticação PRÓPRIA (token de webhook, chave de API). Não usam o login dos usuários, mas cada rota
# declarada nestes prefixos precisa ter ao menos uma dependência de autenticação (verificado em teste).
PUBLICAS_AUTENTICACAO_PROPRIA: list[str] = [r"/api/webhooks/"]

# (métodos, regex do caminho SEM o /api, permissão). A primeira regra que casa vale.
#   "recurso.acao"  -> exata
#   "recurso.*"     -> pela ação do método: GET=ver, demais=editar (no FlicSales nada é excluído)
#   "recurso.*e"    -> idem (mantido por compatibilidade com o formato do MayaFit)
# Os prefixos dos módulos abaixo são o PADRÃO combinado com o frontend; cada módulo refina com `adicionar_regras`
# (que entra ANTES destas).
_REGRAS: list[tuple[str, str, str | None]] = [
    # --- core ---
    ("POST", r"/auth/usuarios/\d+/foto$", "nucleo.administracao.editar"),
    ("DELETE", r"/auth/usuarios/\d+/foto$", "nucleo.administracao.editar"),
    ("*", r"/auth/", LIVRE),
    ("GET", r"/config/identidade$", LIVRE),
    ("GET", r"/config/identidade/assinatura-imagem$", LIVRE),  # imagem da assinatura padrão (prévia nas telas)
    ("GET", r"/config/usuarios/opcoes$", LIVRE),  # lista curta (id, nome) para escolher responsável
    ("*", r"/config/identidade", "configuracoes.*e"),
    ("*", r"/config/(email|ia)", "configuracoes.*e"),
    ("*", r"/config/perfis", "nucleo.administracao.*e"),
    ("*", r"/config/usuarios", "nucleo.administracao.*e"),
    ("*", r"/auditoria", "auditoria.ver"),
    ("GET", r"/arquivos/", LIVRE),  # a categoria do arquivo é checada na própria rota (core/storage.py)
    # --- núcleo (/api/nucleo) ---
    ("*", r"/nucleo/(empresas|pessoas|produtos|cadastros)", "nucleo.cadastros.*e"),
    ("*", r"/nucleo/campos", "nucleo.campos.*e"),
    ("*", r"/nucleo/(administracao|qualidade|duplicidades)", "nucleo.administracao.*e"),
    # --- comercial (/api/comercial) ---
    ("GET", r"/comercial/hoje", "comercial.oportunidades.ver"),
    ("*", r"/comercial/(oportunidades|funis|etapas)", "comercial.oportunidades.*e"),
    ("*", r"/comercial/atividades", "comercial.atividades.*e"),
    ("*", r"/comercial/comunicacoes", "comercial.comunicacoes.*e"),
    ("*", r"/comercial/propostas", "comercial.propostas.*e"),
    ("*", r"/comercial/(metas|forecast)", "comercial.metas.*e"),
    ("*", r"/comercial/(desempenho|dashboards|indicadores)", "comercial.desempenho.*e"),
    ("*", r"/comercial/(playbooks|modelos)", "comercial.recursos.*e"),
    # --- financeiro (/api/financeiro) ---
    ("GET", r"/financeiro/hoje", "financeiro.titulos.ver"),
    ("*", r"/financeiro/titulos/\d+/baixas", "financeiro.baixas.*e"),
    ("*", r"/financeiro/titulos/\d+/aprovar", "financeiro.aprovacoes.editar"),
    ("*", r"/financeiro/(titulos|receber|pagar)", "financeiro.titulos.*e"),
    ("*", r"/financeiro/baixas", "financeiro.baixas.*e"),
    ("*", r"/financeiro/aprovacoes", "financeiro.aprovacoes.*e"),
    ("*", r"/financeiro/(caixa|transferencias|dashboards)", "financeiro.caixa.*e"),
    ("*", r"/financeiro/cobrancas", "financeiro.cobrancas.*e"),
    ("*", r"/financeiro/recorrencias", "financeiro.recorrencias.*e"),
    ("*", r"/financeiro/(categorias|centros-custo|contas|fornecedores)", "financeiro.cadastros.*e"),
    # --- orquestração (/api/orquestracao) ---
    ("*", r"/orquestracao/(ia|assistente|leitura)", "orquestracao.ia.*e"),
    ("*", r"/orquestracao/automacoes", "orquestracao.automacoes.*e"),
    ("*", r"/orquestracao/integracoes", "orquestracao.integracoes.*e"),
]


def _compilar(rx: str) -> re.Pattern:
    """Prefixo /api + regex; sem '$' nem '/' no fim, exige fronteira (/comercial/metas não casa /comercial/metas-x)."""
    fim = "" if rx.endswith(("$", "/", "*")) else r"(?![A-Za-z0-9_-])"
    return re.compile(A + rx + fim)


_COMPILADAS: list[tuple[str, re.Pattern, str | None]] = [(m, _compilar(rx), p) for m, rx, p in _REGRAS]
_PUBLICAS_C = [(m, re.compile(rx)) for m, rx in PUBLICAS]
_PROPRIA_C = [re.compile(rx) for rx in PUBLICAS_AUTENTICACAO_PROPRIA]


def adicionar_regras(regras: list[tuple[str, str, str | None]], *, antes: bool = True) -> None:
    """Módulos registram suas rotas aqui (o regex NÃO leva o prefixo /api). Por padrão entram antes das demais.

    Ex.: adicionar_regras([("POST", r"/comercial/oportunidades/\\d+/ganhar$", "comercial.oportunidades.editar")])
    A permissão precisa existir no catálogo (senão ValueError: nada de permissão inventada).
    """
    for _m, _rx, p in regras:
        if p is not None:
            rec, acao = separar(p)
            if rec not in RECURSOS or (acao not in ("*", "*e") and p not in TODAS):
                raise ValueError(f"Permissão fora do catálogo: {p}")
    novas = [(m, _compilar(rx), p) for m, rx, p in regras]
    if antes:
        _COMPILADAS[:0] = novas
    else:
        _COMPILADAS.extend(novas)


def _acao_por_metodo(metodo: str) -> str:
    return "ver" if metodo in ("GET", "HEAD", "OPTIONS") else "editar"


def permissao_da_rota(metodo: str, caminho: str) -> tuple[bool, str | None]:
    """(mapeada?, permissão exigida). Permissão None = livre para quem está logado. Não mapeada = negar."""
    for m, rx, p in _COMPILADAS:
        if (m == "*" or m == metodo) and rx.match(caminho):
            if p is None:
                return True, None
            rec, acao = separar(p)
            if acao in ("*", "*e"):
                acao = _acao_por_metodo(metodo)
            return True, f"{rec}.{acao}"
    return False, None


def rota_publica(metodo: str, caminho: str) -> bool:
    return any((m == "*" or m == metodo) and rx.match(caminho) for m, rx in _PUBLICAS_C)


def rota_autenticacao_propria(caminho: str) -> bool:
    return any(rx.match(caminho) for rx in _PROPRIA_C)


def normalizar(permissoes: list[str]) -> list[str]:
    """Só permissões conhecidas; quem pode editar também pode ver (quando o recurso tem 'ver')."""
    ok = {p for p in permissoes if p in TODAS}
    ok |= {f"{separar(p)[0]}.ver" for p in ok if f"{separar(p)[0]}.ver" in TODAS}
    return sorted(ok)
