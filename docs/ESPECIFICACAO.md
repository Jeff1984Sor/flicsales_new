# Especificação — FlicSales OS

Extraída do protótipo [`prototipo/flicsales-prototipo.html`](prototipo/flicsales-prototipo.html) em 10/11/2026.
O protótipo é um mockup em memória ("IA e integrações simuladas"); aqui está o que precisa existir **de verdade**:
persistido, com permissão, auditoria e testes. Onde o protótipo dizia "no produto, será necessário…", isso entra como requisito.

Códigos `COM-xx`, `FIN-xx`, `NUC-xx`, `IA-xx` são só para rastrear — **nunca aparecem na tela**.

---

## 1. Modelo de dados (todas as tabelas sem `tenant_id`; um banco por organização)

### Núcleo (cadastros compartilhados)
| Tabela | Campos |
|---|---|
| `empresa` | nome* (único), documento (CNPJ/CPF), nome_fantasia, segmento, porte, site, email_financeiro, telefone, endereco, responsavel_id→usuario, papeis (prospect/cliente/fornecedor/parceiro — multi), origem, observacoes, campos_custom JSON, ativo |
| `pessoa` | nome*, empresa_id, cargo (papel na compra), email, telefone, responsavel_id, canal_preferido (email/ligacao/whatsapp), observacoes, campos_custom JSON, ativo |
| `produto` | nome*, tipo* (servico/produto), codigo, unidade, preco_referencia, recorrente bool, descricao, ativo |
| `fornecedor` | → é `empresa` com papel fornecedor + extras: categoria_padrao_id, condicao_habitual (pode ser view/aba da empresa; decidir no Fundação e registrar) |
| `categoria` | nome*, natureza* (receita/despesa), superior_id, ativo |
| `centro_custo` | nome*, codigo* (único), responsavel_id, ativo |
| `conta_financeira` | nome*, instituicao, saldo_inicial* (pode ser negativo), data_base*, ativo. Não edita saldo inicial/data-base se houver movimento |
| `campo_custom` | nome*, slug, tipo* (texto/numero/moeda/data/sim_nao/lista), objeto* (empresa/pessoa/oportunidade), opcoes JSON, obrigatorio, exigido_na_etapa_id (opcional), arquivado |
| `auditoria` | (core) quando, usuario, acao, entidade, entidade_id, resumo, antes JSON, depois JSON |

### Comercial
| Tabela | Campos |
|---|---|
| `funil` | nome*, ativo |
| `etapa` | funil_id*, nome*, ordem, probabilidade (0–100), limite_dias, criterios (texto) |
| `oportunidade` | titulo*, funil_id*, etapa_id, resultado (aberta/ganha/perdida), empresa_id, contato_id→pessoa, responsavel_id*, valor_unico, valor_recorrente_mensal, previsao_fechamento, proxima_acao, proxima_acao_prazo, origem, necessidade, decisor, orcamento_concorrencia, criterio_sucesso, motivo_perda, concorrente, data_retomada, ganha_em, perdida_em, entrou_etapa_em, campos_custom JSON (ex.: Interesse = Baixo/Médio/Alto) |
| `oportunidade_evento` | histórico compartilhado: oportunidade_id, quando, tipo (etapa, reunião vinculada, proposta, nota…), texto |
| `atividade` | assunto*, tipo* (tarefa/email/ligacao/whatsapp/reuniao), responsavel_id*, empresa_id, oportunidade_id, prazo*, hora_inicio, hora_fim, fuso, participantes, canal (link/telefone/endereço), objetivo, resultado, status (pendente/concluida), concluida_em, origem (manual/automacao/ia) |
| `comunicacao` | canal* (reuniao/email/whatsapp/notas), titulo, conteudo*, data, empresa_id, oportunidade_id, analise JSON (necessidades, objeções, compromissos, citações), analisada_em |
| `proposta` | titulo*, oportunidade_id*, empresa_id*, versao*, escopo*, produto_id, quantidade*, preco_unitario*, desconto_pct, mensalidade_adicional, validade*, condicao* (à vista/2x/3x/recorrente mensal), responsavel_id*, status* (rascunho/em_aprovacao/aprovada_internamente/enviada/aceita/recusada), justificativa_desconto, total (calculado) |
| `meta` | nome*, responsavel (pessoa/equipe)*, inicio*, fim*, indicador* (receita única ganha / MRR novo / vendas ganhas / atividades concluídas), alvo*, funil_id |
| `playbook` | nome*, funil_id, etapa_id, objetivo*, perguntas_discovery, criterios_avanco*, objecoes, proxima_acao_padrao, responsavel |
| `modelo_comunicacao` | nome*, canal* (email/whatsapp/ligacao/reuniao), finalidade* (prospecção/follow-up/proposta/cobrança/renovação), assunto, conteudo* (com variáveis), status (rascunho/revisado) |
| `indicador_config` | dashboards configuráveis: nome, objeto, métrica (soma valor único / quantidade), filtro campo_custom + valor |

### Financeiro
| Tabela | Campos |
|---|---|
| `titulo` | direcao* (receber/pagar), empresa_id* (cliente ou fornecedor), descricao*, documento, emissao, competencia (AAAA-MM), vencimento*, valor_original*, saldo (calculado/armazenado), categoria_id, centro_custo_id, conta_prevista_id, forma (pix/boleto/transferencia/cartao/dinheiro/outra), responsavel_id*, observacoes, status (rascunho/aberto/parcial/liquidado/cancelado — "vencido" é derivado), aprovacao (pendente/aprovado — só pagar), motivo_cancelamento, origem_oportunidade_id, origem_recorrencia_id, parcela (n/total). **Únicos:** (origem_oportunidade_id, parcela) e (origem_recorrencia_id, competencia) |
| `baixa` | titulo_id*, valor*, data*, conta_id*, forma*, referencia_comprovante, observacao, estornada bool, estorno_motivo, estornada_em, estornada_por |
| `transferencia` | conta_origem_id*, conta_destino_id*, valor*, data*, descricao |
| `recorrencia` | descricao*, direcao* (receber/pagar), empresa_id*, valor_ciclo*, frequencia* (mensal/trimestral/anual), inicio*, fim*, dia_vencimento* (1–28), categoria_id, centro_custo_id, situacao* (ativa/pausada/cancelada) |
| `cobranca` | assunto*, titulo_id*, responsavel_id*, canal*, situacao* (em acompanhamento/promessa de pagamento/em contestação/resolvida), data_prometida, valor_prometido, proximo_contato, historico* |

### Plataforma (Núcleo)
| Tabela | Campos |
|---|---|
| `automacao` | area* (comercial/financeiro), nome*, gatilho*, funil_id, etapa_destino, campo, operador (igual/diferente/maior/menor/preenchido), valor_esperado, prazo_dias, acao* (criar atividade/enviar e-mail/enviar WhatsApp/atualizar campo/notificar responsável), tipo_atividade, responsavel_regra, destinatario, conteudo*, estado (rascunho/ativa/pausada) |
| `automacao_execucao` | automacao_id, quando, chave_idempotencia (única), registro, resultado, simulacao bool, erro, tentativas |
| `integracao` | tipo (google_calendar/outlook/email/whatsapp), estado (desconectado/conectado/erro), escopos, conta, segredo_cifrado, ultimo_erro |
| `ia_conversa` / `ia_mensagem` | escopo, contexto (módulo/tela/registro), pergunta, resposta JSON (resumo, evidências, fontes, limites, ações sugeridas), ferramentas usadas |

**Gatilhos comerciais:** oportunidade criada · movida de etapa · ganha · perdida · campo personalizado alterado · sem interação por período · atividade atrasada · data de fechamento próxima · reunião encerrada.
**Gatilhos financeiros:** recebível confirmado · vencimento próximo · título vencido · recebimento parcial · recebimento total · pagamento próximo · recorrência a gerar · recorrência a renovar · campo personalizado alterado · saldo projetado abaixo do limite.
**Variáveis de modelo:** `{{empresa.nome}} {{contato.nome}} {{oportunidade.titulo}} {{titulo.valor}} {{titulo.vencimento}}` + campos personalizados do objeto.

---

## 2. Telas

### Comercial
- **COM-01 Hoje** — saudação ("Boa tarde, {nome}. Seu próximo movimento começa aqui."), *Acesso rápido* (+Oportunidade, +Atividade, +Proposta, +Empresa, +Criar funil), **Leitura do momento** (insight priorizado com botão "Entender e agir"), KPIs: Pipeline aberto (n oportunidades ativas) · Em negociação · Tarefas do dia · Recebíveis vinculados ("Vendas ≠ recebimentos"). Painéis: *O que merece sua atenção* (atividades com Concluir), *Do negócio ao recebimento* (Oportunidade → Condição comercial → Recebível em rascunho → Recebimento), *Agenda conectada* (atividades do dia; "Prévia • sem conexão" se agenda não conectada), *Saúde da operação* (barra do funil por etapa).
- **COM-02 Oportunidades** — seletor de funil, +Criar funil, Configurar etapas (probabilidade, limite de dias, critérios), Kanban por etapa (contagem, "% · limite de N dias"), card (tag interesse, título, empresa, valor, responsável · próxima ação), drawer do registro: valor, interesse, troca de etapa (inclui Ganha/Perdida), **Contexto da negociação (IA)** com fonte, Analisar registro, Marcar como ganha, Histórico compartilhado, bloco Gestão (funil, contato, MRR, previsão, próxima ação, Atualizar). Painel Resultados do funil (ganhos/perdidos). Nova oportunidade: título*, funil*, empresa (selecionar **ou criar**), responsável*, contato, valor único, MRR, previsão, próxima ação + prazo, interesse, *Qualificação e estratégia* (origem, necessidade, decisor, orçamento/concorrente, critério de sucesso). Nasce na 1ª etapa.
  - **Revisar fechamento (ganho):** empresa*, valor acordado*, condição (parcela única / 2 parcelas iguais / … ), 1º vencimento* → "O fechamento prepara recebíveis em rascunho. Não registra pagamento nem movimenta o caixa." → leva a Financeiro › A receber.
  - **Perda:** motivo obrigatório (+ concorrente, data de retomada).
- **COM-03 Atividades** — filtros por tipo (Tarefa, E-mail, Ligação, WhatsApp, Reunião) e status, tabela (atividade+empresa, tipo, responsável, prazo, status, Editar/Concluir). Form: assunto*, tipo*, responsável*, empresa, oportunidade, prazo*, horário, horário final (reunião), fuso, participantes, canal, objetivo, resultado. Painel "Agenda e sincronização" → Integrações.
- **COM-04 Comunicações** — Conversas vinculadas (canal, assunto, data, Analisar); Importar conteúdo (canal + texto colado). **Análise com evidências**: necessidade declarada, objeção, compromisso identificado, citação literal + fonte; "Criar tarefa sugerida" e "Preparar resposta" (rascunho, sem envio). Sem transcrição de áudio nem análise de emoções.
- **COM-05 Propostas** — CRUD + "Ver documento" (prévia: escopo, qtd × unitário, desconto, total, mensalidade, condição, validade, status). Versão incrementa ao duplicar.
- **COM-06 Metas e forecast** — CRUD de metas + painel Forecast: pipeline único aberto, valor ponderado, MRR potencial, sem previsão de fechamento. Apuração da meta vs realizado no período.
- **COM-07 Desempenho** — período; KPIs conversão, receita ganha, ticket médio, ciclo mediano; tabela por vendedor (ganhas/encerradas, conversão, receita, sem próxima ação, Ver evidências → gargalo + ação sugerida + "Criar ação de desenvolvimento"). *Critérios transparentes* com fórmulas. Sem ranking.
- **COM-08 Dashboards** — KPIs (pipeline alto interesse via campo custom, oportunidades, recebíveis, próximas ações), gráfico Pipeline por etapa, "+ Configurar indicador" (objeto, métrica, filtro de campo custom, Calcular prévia).
- **COM-09 Empresas e clientes / Pessoas e contatos / Produtos e serviços / Playbooks / Modelos de comunicação** — listas com filtro, Exportar CSV, form no drawer. Empresa: contagem de oportunidades e recebíveis + "Novo contato".
- **COM-10 Gestão comercial** — página de referência (fluxo ponta a ponta + catálogo de campos) com botão "Configurar automações da área".

### Financeiro
- **FIN-01 Hoje** — "Sua operação financeira, em um só lugar." KPIs: saldo gerencial, recebíveis vencidos, aprovações pendentes, recorrências ativas. *Fila de cobrança* (vencidos) e *Comandos da gestão financeira*. Acesso rápido: +A receber, +A pagar, Registrar baixa, +Cobrança, +Transferência.
- **FIN-02 A receber / A pagar** — chips de estado (Todos, Aberto, Rascunho, Parcial, Liquidado, Cancelado, Vencido), tabela (empresa/descrição, valor original, saldo aberto, vencimento, estado [+aprovação no pagar], Abrir). Drawer: dados + origem ("Oportunidade #n" com link), Editar, Confirmar título (rascunho), Registrar recebimento/pagamento, Cancelar título, Histórico de baixas, Perguntar à IA. Form título: cliente/fornecedor*, descrição*, documento, emissão, competência, vencimento*, valor*, categoria, centro de custo, conta prevista, forma, responsável*, observações (+ aprovação no pagar).
- **FIN-03 Cobranças e acordos** — CRUD ligado a título a receber.
- **FIN-04 Recorrências** — CRUD + "Gerar competência" (mês) → título em rascunho. Futuro: geração automática pelo worker (gatilho "recorrência a gerar").
- **FIN-05 Caixa** — KPIs saldo gerencial (inicial + baixas + transferências), entradas abertas, saídas abertas, saldo após títulos; tabela por conta (saldo inicial, data-base, saldo atual); Transferir entre contas. Texto de limites ("Sem conciliação bancária…").
- **FIN-06 Aprovações** — contas a pagar pendentes (Conferir, Aprovar). Alçada por perfil (Gestor aprova). Também lista propostas com desconto em aprovação.
- **FIN-07 Baixas e estornos** — trilha (data, contraparte, recebimento/pagamento, valor, conta, situação, Estornar com motivo).
- **FIN-08 Transferências** — lista + nova.
- **FIN-09 Dashboards** — Caixa + Aging (a vencer / vencidos; evoluir para faixas 1–30, 31–60, 61–90, 90+).
- **FIN-10 Fornecedores / Categorias / Centros de custo / Contas financeiras / Gestão financeira** — CRUDs + página de referência.

### Núcleo
- **NUC-01 Cadastros mestres** — abas Empresas, Pessoas, Produtos e serviços; registro único com relacionamentos (n oportunidades, n recebíveis).
- **NUC-02 Campos personalizados** — catálogo (campo · tipo · objeto, usos, Inspecionar dependências). Regras: exigir por etapa/ação; antes de arquivar, verificar dependências.
- **NUC-03 Automações** — alternar área (Comercial/Financeiro; "Motor compartilhado · configurações independentes"); abas Modelos / Minhas automações / Histórico. Modelos prontos (ver lista abaixo). Editor: nome, gatilho, funil, etapa destino, campo/condição, operador, valor, prazo (dias), ação, tipo de atividade, responsável, destinatário, modelo/instrução com variáveis, checkbox "Revisar condições antes de executar e impedir duplicação". Testar (prévia de elegibilidade sem executar), Ativar/Pausar (envio exige canal conectado). Motor real: execução idempotente, retentativas limitadas, prevenção de ciclos, histórico.
- **NUC-04 Integrações** — cards Google Calendar, Microsoft Outlook, E-mail (SMTP/IMAP), WhatsApp: estado, requisitos (conta, escopos, responsável, retenção, fluxos dependentes), conectar/testar/reconectar/revogar, último erro.
- **NUC-05 Administração** — cards: Usuários e perfis · Configuração da IA · Categorias e contas · Auditoria · Qualidade dos dados (duplicidades + mesclagem revisada preservando vínculos) · Plano e consumo (uso de IA).
- **NUC-06 Histórico de ações** — auditoria (data, ação, registro, autor) com filtros.
- **NUC-07 Arquitetura e escopo** — página informativa (link no rodapé da lateral).

### Assistente (em todos os módulos) — IA
- **IA-01 Tela Assistente**: "Uma conversa. Todos os contextos." / "O que você precisa decidir?" + atalhos: Analisar este módulo · Relacionar vendas e caixa · Priorizar minha semana.
- **IA-02 Drawer "Assistente de orquestração"** (botão ✧ IA unificada no topo e "✧ Perguntar à IA" em cada tela): escopo (Este registro / Este módulo / Toda a FlicSales), contexto atual, pergunta, resposta estruturada (título, análise, **Próxima ação sugerida**, bloco *fonte/evidência/limite*), *Assistentes e fontes consultadas* (expansível), botão "Criar tarefa após revisão".
- Ferramentas (somente leitura, filtradas pela permissão): oportunidades, atividades, comunicações, títulos/baixas/caixa, cadastros, desempenho. Ações (criar tarefa, preparar resposta) só por confirmação.

### Modelos de automação prontos
Comercial: Boas-vindas e primeiro contato · Follow-up de proposta (2 dias úteis) · Retomar negociação sem interação (5 dias) · Reunião de diagnóstico (Discovery) · Nutrição por e-mail (Interesse = Alto) · Mensagem de acompanhamento (WhatsApp) · Handoff de venda ganha · Revisão de perda.
Financeiro: Lembrete antes do vencimento (3 dias) · Cobrança após vencimento (2 dias; suspende ao receber/cancelar/contestar) · Tratar recebimento parcial · Preparar pagamento · Revisar renovação (30 dias antes) · Alerta de caixa (saldo projetado abaixo do limite) · Conferir recorrência.

---

## 3. Dados de demonstração (seed `app.seed`)
Usuários: Francine (Gestor), Marina e Lucas (Comercial), um Financeiro. Funil "Serviços B2B": Entrada 10%/2d · Discovery 25%/7d · Proposta 50%/10d · Negociação 75%/14d.
Oportunidades: Projeto de consultoria · Aurora Consultoria · R$ 24.000 · Negociação · Marina · Alto; Expansão de operação · Vértice Serviços · R$ 18.000 · Proposta · Lucas · Alto; Diagnóstico estratégico · Horizonte Gestão · R$ 12.000 · Discovery · Marina · Médio; Consultoria recorrente · Atlas Tecnologia · R$ 9.600 · Entrada · Lucas · Médio.
A receber: Ponto Norte (Consultoria • parcela 1/2, R$ 6.000, vencido); Estúdio Base (Mensalidade • novembro, R$ 4.800); Lume Serviços (Implantação • parcela única, R$ 8.500). A pagar: Espaço Compartilhado (Aluguel R$ 4.200, pendente de aprovação); Nuvem Digital (Serviços de tecnologia R$ 3.000, aprovado).
Conta operacional saldo inicial R$ 25.000. Categorias Serviços prestados (receita), Estrutura (despesa); centro de custo Operação (OP). Produto Consultoria estratégica R$ 24.000/projeto. Recorrência Estúdio Base R$ 4.800/mês. Campos personalizados: Interesse (lista, Oportunidade), Origem (lista, Empresa). Comunicações: Discovery Aurora (notas), Proposta Vértice (e-mail), Próximo encontro Horizonte (WhatsApp). Atividades: Confirmar escopo com Aurora, Retomar proposta da Vértice, Preparar discovery da Horizonte.
Datas relativas a "hoje" (não fixas em 07/11/2026).

## 4. Fora do escopo inicial (adiar, decisão do protótipo)
Captura automática de todos os canais; ERP fiscal / NF; Open Finance e execução bancária; comissões complexas; previsão estatística (exige histórico); transcrição de áudio; análise de emoções.
