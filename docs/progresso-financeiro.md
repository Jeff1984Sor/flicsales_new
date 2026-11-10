# Progresso — Módulo Financeiro

Agente: Financeiro · 10/11/2026 · escopo: `backend/app/modules/financeiro/`, `backend/tests/financeiro/`, regras financeiras em
`backend/app/domain/`, `frontend/components/financeiro/`, `frontend/lib/tipos-financeiro.ts` e as telas do Financeiro
(menos Empresas, Fornecedores, Categorias, Centros de custo, Contas e Assistente, que são do Núcleo/Orquestração).

## Estado
- `uv run python -m pytest -q` → **292 verdes** (suíte toda; Financeiro: 47 de API + 24 de domínio novos).
- `uv run python -m ruff check app tests` → limpo.
- `npm run lint` ✔ · `npm run build` ✔ · `tsc --noEmit` ✔.
- Sem migração nova: os modelos da Fundação (`0001`) atenderam tudo.

## API (`/api/financeiro`, permissões do mapa padrão de `app/core/permissoes.py`)
| Rota | Permissão | O que faz |
|---|---|---|
| `GET /hoje` | titulos.ver | KPIs (saldo gerencial, recebíveis vencidos, aprovações pendentes, recorrências ativas), fila de cobrança e **leitura do momento determinística** (`app.domain.leitura`; títulos em contestação ficam fora da leitura) |
| `GET /titulos` `?direcao&estado&q&empresa_id&origem_oportunidade_id&pagina&por_pagina` | titulos.ver | `Pagina<TituloOut>`; `estado=vencido` é derivado (aberto/parcial com vencimento < hoje) |
| `GET /titulos/contagens?direcao&q` | titulos.ver | números dos chips (todos, aberto, rascunho, parcial, liquidado, cancelado, vencido) |
| `GET /titulos/opcoes` | titulos.ver | empresas, categorias, centros de custo e contas ativas para os formulários |
| `POST /titulos` | titulos.editar | cria (nasce **aberto**; `rascunho: true` opcional); a pagar nasce **pendente**; `aprovacao: "aprovado"` exige alçada |
| `GET /titulos/{id}` | titulos.ver | detalhe + `origem` ("Oportunidade #n — título" / recorrência / manual) + baixas + cobranças |
| `PATCH /titulos/{id}` | titulos.editar | grava só o enviado; **recusa com baixa ativa** ou cancelado; mudar aprovação exige alçada |
| `POST /titulos/{id}/confirmar` | titulos.editar | rascunho → aberto (não é baixa) |
| `POST /titulos/{id}/cancelar` `{motivo}` | titulos.editar | motivo obrigatório; recusa com baixa ativa |
| `POST /titulos/{id}/aprovar` | **aprovacoes.editar** | registra quem/quando |
| `GET/POST /titulos/{id}/baixas` | baixas.ver/editar | baixa gerencial (domínio `validar_baixa`) com **UPDATE condicional** do saldo |
| `GET /baixas` `?situacao&direcao&q` | baixas.ver | trilha |
| `POST /baixas/{id}/estornar` `{motivo}` | baixas.editar | nunca apaga; título volta a ter saldo/estado; dois estornos simultâneos: só um vale |
| `GET /aprovacoes?situacao=pendente|aprovado|todos` | aprovacoes.ver | contas a pagar não canceladas |
| `GET/POST /transferencias` | caixa.ver/editar | contas diferentes e ativas, valor > 0, data entre as datas-base e hoje |
| `GET/POST /recorrencias`, `GET/PATCH /recorrencias/{id}` | recorrencias.* | CRUD (situação ativa/pausada/cancelada; nada é excluído) + `competencias_geradas`, `proxima_competencia` |
| `POST /recorrencias/{id}/gerar` `{competencia}` | recorrencias.editar | título em **rascunho**, sem duplicar, na vigência, alinhado à frequência (a pagar nasce pendente) |
| `GET/POST /cobrancas`, `GET/PATCH /cobrancas/{id}` | cobrancas.* | ligada a título a receber confirmado; promessa exige data; valor prometido ≤ saldo |
| `GET /cobrancas/contestados` | cobrancas.ver | `{titulo_ids: [...]}` — **a automação de cobrança deve pular esses títulos** |
| `GET /caixa` | caixa.ver | saldo por conta (inicial + baixas não estornadas ± transferências), entradas/saídas abertas (rascunho/cancelado fora), saldo após títulos, fórmulas e texto de limites |
| `GET /dashboards` | caixa.ver | caixa + aging a receber e a pagar (a vencer, 1–30, 31–60, 61–90, 90+) |

Auditoria em toda mudança: `titulo.criar|editar|confirmar|cancelar|aprovar`, `baixa.registrar|estornar`,
`transferencia.criar`, `recorrencia.criar|editar|gerar_competencia` (worker grava como "Robô"), `cobranca.criar|editar`.

**Concorrência da baixa** (`operacoes.debitar_saldo`): `UPDATE titulo SET saldo = saldo − v WHERE id = … AND saldo >= v AND
status IN ('aberto','parcial')`; rowcount 0 → "Valor deve ser positivo e não superar o saldo". A leitura usa
`SELECT … FOR UPDATE` (trava no Postgres) e o CHECK `saldo >= 0` é a última barreira. Teste:
`test_duas_baixas_simultaneas_nao_estouram_o_saldo` (sessão B com leitura velha é recusada).

## Serviço para outros módulos (`modules/financeiro/servico.py`)
- `preparar_recebiveis_do_ganho(...)` — **assinatura intacta** (Comercial).
- Novo: `titulos_em_contestacao(db) -> set[int]` e `cobranca_suspensa(db, titulo_id) -> bool` (Orquestração/automações:
  suspende ao receber, cancelar, rascunho ou contestar).

## Worker (`modules/financeiro/tarefas.py`)
`gerar-competencias-recorrencias` (a cada 6 h): para cada recorrência ativa gera, em rascunho, a competência cujo vencimento
cai entre hoje e hoje + 30 dias (`app.domain.recorrencia.proximas_competencias`). Idempotente (domínio + UNIQUE).
Competências passadas sem título não são geradas sozinhas — a tela "Gerar competência" cuida delas (evita enxurrada de
rascunhos retroativos; **ver Dúvidas**).

## Domínio acrescentado (`app/domain/`, com testes em `tests/domain/test_financeiro_aging_cobranca.py`)
- `titulos.faixa_aging/aging` (+ `TituloAging`, `FaixaAging`): só aberto/parcial com saldo > 0.
- `recorrencia.proximas_competencias` (horizonte do worker).
- `cobranca.py` (novo): `validar_cobranca`, `cobranca_suspensa`, situações e canais.

## Telas (frontend)
`/financeiro` (Hoje: Acesso rápido, Leitura do momento por regras com Fonte, KPIs com fórmula, Fila de cobrança, Comandos),
`/receber` e `/pagar` (chips com contagem, busca, Exportar CSV, tabela, drawer de detalhe com Editar / Confirmar título /
Registrar recebimento|pagamento / Cancelar título / Histórico de baixas com Estornar / Perguntar à IA; links `?novo=1` e
`?titulo=<id>`), `/cobrancas`, `/recorrencias` (+ Gerar competência), `/caixa` (+ Transferir entre contas), `/aprovacoes`,
`/baixas`, `/transferencias`, `/dashboards` (caixa + aging em barras), `/gestao`. **Alt+N**: novo título a receber (Hoje e
A receber), a pagar (A pagar), novo registro nas demais. Textos de limite do protótipo ("Baixas são gerenciais. Nenhuma
operação bancária é executada.", "Sem conciliação bancária…"). Componentes em `frontend/components/financeiro/`.

## Pedidos a outros módulos
- **Núcleo** (`app/(app)/nucleo/historico/page.tsx`): acrescentar `"cobranca"` à lista `ENTIDADES` do filtro de auditoria.
- **Comercial**: o detalhe do título liga a origem para `/comercial/oportunidades?oportunidade=<id>`; abrir o drawer da
  oportunidade a partir desse parâmetro (ou dizer qual parâmetro usar). Para levar o usuário do "Revisar fechamento" às
  parcelas: `/financeiro/receber?titulo=<id>` abre o detalhe; a lista aceita `origem_oportunidade_id` na API.
- **Orquestração**: a automação "Cobrança após vencimento" deve consultar `GET /api/financeiro/cobrancas/contestados` (ou
  `servico.cobranca_suspensa`). Ferramentas de leitura da IA podem usar `GET /api/financeiro/hoje|caixa|dashboards`.
  `Gestão financeira` linka `/nucleo/automacoes?area=financeiro`.
- **Fundação/Coordenação**: nenhum pedido no `core/`.

## Dúvidas (decisão do Jefferson)
1. Lançamento manual nasce **aberto** (como no protótipo); "rascunho" ficou opcional. Ok?
2. Worker de recorrência: só a próxima competência dentro de 30 dias, sem gerar passadas automaticamente. Ok?
3. Editar título com baixa ativa: recusei **qualquer** edição (como o protótipo), não só a do valor.
4. Cobrança: só nasce para título confirmado com saldo (aberto/parcial); a edição posterior é livre para registrar o desfecho.
5. "Aprovações" lista só contas a pagar; descontos comerciais em aprovação ficam em Comercial › Propostas (texto na tela).

## Correções do QA (acesso, alçada e escopo) — decisões
- **Alçada**: editar `valor_original`, `empresa_id` ou `vencimento` de conta a pagar **aprovada** volta a aprovação para
  `pendente` (limpa quem/quando aprovou; fica na auditoria de `titulo.editar`). Regra pura
  `domain/titulos.exige_nova_aprovacao`. Descrição, categoria etc. não mexem na aprovação.
- **Contas a pagar** são da operação financeira: `financeiro.titulos.ver` sozinho (perfil Comercial, "leitura dos
  recebíveis") vê só **a receber**. Ver/abrir/criar **a pagar** exige também `financeiro.aprovacoes.ver` **ou**
  `financeiro.baixas.ver` (`servico.pode_ver_pagar`; Financeiro, Somente leitura e Gestor têm). Lista com
  `direcao=pagar` e contagens de pagar → 403 com mensagem; detalhe de título a pagar → 404; lista sem direção → só
  a receber. A IA usa a mesma regra (ferramenta de títulos e foco "Este registro"). No menu, "A pagar" passou a
  depender de `financeiro.aprovacoes` (o menu só aceita um recurso). Não mexi em `core/permissoes.py`: o perfil
  Comercial continua com `financeiro.titulos.ver`.
- **Caixa**: `GET /financeiro/hoje` só traz `saldo_gerencial` com `financeiro.caixa.ver`; `aprovacoes_pendentes` só
  para quem vê a pagar; `recorrencias_ativas` só com `financeiro.recorrencias.ver` (senão `null`, a tela esconde o KPI).
  `/titulos/opcoes` só traz contas financeiras com `financeiro.caixa.ver` ou `financeiro.baixas.editar` (quem
  registra baixa precisa escolher a conta).
- **Só meus registros**: Hoje (fila, totais, aprovações, recorrências), baixas (lista; estornar baixa de título fora
  do escopo → 404), cobranças (minha se sou responsável pela cobrança **ou** pelo título; detalhe/edição → 404),
  aprovações e recorrências (lista; detalhe/edição/gerar → 404). Criar cobrança só para título do meu escopo.
- CSV de A receber/A pagar exporta **todos** os títulos dos filtros atuais (página a página, 200 por vez) e avisa
  quantos foram exportados.

## Não feito / limites
- Não testei no navegador com o backend rodando (só testes de API, lint e build).
- Juros/multa/desconto na baixa, reajuste de recorrência, anexo de comprovante e DRE: fora desta fase.
- Postgres não testado (SQLite); o `FOR UPDATE` e o UPDATE condicional são SQL portável.
