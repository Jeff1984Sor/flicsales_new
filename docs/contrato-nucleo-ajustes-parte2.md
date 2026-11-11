# Contrato — Ajustes do Núcleo, parte 2 ("Módulo Núcleo_11.2026_parte 2.docx", Jefferson, 11/11/2026)

Três frentes em paralelo: **backend**, **front-cadastros** (seções 1–4) e **front-admin** (seções 5–7). Migração única
nova `0006_nucleo_parte2` (revisa `0005_nucleo_ajustes`). Mudou o contrato → atualize aqui.
Autorização: este pacote pode mexer em `core/`, `comercial` (motivos de perda, modelos) e `nav.ts`/shell conforme abaixo.

## 1. Empresa
- Tirar **E-mail financeiro** do formulário de empresa e de fornecedor (coluna fica no banco; some da tela, do Enriquecer
  e da planilha-modelo; importação ainda aceita a coluna antiga sem erro).
- Drawer de **empresa** (ver/editar) mais largo: novo prop `largura?: "padrao" | "metade"` no `Drawer`
  (`metade` = `min(50vw)` com mínimo 640px; em tela < 1024px ocupa a largura toda). Empresa e fornecedor usam `metade`.
- Botão **"+ Empresa"** sempre **depois** de "Importar planilha" (regra para todas as listas: Importar à esquerda,
  ação primária por último).
- **Segmento** e **Porte** viram lista suspensa alimentada pela Governança de ajustes (seção 6); valor antigo fora da
  lista aparece como opção. O CNPJ continua preenchendo: se o texto vindo da Receita não existir na lista, a tela mostra
  o valor e oferece "Adicionar à lista" (só quem pode editar a governança).

## 2. Pessoas
- Lista de pessoas ganha coluna **Cargo**.
- **Vários telefones e vários e-mails**:
  - backend: `pessoa.telefones` JSON `[{"numero": "...", "tipo": "celular|whatsapp|fixo|comercial", "principal": bool}]`
    e `pessoa.emails` JSON `[{"email": "...", "tipo": "comercial|pessoal|financeiro", "principal": bool}]`, default [].
    Exatamente um `principal` quando a lista não for vazia (domínio puro: se nenhum, o primeiro vira principal; mais de
    um → 400). E-mail validado e sem repetição; telefone normalizado.
    `pessoa.email`/`pessoa.telefone` continuam e passam a espelhar o **principal** (busca, IA, planilha e telas antigas
    seguem funcionando). Migração copia email/telefone existentes para as listas.
  - planilha de pessoas: colunas "E-mails adicionais" e "Telefones adicionais" (separados por `;`).
  - front: no drawer, listas com "+ Adicionar telefone" / "+ Adicionar e-mail", tipo e marcador de principal.

## 3. Produtos e serviços
- **Desconto**: `produto.desconto_tipo` `percentual|valor` null, `produto.desconto_valor` Numeric(15,2) null.
  Regras: percentual 0–100; valor ≥ 0 e ≤ preço de referência (se houver); tipo sem valor ou valor sem tipo → 400.
- **Recorrência** (quando `recorrente=true`): `produto.frequencia` `diaria|semanal|mensal|semestral|anual`,
  `produto.intervalo` int ≥ 1 (a cada N dias/semanas/meses/anos; semestral fixo 1), `produto.dias_semana` JSON lista de
  `seg|ter|qua|qui|sex|sab|dom` (obrigatório ≥ 1 quando semanal; vazio nos outros). `recorrente=false` limpa os três.
  Texto pronto para exibir: função pura `descrever_recorrencia` ("Toda semana: seg, qua", "A cada 2 meses",
  "Todo dia", "Semestral", "A cada 3 anos") devolvida na saída como `recorrencia_texto`.
- Planilha de produtos e o Enriquecer da IA cobrem os campos novos (IA não sugere desconto).
- Produtos e serviços **sai de Cadastros mestres** e vai para a Governança de ajustes (seção 6). Rotas não mudam.

## 4. Campos de dados (antigo "Campos personalizados")
- Renomear menu, título e breadcrumb para **"Campos de dados"**. Tela com abas por objeto:
  **Oportunidades · Empresas · Contatos · Produtos e serviços** (objeto `produto` novo no CampoCustom; ajustar
  constraint, lista branca da IA, planilha e o drawer de produto para editar os valores).
- Cada aba tem três blocos (como a imagem do documento):
  1. **Campos personalizados** — ordem (arrastar), nome, tipo, obrigatoriedade, preferências (visível), criado em, ações.
  2. **Sugestão de campos** — modelos prontos com "+ Adicionar campo" (cria o campo personalizado já configurado).
     Catálogo em `app/domain/campos_sugeridos.py` por objeto, ex.: Contatos: Data de nascimento, LinkedIn, CPF,
     Departamento; Empresas: Inscrição estadual, Nº de funcionários, Faturamento anual, LinkedIn; Oportunidades:
     Concorrente, Fonte do lead, Data prevista de decisão; Produtos: SKU externo, NCM, Garantia. Sugestão já criada
     não aparece.
  3. **Campos padrões** — campos fixos do sistema daquele objeto (nome, tipo "Campo padrão", obrigatoriedade,
     visível no cadastro). Backend: tabela `campo_padrao_config` (objeto, campo, obrigatorio bool, visivel bool, ordem)
     + catálogo fixo em domínio com o que **pode** ser mudado (ex.: nome da empresa e da pessoa são sempre obrigatórios
     e visíveis — sem lápis). `GET /api/nucleo/campos/padroes?objeto=` e `PATCH /api/nucleo/campos/padroes/{objeto}/{campo}`.
     Os formulários respeitam (esconde o invisível; exige o obrigatório) e o backend valida o obrigatório.
- No cadastro do campo (objeto Oportunidade):
  - **Exigir no funil → etapa** (já existe).
  - **Exibir na etapa** (novo): funil + etapa a partir da qual o campo aparece. Backend `exibir_funil_id`,
    `exibir_etapa_id` (null = sempre). Regra: aparece nas oportunidades daquele funil quando a etapa atual tem ordem ≥
    a da etapa escolhida (etapa null = qualquer etapa daquele funil); em outro funil não aparece. Exigir numa etapa
    anterior à de exibir → 400.

## 5. Administração
- **"← Administração"** também em Usuários e perfis (layout de `/configuracoes`), como já existe em Identidade.
- Cards, nesta ordem: **Usuários e perfis · Identidade · Categorias e contas · Qualidade dos dados · Governança de
  ajustes** (novo). Saem **Configuração da IA** e **Plano e consumo** (vão para o módulo Assistente).
- **Identidade**: imagem da assinatura geral (`identidade.assinatura_imagem`, PNG/JPG até 1 MB;
  `POST/DELETE /api/config/identidade/assinatura-imagem`, `GET` para logados; `assinatura_imagem_url` na saída).
  E-mails que caem na assinatura padrão levam essa imagem (CID), como a do usuário.

## 6. Governança de ajustes (novo, `/nucleo/governanca`, permissão `nucleo.administracao`)
Tela com abas:
- **Segmentos** e **Portes** (listas da empresa) e **Motivos de perda** (usados ao perder oportunidade):
  backend tabela `opcao_lista` (id, tipo `segmento|porte|motivo_perda`, nome, ordem, ativo, Timestamped; único por
  tipo+nome). `GET /api/nucleo/listas/{tipo}` (livre para logados — alimenta selects),
  `POST/PATCH /api/nucleo/listas/{tipo}[/{id}]`, reordenar, inativar (nada se exclui). Seed: portes ME · EPP · Médio ·
  Grande; segmentos e motivos a partir dos valores já usados nos dados + exemplos do protótipo.
  Perder oportunidade: select dos motivos ativos + "Outro" (texto livre). `oportunidade.motivo_perda` continua texto.
  Rotas que o front usa (front-admin): `GET /api/nucleo/listas/{tipo}` → `[{id, tipo, nome, ordem, ativo, criado_em}]`
  só ativas, na ordem; `?incluir_inativos=true` → todas (tela de governança); `POST /api/nucleo/listas/{tipo}` `{nome}`;
  `PATCH /api/nucleo/listas/{tipo}/{id}` `{nome?, ativo?}`; `POST /api/nucleo/listas/{tipo}/reordenar` `{ids: [...]}`
  com **todos** os ids da lista (ativos e inativos) na ordem nova. Hook do front: `useOpcoesLista(tipo)`
  (`components/governanca/opcoes-lista.ts`); tipos em `lib/tipos-governanca.ts`.
- **Produtos e serviços**: a tela de produtos (mesmo componente) passa a morar aqui.
- **Modelos de e-mail**: os modelos de comunicação do Comercial, com nova **classificação**
  `comercial|financeiro|geral` (`modelo_comunicacao.classificacao`, default `comercial`). Comercial lista
  comercial+geral; Financeiro (cobranças) lista financeiro+geral; automações listam todos. A tela de modelos do Comercial
  continua existindo (mesmo componente, filtrado).

## 7. Assistente vira módulo
- Nova aba no topo **Assistente** (4º módulo, `/assistente`), com menu: **Assistente** (chat universal, escopo
  "Toda a FlicSales" por padrão, perguntas sobre Núcleo, Comercial e Financeiro) e grupo **ADMINISTRAÇÃO** com
  **Configurações de IA** (`/assistente/configuracoes` = tela atual de IA) e **Plano e consumo**
  (`/assistente/consumo` = tela atual de consumo). Permissão `orquestracao.ia`.
- Sai o item "Assistente" dos menus de Comercial, Financeiro e Núcleo (rotas antigas redirecionam para `/assistente`).
- Botão **"✧ Perguntar à IA"** do cabeçalho aparece **só** nas telas de Comercial e Financeiro (some no Núcleo,
  configurações e Assistente). O botão "✧ IA unificada" do topo continua.

## Anexo — o que o front-cadastros (seções 1–4) chama
- `GET /api/nucleo/campos/padroes?objeto=` → `[{campo, nome, tipo, fixo, obrigatorio, visivel, ordem}]`;
  `PATCH /api/nucleo/campos/padroes/{objeto}/{campo}` com `{visivel, obrigatorio}`. Chaves de `campo` = atributos da
  API (as de `domain/campos_padrao.py`). Sem a rota: tudo visível e opcional.
- `GET /api/nucleo/campos/sugestoes?objeto=` → `[{chave, nome, tipo, opcoes, descricao}]` (só as ainda não criadas).
  "+ Adicionar campo" usa o `POST /api/nucleo/campos` normal (`{nome, tipo, objeto, opcoes, obrigatorio:false}`).
  Sem a rota: catálogo local igual ao de `domain/campos_sugeridos.py`.
- `CampoSaida` ganha (opcionais no front): `exibir_funil_id`, `exibir_funil_nome`, `exibir_etapa_id`,
  `exibir_etapa_nome`, `visivel` (preferência; `PATCH {visivel}`), `criado_em`. Reordenar = `PATCH {ordem}` por campo
  (1, 2, 3…). `GET /nucleo/campos?objeto=produto` e `campos_custom` no produto (entrada e saída).
- Pessoa: envia `telefones`/`emails` (listas com um `principal`), não envia mais `email`/`telefone`.
- Produto: `desconto_tipo`, `desconto_valor` (string decimal), `frequencia`, `intervalo`, `dias_semana`,
  `recorrencia_texto` (saída). No cadastro novo só vão quando ligados.
- Segmento/Porte: `GET /api/nucleo/listas/{tipo}` (array) e "Adicionar à lista" = `POST /api/nucleo/listas/{tipo}` `{nome}`.

## Backend entregue (11/11/2026)
Migração `0006_nucleo_parte2` (revisa `0005_nucleo_ajustes`). Tudo abaixo bate com os anexos do front; diferenças e
extras estão marcados.
- **Pessoa**: `telefones` `[{numero, tipo, principal}]` e `emails` `[{email, tipo, principal}]` na entrada e na saída
  (principal sempre primeiro). Com a lista, o backend deriva `email`/`telefone` do principal (o front não precisa
  mandá-los); sem a lista, `email`/`telefone` trocam o principal (telas antigas, planilha, fornecedor). Erros 400:
  "Marque só um e-mail como principal.", "E-mail repetido: x.", "Telefone inválido: …", tipo inválido. Linha vazia é
  ignorada. Busca de pessoas também procura nos e-mails/telefones adicionais. Regras: `app/domain/contatos.py`.
- **Produto**: `desconto_tipo`, `desconto_valor` (string decimal), `frequencia`, `intervalo`, `dias_semana`,
  `campos_custom`, saída `recorrencia_texto`. Recorrente sem frequência = mensal a cada 1 (produtos recorrentes antigos
  foram migrados assim). Validação sobre o estado final (mudar o preço abaixo do desconto em valor → 400).
  Regras: `app/domain/produto.py`.
- **Campos de dados**: `GET /api/nucleo/campos/sugestoes?objeto=` (alias `/campos/sugeridos`) →
  `[{objeto, chave, nome, tipo, tipo_rotulo, descricao, opcoes}]`. Extra: `POST /api/nucleo/campos/sugeridos/{objeto}/{chave}`
  cria já configurado (o `POST /campos` normal também serve; slug = chave). `CampoSaida` ganhou `exibir_funil_id`,
  `exibir_funil_nome`, `exibir_etapa_id`, `exibir_etapa_nome`, `exibir_etapa_ordem`, `visivel` (coluna nova
  `campo_custom.visivel`, `PATCH {visivel}`), `criado_em`. `GET /campos/etapas` ganhou `ordem`. Tirar
  `exibir_funil_id` (null) limpa também a etapa. Comercial: `GET /comercial/oportunidades/opcoes` → cada campo traz
  `exibir_funil_id`, `exibir_etapa_id`, `exibir_etapa_ordem` (regra pura `app/domain/campos_exibicao.visivel_na_oportunidade`).
- **Campos padrões**: `GET /api/nucleo/campos/padroes?objeto=` (livre para logados; sem objeto = todos) →
  `[{objeto, campo, nome, tipo, tipo_rotulo:"Campo padrão", fixo, obrigatorio, visivel, ordem}]`;
  `PATCH /api/nucleo/campos/padroes/{objeto}/{campo}` `{obrigatorio?, visivel?, ordem?}` (nucleo.campos.editar).
  Fixo → 400; obrigatório invisível → 400. O servidor exige o obrigatório nos POST (todos) e PATCH (só os campos
  enviados) de empresa, pessoa, produto e oportunidade. Catálogo: `app/domain/campos_padrao.py`.
- **Listas**: como no §6 (`?incluir_inativos=true`, `POST …/reordenar {ids}`), mais `DELETE /api/nucleo/listas/{tipo}/{id}`
  = inativar. Tipo desconhecido → 404. Saída `{id, tipo, nome, ordem, ativo, criado_em}`. Renomear não altera os
  cadastros que já usam o texto antigo.
- **Modelos**: `classificacao` em `POST/PATCH/GET /api/comercial/modelos`; filtros `?classificacao=a,b` e
  `?contexto=comercial|financeiro|automacoes|todos`. A rota continua exigindo `comercial.recursos.ver` (o perfil
  Financeiro padrão não tem — se o Financeiro for listar modelos, peça a regra).
- **Identidade**: `assinatura_imagem_url` em `GET/PUT /api/config/identidade`; `POST/DELETE
  /api/config/identidade/assinatura-imagem` (configuracoes.editar), `GET` livre para logados.
- **E-mail financeiro**: fora da planilha-modelo de empresas e fornecedores e da lista branca da IA; a importação
  ainda aceita as colunas antigas ("E-mail financeiro", "E-mail" do fornecedor) e grava. Planilha de pessoas: colunas
  "E-mails adicionais"/"Telefones adicionais" (`;`); de produtos: Frequência, Intervalo, Dias da semana, Tipo de
  desconto, Desconto e os campos personalizados de produto.
- **Assistente**: `configurar_em` = `/assistente/configuracoes`; mensagens apontam "Assistente › Configurações de IA".
