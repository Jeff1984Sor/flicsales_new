# Progresso — Fundação Backend

Agente: Fundação-Backend · 10/11/2026 · escopo: `backend/` (sem `frontend/`, sem commit). Base: núcleo do MayaFit
(`Projetos/MayaFit/backend`, só copiado — nada foi alterado lá).

## Estado
- `uv run python -m pytest -q` → **221 testes verdes** (domínio 78; core: auth, tokens, recuperação, rate limit,
  segredos/auditoria, storage/links, config/usuários/perfis, permissões, cobertura de rotas; tenancy 23; seed + migração).
- `uv run python -m ruff check app tests` → limpo.
- `alembic upgrade head` num SQLite limpo → 37 tabelas, **zero diferença** contra os modelos (há teste disso).
- `uv run python -m app.seed` num banco limpo → cria; de novo → "já existia (nada duplicado)". Login `francine` testado.
- `uv run python -c "from app.main import app"` → ok.

## O que foi feito
1. **Core portado do MayaFit** (`app/core/*`): config, db (`SessaoDaOrganizacao`, `UtcDateTime`, `hoje()` no fuso
   America/Sao_Paulo), models, security (Argon2/JWT; saiu o hash do Django), segredos (Fernet + rotação), auth_service
   (login curto, bloqueio, refresh com rotação e detecção de reuso, recuperação por e-mail e por código no WhatsApp),
   audit (imutável, snapshot/diff), deps (`Ctx`, `ctx.auditar`, escopo), permissoes, perfis, escopo, email (outbox em dev),
   ia (OpenAI/Gemini plugável + `ligada()`), storage, links assinados, ratelimit, notificador, rotas
   (`auth`, `config`, `auditoria`, `public`, `arquivos`), `main.py` (descoberta automática de módulos), `worker.py`.
   Removido: escopo de professor, totem/app do aluno/wellhub, bloqueio por plano (`recursos_http`), usuário Suporte,
   hash do Django, `limpar_dados`.
2. **Multi-tenant (um banco por organização)** portado: `tenancy.py` (`Organizacao`, claim `org`, banco de controle `BANCO_CONTROLE`),
   `organizacao_http.py` (token → endereço/`X-Forwarded-Host`; conferência de Host), `app/controle/` mínimo
   (`organizacao`, `dominio`, `login` + migração própria `alembic_controle/0001`), catálogo de logins sincronizado
   (`sincronia.py`), provisionamento (`service.provisionar`, com convite ou link de **primeiro acesso**), CLI
   (`python -m app.controle.cli ativar|migrar|nova-organizacao|dominio|status|sincronizar-logins|listar`).
   Sem o banco de controle roda com um banco só (dev/testes). Testado de verdade com duas organizações (isolamento de
   dados/arquivos, login ambíguo, token de uma org na outra, slug forjado, host falso, org inativa, worker por org).
3. **Permissões**: catálogo com os 22 recursos de todos os módulos, ações `ver`/`editar` (`auditoria` só `ver`);
   recurso com ponto (`comercial.oportunidades.ver`: a ação é o último segmento). Mapa dos prefixos combinados
   (`/api/nucleo|comercial|financeiro|orquestracao/...`) já pronto; módulos refinam com `adicionar_regras` (valida contra o
   catálogo). Perfis padrão: Gestor (administrador, não excluível), Comercial, Financeiro, Somente leitura. Opção de perfil
   `somente_meus_registros` (`ctx.filtrar_meus`, `ctx.pode_acessar`).
4. **Modelos** (todos da seção 1 da especificação) em `app/modules/{nucleo,comercial,financeiro,orquestracao}/models.py`,
   com FKs reais, `Numeric(15,2)`, `Date`, índices, CHECKs nomeados e as UNIQUEs: `titulo(origem_oportunidade_id, parcela)`,
   `titulo(origem_recorrencia_id, competencia)`, `automacao_execucao.chave_idempotencia`, `empresa.nome`/`nome_chave`,
   `etapa(funil_id, nome)`, `proposta(oportunidade_id, versao)`, `campo_custom(objeto, slug)`. Migração única
   `alembic/versions/0001_esquema_inicial.py` (autogenerate + revisão).
5. **Domínio** (`app/domain/`, puras, `RegraViolada` com as mensagens do protótipo): dinheiro, titulos, fechamento,
   caixa (25.000 + 19.300 − 7.200 = 37.100), recorrencia, funil, proposta, indicadores (8/24 = 33,3%; 160k/8 = 20k),
   atividade, cadastro, csv_seguro, leitura (Leitura do momento determinística). `RegraViolada` → HTTP 400 no `main.py`.
6. **Seed** `app/seed.py` com os dados da seção 3 (datas relativas a hoje; só a Ponto Norte nasce vencida).
7. `CLAUDE.md` › Contratos do core › **Backend** preenchido. `.env.example` do backend.

## Decisões tomadas (registrar/validar com o Jefferson)
- **Fornecedor** = `empresa` com `papel_fornecedor=True` + colunas `categoria_padrao_id` e `condicao_habitual` na própria
  empresa (sem tabela `fornecedor`). Financeiro › Fornecedores é uma visão filtrada; renomear vale em todo lugar.
- **Papéis da empresa** em 4 booleanos (`papel_prospect/cliente/fornecedor/parceiro`) em vez de JSON (filtro/índice iguais
  em SQLite e Postgres); `empresa.papeis` lê/escreve a lista.
- **Nome de empresa único** pela chave normalizada (`nome_chave`: minúsculo, sem acento, espaços colapsados), preenchida
  por evento do modelo — "Aurora Consultoria" e " aurora consultória" colidem no banco.
- **Título**: `parcela` (n) + `parcelas_total` (em vez de texto "n/total"), para a UNIQUE funcionar; `saldo` armazenado
  (CHECK 0 ≤ saldo ≤ valor_original); `confirmado_em`, `cancelado_em`, `aprovado_por_id/aprovado_em` acrescentados.
- **Baixa** com `registrada_por_id`; estorno guarda `estornada_por_id`/`estornada_em`/motivo (nunca DELETE).
- **Data da baixa**: a mensagem do protótipo citava "a posição da demonstração (07/11/2026)"; no produto virou
  "Data da baixa deve estar entre a data-base da conta e hoje".
- **Comercial e Financeiro editam cadastros compartilhados** (`nucleo.cadastros.editar`): as duas áreas têm
  Empresas/Pessoas/Fornecedores no menu e a empresa nasce dentro da oportunidade. O CLAUDE.md dizia "leitura de
  cadastros" — **ver Dúvidas**.
- **Alçada**: Financeiro vê Aprovações mas não aprova (`financeiro.aprovacoes.editar` só no Gestor).
- **Nada é excluído**: `DELETE` mapeia para `editar` (inativar/arquivar). Não existe ação `excluir` no catálogo.
- **Recorrência**: competência alinhada contando a partir do MÊS de início (trimestral iniciada em set/26 → set, dez, mar…).
- **Leitura do momento**: prioridade vencidos → sem próxima ação → além do limite da etapa → atividades atrasadas.

## Contratos de API do core (mudanças em relação ao MayaFit)
Iguais ao MayaFit: `/api/auth/{login,refresh,forgot,reset,forgot-codigo,reset-codigo,logout,trocar-senha,me,me/preferencias,me/foto,primeiro-acesso}`,
`/api/config/{usuarios,perfis,perfis/catalogo,perfis/{id}/duplicar,identidade,identidade/logo,email,email/testar,ia,ia/modelos}`,
`/api/auditoria`, `/api/public/{identidade,logo}`, `/api/arquivos/{caminho}`, `/api/arquivos-publicos/{token}`, `/api/health`.
Mudanças (o frontend já está alinhado):
- `UsuarioMe.estudio` → **`organizacao`** `{slug, nome, status}` (None com um banco só); saíram `mayacorp`, `teste_ate`, `recursos`.
- `somente_proprias_aulas` → **`somente_meus_registros`** (em `UsuarioMe`, `PerfilAcessoIn/Out`).
- `GET /api/auth/primeiro-acesso` devolve **`{organizacao, email}`** (era `{estudio, email}`).
- Claim do JWT `est` → **`org`**. Permissões `"<recurso>.<acao>"` com recurso pontuado; ações só `ver`/`editar`.
- Novo: `GET /api/config/usuarios/opcoes` → `[{id, nome, login}]` (livre para logados; para escolher responsável).
- Sem bloqueio por plano (403 "não está no seu plano") nem usuário Suporte.

## Preparação do hml
- **Nomes de banco configuráveis**: `BANCO_CONTROLE` (padrão `flicsalesos_controle`) e `BANCO_PREFIXO` (padrão
  `flicsalesos_`) no `.env` (`core/config.py`, validados: minúsculas, números e `_`). `tenancy.banco_controle()`
  substitui a constante `BANCO_CONTROLE`; `controle/service.nome_do_banco(slug)` = prefixo + slug (hífen → `_`).
  Evita colisão com o flicsales antigo (`flicsales_test`…) e deixa hml (`flicsalesos_controle_hml` /
  `flicsalesos_hml_`) e prod coexistirem. O nome gravado no controle de organizações já existentes não muda.
  No SQLite de dev o arquivo do controle passa a ser `data/flicsalesos_controle.db` (quem tinha
  `data/flicsales_controle.db` local: renomeie ou defina `BANCO_CONTROLE=flicsales_controle`).
  Testes: `tests/tenancy/test_nomes_de_banco.py`.
- **Seed por organização**: `python -m app.seed --organizacao <slug> [--forcar]` (`seed.popular_organizacao`) popula
  UMA organização do modo multi com os dados do protótipo e só os usuários de demo (francine/marina/lucas/fin, senha
  de demonstração). Qualquer ambiente; em prod recusa sem `--forcar`; idempotente; organização inexistente ou sem
  banco de controle → mensagem dizendo o que fazer. `python -m app.seed` sem argumento continua só dev.
  Testes: `tests/tenancy/test_seed_organizacao.py`.

## Pendências
- **Contrato da IA** (agente Orquestração): a Leitura determinística devolve `{titulo, analise, proxima_acao, evidencias,
  limites, acoes_sugeridas, origem}` (pedido da Fundação); o frontend (`lib/types.ts` › `RespostaIA`) espera
  `resumo, fontes[], ferramentas[], ia_ativa`. Unificar no `POST /api/orquestracao/ia/perguntar`.
- O frontend cita `pode("financeiro.baixas.estornar")` como exemplo; no catálogo estorno = `financeiro.baixas.editar`.
- Admin FlicSales (planos, cobrança, consumo de IA) e `uso` por organização: fora desta fase (fase 4).
- Postgres não foi testado aqui (só SQLite); a migração usa só tipos portáveis.
- Worker: nenhuma tarefa de negócio ainda (recorrências/automações ficam com os módulos).
- `StarletteDeprecationWarning` do `TestClient` (httpx) — inofensivo; trocar quando o FastAPI estabilizar `httpx2`.
