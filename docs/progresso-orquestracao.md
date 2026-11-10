# Progresso — Orquestração (IA unificada · Automações · Integrações)

Agente: Orquestração · 10/11/2026 · branch `worktree-agent-a97c2c1af800526e2`.

## Estado
- `uv run python -m pytest -q` → **299 testes verdes** (37 em `tests/orquestracao`, 38 em `tests/domain/test_automacao.py`); `ruff check app tests` limpo.
- `npm run lint` ✔ · `npm run build` ✔ · `tsc --noEmit` ✔.
- Migração nova `alembic/versions/0002_orquestracao_motor.py` (revision `0002_orquestracao`, down `0001`): colunas
  `automacao.ativada_em`, `automacao_execucao.registro_criado` / `detalhe`, `integracao.testado_em` /
  `aguardando_conector`. **Sem tabela nova** (o teste do core conta 38 tabelas). O teste "migração bate com os modelos"
  passa (DIFF []).

## API (`/api/orquestracao`)
| Rota | Permissão | O que faz |
|---|---|---|
| `GET /leitura?modulo=comercial\|financeiro\|nucleo` | `orquestracao.ia.ver` | Leitura do momento (IA se ligada; senão `app.domain.leitura`) |
| `GET /ia/estado` | `orquestracao.ia.ver` | `{ligada, provedor, modelo, configurar_em}` |
| `POST /ia/perguntar` | `orquestracao.ia.editar` (mapa do core) | `{escopo: registro\|modulo\|tudo, modulo, tela, registro:{tipo,id}?, pergunta, conversa_id?}` → formato único; grava `ia_conversa`/`ia_mensagem` |
| `GET /ia/conversas`, `GET /ia/conversas/{id}/mensagens` | `orquestracao.ia.ver` | histórico do próprio usuário |
| `POST /ia/comunicacoes/{id}/analisar` | `comercial.comunicacoes.editar` + `orquestracao.ia.ver` | grava `comunicacao.analise` + `analisada_em` (IA ou heurística) e audita |
| `POST /acoes/executar` | `orquestracao.ia.editar` + `comercial.atividades.editar` | só `criar_atividade`; cria a atividade (`origem="ia"`) e audita |
| `GET /automacoes/catalogo`, `GET /automacoes/modelos?area=` | `orquestracao.automacoes.ver` | gatilhos, ações, operadores, funis/etapas, campos; 15 modelos |
| `GET/POST /automacoes?area=`, `GET/PATCH /automacoes/{id}` | `orquestracao.automacoes.*` + acesso à área | CRUD (nada é excluído; pausar encerra) |
| `POST /automacoes/{id}/testar` · `/ativar` · `/pausar` | `orquestracao.automacoes.editar` | prévia sem executar; ativar envio exige canal conectado (400 "Conecte o canal autorizado antes de ativar envios") |
| `GET /automacoes/execucoes?area=&automacao_id=` | `orquestracao.automacoes.ver` | histórico (execuções e testes) |
| `GET /automacoes/avisos` | livre (logado) | avisos de "Notificar responsável" do próprio usuário |
| `GET /integracoes`, `GET/PUT /integracoes/{tipo}`, `POST /integracoes/{tipo}/testar` · `/revogar` | `orquestracao.integracoes.ver/editar` | cards, segredo somente escrita, teste, revogação |

"Acesso à área" das automações: Comercial exige `comercial.atividades.ver`; Financeiro exige `financeiro.cobrancas.ver`
(os perfis padrão Comercial e Financeiro veem um a área do outro só pelo Gestor).

## Formato único de resposta (IA e regras)
`{titulo, analise, proxima_acao, evidencias:[{fonte, trecho}], limites:[], acoes_sugeridas:[{tipo, rotulo, payload}],
origem: "ia"|"regras", ferramentas:[]}` (+ `ia_ligada`, `conversa_id`, `mensagem_id`). `app.domain.leitura.ler_momento`
passou a devolver o mesmo formato; por compatibilidade mantém `evidencias[].texto` (= trecho) e `acoes_sugeridas[].registro`.
Tipos de ação: `criar_atividade` (vira registro só após o clique) e `abrir_registro` (atalho de navegação).

## Ferramentas de IA (`modules/orquestracao/ia/ferramentas.py`)
| Nome | Dados | Permissão |
|---|---|---|
| oportunidades | etapa, valor, MRR, próxima ação, dias na etapa × limite, campos personalizados | `comercial.oportunidades.ver` |
| atividades | pendentes/recentes, atraso, origem | `comercial.atividades.ver` |
| comunicacoes | conversas vinculadas; o conteúdo entra como DADO importado | `comercial.comunicacoes.ver` |
| desempenho | conversão, ticket, ciclo mediano (fórmulas do domínio) | `comercial.desempenho.ver` |
| titulos | a receber/pagar, saldo, vencimento, situação, cobrança (se `financeiro.cobrancas.ver`) | `financeiro.titulos.ver` |
| baixas | recebimentos/pagamentos dos últimos 60 dias | `financeiro.baixas.ver` |
| caixa | saldo gerencial e projeção (fórmula visível) | `financeiro.caixa.ver` |
| cadastros | empresas (papéis, contatos) | `nucleo.cadastros.ver` |

Todas respeitam "só meus registros". Ferramenta sem permissão não roda e vira limite ("Sem acesso pelo seu perfil: …").
Escopo → ferramentas: registro (o registro e o que se liga a ele), módulo (as da área), tudo (todas).
Anti-injeção: prompt de sistema manda ignorar instruções do conteúdo importado; o conteúdo vai em
`<conteudo_importado>` com `<`/`>` neutralizados; ações fora de `criar_atividade` são descartadas e o payload passa por
lista fechada. JSON validado por Pydantic com **uma** nova tentativa; depois (ou se o provedor falhar) cai nas regras com o
motivo em `limites`. Provedor falso injetável: `gateway.definir_gerador(fn)` (testes nunca chamam provedor real).

## Motor de automações (`modules/orquestracao/motor.py`, regras puras em `app/domain/automacao.py`)
Registrado no worker (`tarefas.py`, a cada 5 min, por organização). Varre o estado (não depende de chamadas dos módulos).
Gatilhos implementados — Comercial: oportunidade criada · movida de etapa (com etapa de destino) · ganha · perdida
(eventos novos de `oportunidade_evento` após a ativação) · campo personalizado alterado (dispara quando o campo passa a
casar com a condição) · sem interação por N dias · atividade atrasada · data de fechamento próxima · reunião encerrada.
Financeiro: recebível confirmado · vencimento próximo · título vencido · recebimento parcial · recebimento total ·
pagamento próximo · recorrência a gerar · recorrência a renovar · campo alterado (campos do título) · saldo projetado
abaixo do limite (limite = "valor esperado").
Ações: Criar atividade (`origem="automacao"`, prazo em dias úteis nos gatilhos de evento; reunião sai com horário sugerido
09:00–10:00) · Notificar responsável (aviso interno, `GET /automacoes/avisos`) · Atualizar campo (`campo = valor`;
oportunidade: campos personalizados e próxima ação; título: observações) · Enviar e-mail/WhatsApp → execução
`pendente_conector` (nada é enviado). Idempotência por `chave_idempotencia` = automação:registro:ocorrência (UNIQUE no
banco); retentativas até 3; prevenção de ciclo (atividade criada por uma automação não dispara a mesma; atualizar o
próprio campo monitorado é recusado); cobrança ignora título em contestação, recebido ou cancelado. Toda mudança feita
pelo motor é auditada (usuário vazio = sistema).

## Integrações
Google Calendar, Microsoft Outlook, E-mail, WhatsApp. Segredo cifrado (Fernet/MASTER_KEY), somente escrita (só "configurado"
+ 4 últimos). Testar: E-mail usa o SMTP do core (sem SMTP → erro claro); WhatsApp/Google/Outlook validam formato (conta,
escopos, segredo ≥ 20) e ficam "Aguardando conector oficial" — sem chamada externa. Revogar apaga o segredo e **pausa** as
automações de envio do canal. Ativar automação de envio exige a integração com estado `conectado` (hoje só o e-mail chega lá).

## Telas
- Drawer do assistente (`components/flic/assistente-drawer.tsx`): escopo, contexto, pergunta, resposta no formato único,
  "Próxima ação sugerida", bloco fonte/evidência/limite, "Assistentes e fontes consultadas", "Criar tarefa após revisão"
  (revisão de assunto/prazo antes de criar), aviso de IA desligada com link para Configurações › IA. Novo helper
  `perguntarAoAssistente(escopo, pergunta, registro?)` em `components/orquestracao/eventos-ia.ts` abre o drawer já perguntando.
- `/comercial|financeiro|nucleo/assistente`: atalhos (Analisar este módulo · Relacionar vendas e caixa · Priorizar minha
  semana), estado da IA e leitura do momento do módulo.
- `/nucleo/automacoes`: área, abas Modelos (15) / Minhas automações / Histórico, editor completo, Testar, Ativar/Pausar.
- `/nucleo/integracoes`: 4 cards + drawer com requisitos, conta, escopos, responsável, segredo, Testar conexão, Revogar.

## Para os outros módulos
- **Comercial**: a tela Comunicações pode chamar `POST /api/orquestracao/ia/comunicacoes/{id}/analisar` (devolve e grava
  a análise) e mostrar `analise.citacoes`/`limites`. Para "Criar tarefa sugerida", use `POST /api/orquestracao/acoes/executar`
  `{tipo:"criar_atividade", payload:{assunto, tipo, prazo, oportunidade_id}}` ou crie pela própria rota de atividades.
  Continue gravando `oportunidade_evento` com os tipos combinados (criada, etapa, ganha, perdida…) — o motor depende disso.
- **Comercial/Financeiro (Hoje)**: `GET /api/orquestracao/leitura?modulo=` devolve a "Leitura do momento" pronta (componente
  `Insight` + `CorpoRespostaIA` de `components/orquestracao/resposta-ia.tsx`), ou chamem `app.domain.leitura.ler_momento`.
- Telas com registro: `abrirAssistente("Este registro", {tipo, id, rotulo})` — tipos aceitos: oportunidade, titulo,
  empresa, atividade, comunicacao. Atalhos `abrir_registro` levam a `/<rota>?id=<id>` (leiam `?id=` para abrir o drawer).

## Pedidos / pendências
- **Core (não editei)**: o teste `tests/test_permissoes.py` fixa `POST /orquestracao/ia/perguntar` → `orquestracao.ia.editar`;
  por isso o perfil "Somente leitura" (só `ia.ver`) vê a leitura do momento mas não pergunta. Se a decisão for deixar
  perguntar com `ia.ver`, basta mudar esse teste e acrescentar a regra em `orquestracao/routes.py`.
- **Migrações em paralelo**: se outro módulo também criar `0002_*` com `down_revision='0001'`, o Alembic terá duas cabeças —
  quem integrar precisa encadear (ou `alembic merge`). A minha é `0002_orquestracao`.
- `components/flic/assistente-pagina.tsx` (da fundação) ficou sem uso: as páginas Assistente usam
  `components/orquestracao/assistente-tela.tsx`. Pode ser apagado na integração.
- Conectores reais (OAuth Google/Microsoft, WhatsApp Business, IMAP) e o envio de fato ficam para a próxima fase; o motor
  já registra os envios como `pendente_conector`.
- Leitura do momento com IA ligada chama o provedor a cada abertura da tela (sem cache).
- Sem teste no navegador com o backend real (só lint/build/tsc e testes de API).
