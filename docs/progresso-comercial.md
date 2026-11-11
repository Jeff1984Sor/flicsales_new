# Progresso — Comercial

Agente: Comercial · 10/11/2026 · escopo: `backend/app/modules/comercial/`, `backend/tests/comercial/`,
`frontend/components/comercial/`, `frontend/lib/tipos-comercial.ts` e as páginas do Comercial (menos Empresas, Pessoas,
Produtos e Assistente).

## Estado
- `uv run python -m pytest -q` → **277 testes verdes** (53 do Comercial). `uv run python -m ruff check app tests` → limpo.
- `npm run lint` → limpo · `npm run build` → ok · `tsc --noEmit` → limpo.
- Sem migração nova: os modelos da `0001` bastaram (eventos, interesse em `campos_custom`, ciclo usa `criado_em`).

## API `/api/comercial` (permissões pelo mapa padrão do core; prévias exigem só `ver`)
| Recurso | Rotas |
|---|---|
| Funis | `GET/POST /funis`, `PATCH /funis/{id}`, `PUT /funis/{id}/etapas` (probabilidade, limite de dias, critérios; etapa em uso não sai) |
| Oportunidades | `GET /oportunidades?funil_id&resultado&q&responsavel_id&empresa_id`, `GET /oportunidades/opcoes` (empresas, pessoas, produtos, oportunidades, funis, campos, condições, interesse), `GET/PATCH /oportunidades/{id}`, `POST /oportunidades`, `POST /{id}/mover`, `/{id}/ganhar`, `/{id}/perder`, `/{id}/reabrir`, `GET /{id}/historico`, `POST /{id}/notas` |
| Atividades | `GET /atividades?tipo&status&q&oportunidade_id&empresa_id&responsavel_id&de&ate&atrasadas`, `GET/PATCH /atividades/{id}`, `POST /atividades`, `POST /atividades/{id}/concluir` |
| Comunicações | `GET /comunicacoes?oportunidade_id&empresa_id&canal&q`, `GET /comunicacoes/{id}`, `POST /comunicacoes` (texto colado), `PUT /comunicacoes/{id}/analise`, `POST /comunicacoes/{id}/resposta` (rascunho, sem envio) |
| Propostas | `GET/POST /propostas`, `GET/PATCH /propostas/{id}`, `POST /propostas/{id}/duplicar` (nova versão) |
| Metas e forecast | `GET/POST /metas`, `GET/PATCH /metas/{id}` (com `realizado`, `percentual`, `formula`), `GET /forecast?funil_id` |
| Desempenho | `GET /desempenho?inicio&fim&funil_id`, `GET /desempenho/evidencias?usuario_id&inicio&fim` |
| Dashboards | `GET /dashboards?funil_id`, `GET/POST /indicadores`, `PATCH /indicadores/{id}`, `POST /indicadores/previa` |
| Playbooks / Modelos | `GET/POST /playbooks`, `GET/PATCH /playbooks/{id}`; `GET/POST /modelos`, `GET/PATCH /modelos/{id}`, `POST /modelos/{id}/previa` |
| Hoje | `GET /hoje` → KPIs + atenção + agenda + saúde do funil + `leitura` determinística (`app.domain.leitura`) + `ia_ligada` |

### Contratos com os outros módulos
- **Histórico (`oportunidade_evento.tipo`)**: `criada`, `etapa`, `ganha`, `perdida`, `reaberta`, `proxima_acao`, `proposta`,
  `reuniao` (reunião vinculada e reunião encerrada), `nota` (nota livre, comunicação vinculada, atividade concluída).
  Serviço estável: `app.modules.comercial.servico.registrar_evento(db, oportunidade_id, tipo, texto, usuario_id)`.
- **Ganho**: `POST /oportunidades/{id}/ganhar {empresa_id | empresa_nome, valor, condicao, primeiro_vencimento}` →
  `validar_ganho` → `preparar_recebiveis_do_ganho` → evento `ganha` → auditoria → `{oportunidade, recebiveis, mensagem}`.
  Ganhar de novo = 400 "Esta venda já foi processada" (nada duplica). O front leva a `/financeiro/receber` com o toast
  "Venda ganha. Revise os recebíveis antes de confirmar." Responsável dos títulos = responsável da oportunidade.
- **Empresa nascendo na oportunidade**: `empresa_nome` busca pela chave normalizada; se não existir cria `Empresa`
  (prospect, origem "Oportunidade") com auditoria `empresa.criar`. Não altero empresas existentes.
- **Análise de comunicação**: o botão "Analisar" chama `POST /bff/orquestracao/ia/comunicacoes/{id}/analisar`; aceito a
  resposta como `{analise}`, a comunicação inteira ou a análise pura, e guardo via `PUT /comunicacoes/{id}/analise`
  (formato normalizado: `necessidades[]`, `objecoes[]`, `compromissos[]`, `citacoes[{trecho, fonte}]`, `limites[]`,
  opcionais `origem`, `resumo`, `tarefa_sugerida`). 404/erro → aviso amigável. Se a Orquestração já gravar direto
  em `comunicacao.analise`, o PUT continua inofensivo.
- **Leitura do momento**: o Hoje usa só `GET /api/comercial/hoje` (leitura por regras, mesmo formato da IA).
  Recebíveis vencidos entram na leitura apenas para quem tem `financeiro.titulos.ver` e não é "só meus registros".

## Telas (frontend)
Hoje (Acesso rápido, Leitura do momento com evidência/fonte/limite e "Entender e agir", 4 KPIs com fórmula, atenção
com Concluir, Do negócio ao recebimento, Agenda conectada "Prévia • sem conexão", Saúde da operação; Alt+N) ·
Oportunidades (seletor de funil, Criar funil, Configurar etapas, Kanban com arrastar, card com interesse e alerta de
limite, drawer com etapa incl. Ganha/Perdida, Contexto da negociação, Analisar registro, Marcar como ganha, recebíveis
de origem, Gestão da oportunidade, histórico + nota; Resultados do funil com Reabrir) · Atividades · Comunicações ·
Propostas (Ver documento, Duplicar) · Metas e forecast · Desempenho (Ver evidências, sem ranking) · Dashboards
(recharts, Configurar indicador, Calcular prévia) · Playbooks · Modelos de comunicação (variáveis, Pré-visualizar) ·
Gestão comercial.

## Decisões
- **"Em negociação"** no Hoje = abertas na última etapa de cada funil (o funil é configurável; não há etapa fixa).
- **Proposta com desconto**: "Aprovada internamente" exige `financeiro.aprovacoes.editar` (alçada do Gestor); "Enviada" e
  "Aceita" exigem passar antes por aprovação interna. "Aceita" só grava evento — não fecha a oportunidade.
- **Reabrir** vale só para perdidas; venda ganha se ajusta pela revisão financeira dos recebíveis.
- **Campo personalizado exigido na etapa** (`campo_custom.exigido_na_etapa_id`) é conferido ao mover.
- **Comunicações com "só meus registros"**: só as vinculadas às próprias oportunidades (importar exige vincular).
- **Metas com "só meus registros"**: as próprias + as de equipe.
- Regras novas e puras do módulo (eventos, períodos, meta, modelo/variáveis, análise, rascunho, gargalo) ficam em
  `app/modules/comercial/regras.py` com testes (o `app/domain/` é da Fundação).

## Pendências / pedidos
- **Núcleo**: trocar o `CampoEmpresa` (input + datalist em `components/comercial/dados.tsx`) pelo `SeletorEmpresa`
  reutilizável quando existir — mesmo contrato (`empresa_id` ou `empresa_nome`). Links da tela apontam para
  `/comercial/empresas`, `/nucleo/campos`, `/nucleo/integracoes` e `/nucleo/automacoes`.
- **Orquestração**: confirmar o formato de resposta de `POST /orquestracao/ia/comunicacoes/{id}/analisar` (ver acima).
  Agenda conectada: quando houver integração Google/Outlook conectada, expor um serviço de leitura para o Hoje trocar
  `agenda_conectada` (hoje sempre `false`).
- **Financeiro**: "Aprovações" pode listar `GET /api/comercial/propostas?status=em_aprovacao` e aprovar com
  `PATCH /api/comercial/propostas/{id} {"status": "aprovada_internamente"}` (o Gestor tem a permissão).
- Busca global (paleta) ainda não procura oportunidades.
- Não houve teste no navegador com backend rodando (só testes da API, lint e build).
- **Pedido do Núcleo (ajustes 11/2026)**: campo personalizado novo `multipla` grava **lista** de opções em
  `campos_custom[slug]`. O filtro de indicador em `rotas_gestao._calcular` compara `str(valor) == alvo` e não acha a
  opção dentro da lista — trocar por `app.modules.nucleo.regras.valor_corresponde(valor, filtro_valor)` (pura, testada).
  `conferir_campos_exigidos` já funciona (lista vazia nunca é gravada: vira ausência da chave).
