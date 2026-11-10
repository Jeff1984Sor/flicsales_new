# Progresso — Fundação Frontend

Agente: Fundação-Frontend · 10/11/2026 · escopo: `frontend/` (sem `backend/`, sem commit).

## Estado
- `npm run lint` ✔ sem erros · `npm run build` ✔ (Next 16.4.3 / Turbopack, 55 rotas) · `tsc --noEmit` ✔.
- Teste de fumaça com `next start` sem backend: `/login` 200; rota privada sem cookie → 307 `/login?volta=…`;
  `/bff/health` → 502 "Não foi possível falar com o servidor." (esperado sem API); `/bff/orquestracao/ia/perguntar` sem sessão → 401.

## O que foi feito
1. **Base portada do MayaFit** (sem `node_modules`/`.next`; o MayaFit não foi alterado): `package.json` (`flicsales-web`; saíram
   `@vladmandic/human`, `jsqr`, `qrcode`, `canvas-confetti` e tipos), configs (tsconfig, eslint, components.json,
   next.config com cabeçalhos de segurança, `.npmrc`), `proxy.ts` (telas públicas: login, esqueci/redefinir senha, primeiro
   acesso), BFF `app/bff/[...path]` (cookies `flicsales_access`/`flicsales_refresh`, `X-Requested-With: flicsales`),
   `app/(auth)/*` (login curto, esqueci/redefinir senha por código/link, primeiro acesso), `lib/` (api, auth, env, format,
   utils, validacao, brand, server/sessao, types), `components/ui/*`, `components/mayacorp/*` → **`components/flic/*`**,
   hooks. Removido tudo de estúdio/aluno/aula/totem/site/wellhub/admin, tour guiado e "fora do plano".
2. **Identidade visual** em `app/globals.css` (Tailwind 4 `@theme inline`): `ink`, `primary`, `electric`, `accent`, `bg`,
   `surface`, `muted` (texto), `line`, `amber`/`amber-ink`, `subtle`/`tint` (fundos suaves), `sidebar`, `success`, `danger`;
   tema escuro coerente (`.dark`). Inter + JetBrains Mono via `next/font`. Botões no padrão do protótipo
   (`default` = azul elétrico; `outline` = branco com borda fina). Foco visível turquesa.
3. **Shell** (`components/flic/shell.tsx`): topo 73px (logo `flic`**`sales`**`/ OS`, abas Comercial · Financeiro · Núcleo que
   lembram a última tela, busca global — `/` foca, Enter abre a paleta com o termo —, "✧ IA unificada", avatar com Minha
   conta / Configurações / Trocar senha / Tema / Sair); lateral escura 232px com `WORKSPACE / <MÓDULO>`, grupos, item ativo
   azul com marcador turquesa, rodapé "Um contexto. Próxima ação." + "● Ambiente de demonstração" (fora de prod) +
   "↗ Arquitetura e escopo"; breadcrumb `Workspace / Módulo / Tela` + data de hoje (fuso America/Sao_Paulo). Atalhos:
   Alt+N → evento `flic:novo`, `/` busca, Esc fecha o drawer do topo. Mobile: lateral vira faixa rolável (como no protótipo).
4. **Menu** `components/flic/nav.ts`: 3 módulos, grupos e itens exatamente como o CLAUDE.md, ícones lucide, `planejado`,
   `recurso` de permissão por item (o perfil precisa de `<recurso>.ver`); `TELAS_EXTRAS` (Arquitetura, Configurações, Minha conta).
5. **Páginas**: provisória `<EmConstrucao>` (título/subtítulo do protótipo) em todas as rotas combinadas; prontas de verdade:
   Assistente (3 módulos), Núcleo › Administração (cartões), Núcleo › Histórico de ações (auditoria portada), Configurações
   (usuários, perfis + editor, identidade, IA, e-mail) e Minha conta. `/` → primeira tela visível (Comercial › Hoje).
6. **Kit** (`components/flic/`, props no topo de cada arquivo): PageHeader, Metricas/KpiCard, Insight, Painel/GradePaineis,
   DataTable (+ SearchInput, Segmented, Pagination…), BarraFiltros (CSV `;` + BOM + anti-fórmula em `lib/csv.ts`), Drawer +
   CampoDrawer, Etiqueta, Passos, Kanban + CartaoKanban, Dinheiro, notificar/FlicToaster, AcessoRapido, Fonte, EmptyState,
   EmConstrucao, AssistenteDrawer, AssistentePagina, eventos (`useAtalhoNovo`, `abrirAssistente`, `abrirPaleta`).
7. `lib/format.ts`: `data()` formata data-de-dia **da string**; novos `competencia()`, `hojeISO()`, `hojeExtenso()`, `FUSO`.
8. CLAUDE.md › "Contratos do core" ganhou o bloco **Frontend** (rotas, kit, exemplo lista + drawer, api, tipos).

## Contratos do BFF esperados do backend (prefixo `/api`)
| Uso | Rota | Observação |
|---|---|---|
| Login | `POST /auth/login` `{identificador, senha}` → `TokenOut {access_token, refresh_token, usuario}` | BFF transforma tokens em cookies |
| Renovação | `POST /auth/refresh` `{refresh_token}` → par novo | só o servidor do Next chama |
| Sessão | `GET /auth/me` → `UsuarioMe` (`permissoes: ["<recurso>.<acao>"]`, `administrador`, `somente_meus_registros`, `organizacao`) | 401 sem sessão |
| Sair / senha | `POST /auth/logout`, `POST /auth/trocar-senha`, `POST /auth/forgot`, `/auth/forgot-codigo`, `/auth/reset`, `/auth/reset-codigo` | iguais ao MayaFit |
| Primeiro acesso | `GET /auth/primeiro-acesso?token=` → `{organizacao?, email}`; `POST /auth/primeiro-acesso` → `TokenOut` | **não achei no backend ainda** |
| Foto | `GET/POST/DELETE /auth/me/foto` | Minha conta |
| Configurações | `/config/usuarios[/{id}][/redefinir-senha|/definir-senha]`, `/config/perfis[/{id}][/duplicar]`, `/config/perfis/catalogo`, `/config/identidade[/logo]`, `/config/ia[/modelos]`, `/config/email[/testar]` | iguais ao MayaFit |
| Identidade pública | `GET /public/identidade` → `{nome_exibicao, logo_url, cor_destaque}` | cor substitui `--primary` |
| Auditoria | `GET /auditoria?pagina&por_pagina&q&entidade` → `Pagina<AuditoriaOut>` | Histórico de ações |
| Saúde | `GET /health` → `{versao}` | rodapé das telas públicas |
| IA | `POST /orquestracao/ia/perguntar` `PerguntaIA` → `RespostaIA` (lib/types.ts) | 404/503 tratados com mensagem amigável |

Permissões: o front checa `"<recurso>.ver"` com os recursos da lista combinada (confere com `backend/app/core/permissoes.py`).
Campo de escopo próprio alinhado ao backend: `somente_meus_registros`.

## Pendências / pedidos
- **IA** (agente ia-orquestrador): confirmar o contrato `PerguntaIA`/`RespostaIA` em `lib/types.ts` (escopo `registro|modulo|global`,
  `contexto {modulo, tela, rota, registro}`; resposta `resumo, proxima_acao, evidencias[], fontes[], limites[], acoes_sugeridas[],
  ferramentas[], ia_ativa`). Se mudar, ajustar `components/flic/assistente-drawer.tsx`. "Criar tarefa após revisão" ainda só avisa.
- **Backend**: `primeiro-acesso` (GET/POST) não existe no core ainda; a tela está pronta. Conferir se `/config/perfis/catalogo`
  e o editor de perfis aceitam `somente_meus_registros` (o editor envia esse campo).
- **Busca global**: a paleta só navega por telas; cada módulo pode acrescentar busca de registros (empresas, oportunidades…).
- Telas dos módulos: todas as rotas de Comercial, Financeiro e Núcleo (exceto Administração/Histórico/Assistente) são provisórias.
- `recharts` e `react-dropzone` continuam no `package.json` (gráficos dos dashboards; upload de logo/foto).
- Não houve teste no navegador com backend real (o backend estava em construção em paralelo).
