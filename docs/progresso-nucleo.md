# Progresso — Núcleo

Agente: Núcleo · 10/11/2026 · escopo: `backend/app/modules/nucleo/`, `backend/tests/nucleo/`, `frontend/components/cadastros/`,
`frontend/lib/tipos-nucleo.ts`, páginas de cadastro (Comercial/Financeiro/Núcleo) e `components/flic/command-palette.tsx`.

## Estado
- `uv run python -m pytest -q` → **suíte toda verde** (56 testes novos em `tests/nucleo/`).
- `uv run python -m ruff check app tests` → limpo.
- `npm run lint` ✔ · `npx tsc --noEmit` ✔ · `npm run build` ✔.
- Nenhuma migração nova: os modelos de `nucleo/models.py` (migração `0001`) bastaram.
- Não houve teste no navegador com backend real (só testes de API, incluindo um com o seed de demonstração).

## API (`/api/nucleo`)
| Recurso | Rotas | Permissão |
|---|---|---|
| Empresas | `GET/POST /empresas` (q, papel, situacao=ativos\|inativos\|todos, pagina, por_pagina) · `GET/PATCH/DELETE /empresas/{id}` | `nucleo.cadastros` |
| Pessoas | `GET/POST /pessoas` (q, empresa_id, situacao) · `GET/PATCH/DELETE /pessoas/{id}` | `nucleo.cadastros` |
| Produtos | `GET/POST /produtos` (q, tipo, situacao) · `GET/PATCH/DELETE /produtos/{id}` | `nucleo.cadastros` |
| Fornecedores | `GET/POST /fornecedores` · `GET/PATCH/DELETE /fornecedores/{id}` | `financeiro.cadastros` |
| Categorias | `GET/POST /categorias` (natureza) · `GET/PATCH/DELETE /categorias/{id}` | `financeiro.cadastros` |
| Centros de custo | `GET/POST /centros-custo` · `GET/PATCH/DELETE /centros-custo/{id}` | `financeiro.cadastros` |
| Contas financeiras | `GET/POST /contas` · `GET/PATCH/DELETE /contas/{id}` | `financeiro.cadastros` |
| Campos personalizados | `GET/POST /campos` (objeto, arquivados) · `GET/PATCH /campos/{id}` · `GET /campos/{id}/dependencias` · `POST /campos/{id}/arquivar` `{confirmar}` · `POST /campos/{id}/restaurar` · `GET /campos/etapas` | `nucleo.campos` |
| Busca global | `GET /busca?q=` → `{termo, grupos:[{tipo, rotulo, itens:[{id, titulo, subtitulo, href}]}]}` | logado; cada grupo exige o `.ver` do recurso |
| Qualidade dos dados | `GET /duplicidades` · `POST /empresas/{id}/mesclar` `{duplicada_id}` | `nucleo.administracao` |

- `DELETE` **inativa** (nada é apagado); `PATCH {"ativo": true}` reativa. Update grava só o enviado. Texto vazio vira `null`.
- Auditoria em todo criar/alterar/inativar/arquivar/restaurar/mesclar (`empresa.*`, `pessoa.*`, `produto.*`, `categoria.*`,
  `centro_custo.*`, `conta_financeira.*`, `campo_custom.*`).
- Lista de empresas traz `oportunidades` (todas), `titulos_receber` (não cancelados) e `saldo_receber` (aberto/parcial) —
  leitura direta nos modelos do Comercial/Financeiro.
- Busca: empresas por nome sem acento/fantasia/documento; pessoas por nome/e-mail/empresa; oportunidades por título ou
  empresa (respeita "só meus registros"); títulos por descrição/documento/empresa. Máx. 5 por tipo. `href`:
  `/nucleo/cadastros?aba=empresas|pessoas&id=`, `/comercial/oportunidades?id=`, `/financeiro/receber|pagar?id=`.

## Serviços para outros módulos (`app/modules/nucleo/servico.py`, assinaturas estáveis)
- `obter_ou_criar_empresa(db, nome, *, responsavel_id=None, papeis=None) -> (Empresa, criada)` — empresa nascendo na
  oportunidade/título; nome igual (normalizado) devolve a existente e soma os papéis. Só `flush`.
- `validar_campos_custom(db, objeto, enviados, atuais=None, *, exigir_obrigatorios=True) -> dict` — **o Comercial deve
  usar para `oportunidade.campos_custom`** (tipos, opções de lista, obrigatórios; `None` apaga a chave; valor já gravado
  de campo arquivado pode ser reenviado). Levanta `RegraViolada` → 400.
- `dependencias_do_campo(db, campo)`, `preenchimentos(db, objeto)`, `referencias_a_empresa()`, `vinculos_da_empresa(db, id)`,
  `mesclar_empresas(db, destino=, origem=, hoje=)`.
- Regras puras em `app/modules/nucleo/regras.py` (o Núcleo não edita `app/domain/`): `validar_campos_custom`,
  `normalizar_valor`, `slug_de`, `encontrar_duplicidades`, `nome_comparavel`.

## Decisões
- **Mesclagem** descobre as FKs para `empresa.id` pelo `Base.metadata` (tabela nova de qualquer módulo entra sozinha);
  a que fica herda campos vazios, soma papéis e campos personalizados (os dela prevalecem); a outra é inativada com nota.
  Teste prova que a soma de vínculos é a mesma e que nada aponta mais para a duplicada.
- **Duplicidade**: mesmo documento (≥ 11 dígitos), mesma raiz de CNPJ, mesmo nome sem sufixos (Ltda, ME, S/A, EIRELI, Cia…)
  e pontuação, ou semelhança ≥ 0,88. Só empresas ativas.
- **Fornecedor** = empresa com papel fornecedor (decisão da Fundação). `POST /fornecedores` com `empresa_id` marca uma
  empresa existente como fornecedor (sem duplicar). "Contato" do formulário cria uma Pessoa vinculada (se ainda não existir).
  `email` do fornecedor = `email_financeiro` da empresa. Inativar fornecedor inativa a empresa (é o mesmo cadastro).
- **Contas**: "movimento" = baixa **não estornada** ou transferência (como no protótipo). Com movimento, saldo inicial e
  data-base não mudam ("Conta com movimentos: preserve saldo inicial e data-base."); nome/instituição/ativo mudam.
- **Campos**: `slug` gerado do nome e fixo (renomear não quebra valores gravados); tipo e objeto não mudam depois de criado;
  opção de lista em uso não pode sair. "Exigir na etapa" só para oportunidade. Dependências: indicador (`filtro_campo_id`),
  automação (`campo` = slug, `objeto.slug`, `campos_custom.slug`… ou variável `{{objeto.slug}}` no conteúdo), etapa que exige,
  e registros preenchidos (informativo). Ativas = indicador ativo, automação `ativa`, etapa. Arquivar com dependência ativa
  só com `confirmar: true` (auditado listando as dependências).
- **Qualidade dos dados** no painel de `/nucleo/cadastros` (visível com `nucleo.administracao.ver`); componente exportado
  `QualidadeDados` pode ir também para Administração.

## Frontend
- Telas: `/comercial/empresas`, `/financeiro/empresas` (mesma `TelaEmpresas`: oportunidades/a receber, Cadastro, Novo contato),
  `/comercial/pessoas`, `/comercial/produtos`, `/financeiro/fornecedores|categorias|centros-custo|contas`,
  `/nucleo/cadastros` (abas Empresas · Pessoas · Produtos e serviços + Qualidade dos dados), `/nucleo/campos` (catálogo,
  Inspecionar dependências, arquivar revisado, Regras recomendadas), `/nucleo/arquitetura` (conteúdo de `architecture`).
  Todas abrem o registro com `?id=` (links da busca global).
- Busca global: a paleta (Enter na busca do topo, Ctrl/⌘+K) mostra empresas, pessoas, oportunidades e títulos de
  `GET /nucleo/busca` antes das telas.
- **Componentes exportados** em `@/components/cadastros` (props no topo de cada arquivo): `SeletorEmpresa` (selecionar ou
  criar; `papeisAoCriar`, `papel`), `CamposPersonalizados` (+ `useCamposDoObjeto`, `formatarValorCampo`),
  `SeletorResponsavel/Categoria/CentroCusto/Conta/Produto/Pessoa`, `DrawerEmpresa/Pessoa/Produto/Fornecedor/Categoria/
  CentroCusto/Conta`, `DrawerDependencias`, `ChipsPapeis`, `QualidadeDados`, telas inteiras e utilitários
  (`paraEnvio`, `alterados`, `useIdDaUrl`…).

## Pedidos ao coordenador / outros módulos
1. **Comercial**: validar `oportunidade.campos_custom` com `servico.validar_campos_custom(db, "oportunidade", ...)`; usar
   `obter_ou_criar_empresa` (ou o `SeletorEmpresa`) na Nova oportunidade; respeitar `campo_custom.exigido_na_etapa_id`
   ao mover etapa (campo arquivado não exige). Abrir `/comercial/oportunidades?id=` (link da busca).
2. **Financeiro**: abrir `/financeiro/receber?id=` e `/financeiro/pagar?id=` (links da busca); usar `SeletorEmpresa`
   (`papeisAoCriar={["cliente"]}` / `["fornecedor"]`), `SeletorCategoria`, `SeletorCentroCusto`, `SeletorConta`.
   Os cadastros de categorias/centros/contas/fornecedores ficaram em `/api/nucleo/...` (pedido do coordenador), não em
   `/api/financeiro/...`.
3. **Orquestração**: para as dependências de campo serem achadas, grave em `automacao.campo` o slug do campo (ou
   `objeto.slug`) e use variáveis `{{objeto.slug}}` no conteúdo.
4. **Fundação (frontend)**: em `app/(app)/nucleo/historico/page.tsx`, incluir no filtro as entidades `categoria`,
   `centro_custo`, `conta_financeira` e `campo_custom`; em Núcleo › Administração, o cartão "Qualidade dos dados" pode
   apontar para `/nucleo/cadastros` ou renderizar `<QualidadeDados/>`.

## Pendências
- Sem teste em navegador com backend real.
- Busca usa `ilike`/`contains` (sem índice de texto); suficiente para o volume inicial.
- Contagem de "registros preenchidos" de campos lê o JSON em Python (portável SQLite/Postgres); otimizar se crescer.
