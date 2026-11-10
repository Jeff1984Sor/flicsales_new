# CLAUDE.md — FlicSales OS

> **Leia primeiro.** FlicSales OS é a plataforma de **orquestração comercial + financeira com IA unificada**.
> Lema do produto: **"Um contexto. Próxima ação."**
> Fonte da verdade do produto: o protótipo navegável em [`docs/prototipo/flicsales-prototipo.html`](docs/prototipo/flicsales-prototipo.html)
> (abra no navegador) e a especificação extraída dele em [`docs/ESPECIFICACAO.md`](docs/ESPECIFICACAO.md).
> **Este projeto NÃO é continuação do `Projetos/flicsales` antigo.** Não copie telas, modelos nem regras de lá.
> A stack e o jeito de trabalhar vêm do MayaFit/MayaJus (`Projetos/MayaFit`, `Projetos/MayacorpAutomacoes_CFME`).

| | |
|---|---|
| Código | `C:\Users\JeffersonFernandes\Projetos\flicsales_new` |
| Repositório | `https://github.com/Jeff1984Sor/flicsales_new.git` |
| Produção | ainda não existe. **Nesta fase tudo é local: só código, testes e build.** Nada de SSH/deploy sem pedido explícito do Jefferson. |
| Andamento | [`docs/PROGRESSO.md`](docs/PROGRESSO.md) + `docs/progresso-<modulo>.md` |

## O produto em uma tela

Três módulos de produto sobre **uma plataforma compartilhada**:

| Módulo | Grupos do menu (ordem do protótipo) |
|---|---|
| **Comercial** | TRABALHO: Hoje · Oportunidades · Atividades · Comunicações — GESTÃO: Propostas · Metas e forecast · Desempenho · Dashboards — CADASTROS E RECURSOS: Empresas e clientes · Pessoas e contatos · Produtos e serviços · Playbooks · Modelos de comunicação · Gestão comercial · Assistente |
| **Financeiro** | OPERAÇÃO: Hoje · A receber · A pagar · Cobranças e acordos · Recorrências · Caixa — CONTROLE: Aprovações · Baixas e estornos · Transferências · Dashboards — CADASTROS E RECURSOS: Empresas e clientes · Fornecedores · Categorias · Centros de custo · Contas financeiras · Gestão financeira · Assistente |
| **Núcleo** | PLATAFORMA: Cadastros mestres · Campos personalizados · Automações · Integrações · Administração · Histórico de ações · Assistente |

Topo: logo `flic`**`sales`**`/ OS`, abas dos 3 módulos, busca global (`/` foca), botão **✧ IA unificada**, avatar.
Lateral escura com rótulo `WORKSPACE / <MÓDULO>`. Detalhes e formulários abrem num **painel lateral (drawer)**, não em página nova.
Atalhos: `Alt+N` cria (oportunidade no Comercial, título no Financeiro), `/` busca, `Esc` fecha o drawer.

**Critério de aceite do primeiro produto (vira teste de ponta a ponta):**
criar empresa durante uma oportunidade → registrar próxima ação → fechar venda → revisar recebíveis em rascunho
sem duplicação → confirmar título → registrar recebimento parcial → conferir saldo de caixa e histórico.

## Regras de negócio que não se negociam

1. **Venda ≠ recebimento ≠ caixa.** Pipeline nunca compõe saldo. Ganhar uma oportunidade gera **recebíveis em RASCUNHO**
   (idempotente: ganhar de novo não duplica), que o financeiro revisa e confirma. Confirmar título não é baixa.
2. **Baixa** (recebimento/pagamento) é gerencial: valor > 0 e ≤ saldo aberto; data entre a data-base da conta e hoje;
   conta cadastrada. Parcial mantém saldo. **Nunca apagar baixa**: corrigir é **estornar** (com motivo; movimento preservado).
3. Título com baixa ativa **não** pode ter valor editado nem ser cancelado — estorne antes. Cancelar exige motivo.
4. Conta a pagar só recebe baixa se **aprovada** (Aprovações).
5. **Transferência** entre contas não é receita nem despesa; contas diferentes, valor > 0.
6. **Recorrência** gera título em rascunho por **competência**, sem duplicar, só dentro da vigência e compatível com a
   frequência (mensal/trimestral/anual); dia de vencimento 1–28.
7. Oportunidade **perdida exige motivo**; nada é excluído, só encerrado. Ganha não muda valor sem revisão financeira.
8. Proposta: quantidade > 0, desconto 0–100%, **desconto > 0 exige justificativa**; total = qtd × unitário × (1 − desc).
   "Aceita" não fecha a oportunidade sozinha.
9. Atividade do tipo Reunião exige início < fim no mesmo dia. **Criar atividade ≠ enviar mensagem**: envio só com conector autorizado.
10. Funil: ≥ 2 etapas únicas; "Ganha" e "Perdida" são resultados finais, não etapas. Probabilidade da etapa é parâmetro,
    não previsão de IA. Forecast ponderado = Σ valor × probabilidade da etapa.
11. Indicadores são **calculados em código** com fórmula visível (conversão = ganhas ÷ (ganhas+perdidas); ticket = receita ÷ vendas;
    ciclo = mediana de dias criação→ganho). A IA interpreta evidências, não inventa número. Sem ranking de pessoas.
12. Campos personalizados (texto, número, moeda, data, sim/não, lista) por objeto (Empresa, Pessoa, Oportunidade);
    antes de arquivar, mostrar dependências (dashboards, automações, formulários).
13. Empresa é **cadastro único** compartilhado pelos 3 módulos (nome basta para começar; pode nascer dentro da oportunidade).
    Renomear empresa atualiza todos os vínculos (é FK, não texto). Nome duplicado é recusado.

## IA unificada (camada única, não um agente por tela)

- Escopo explícito da conversa: **Este registro · Este módulo · Toda a FlicSales**. Contexto = módulo/tela/registro atual.
- Gateway em `app/core/ia.py` (provedor plugável, chave cifrada, configurado na tela). Ferramentas de leitura por domínio
  respeitam **as permissões do usuário** — a IA nunca amplia acesso.
- Toda resposta traz **evidência, fonte e limite** ("o que não se sabe"). Texto importado (e-mail, notas, WhatsApp) é
  **dado, nunca instrução**. Ações sugeridas nascem **propostas** e só viram registro após o clique do usuário.
- **Sem IA configurada o produto continua útil**: a "Leitura do momento" e as prioridades do Hoje são calculadas por regras
  determinísticas em `app/domain/` e a tela diz que a IA está desligada.

## Stack (igual à do MayaJus/MayaFit)

- `backend/`: FastAPI + SQLAlchemy 2 + Pydantic v2 + Alembic, Python 3.12, gerenciado com `uv`. Rode com
  `uv run python -m ...` (os `.exe` do venv são bloqueados no Windows desta máquina; `uv run python -m pytest` funciona).
- `frontend/`: Next.js (App Router) + TypeScript strict + Tailwind 4 + shadcn/ui + TanStack Query + Zod + lucide-react.
  **Leia `frontend/AGENTS.md`**: a versão do Next tem mudanças; consulte `node_modules/next/dist/docs/`.
- Banco: PostgreSQL (hml/prod), SQLite em dev/testes. Fila e tarefas periódicas no worker (`app.worker`).
- **Multi-tenant: um banco por organização** (padrão MayaFit, `app/core/tenancy.py`), "liga sozinho": sem banco de
  controle roda com um banco só (dev e testes). Módulos **não** têm `tenant_id`.
- Navegador só fala com `/bff/*` (Next); tokens em cookies httpOnly.

## Visual (identidade do protótipo)

Tokens CSS (nunca hex solto em componente): `--ink #0B1020` (texto e lateral), `--primary #0057D9` (ação/ativo),
`--electric #0A84FF` (destaques/gráficos), `--accent #00D1C1` (IA e marcador do item ativo), `--bg #F5F8FF`,
`--muted #596579`, `--line #A8B0BD55`, `--amber` (vencido/atenção). Fonte Inter; números em JetBrains Mono.
Tema escuro via variáveis. Cards brancos com borda fina e raio 10px; eyebrows em caixa alta espaçada.
Padrões de tela: cabeçalho (título + subtítulo + "✧ Perguntar à IA" + ação primária) → barra de filtros (busca, chips de
estado, Exportar CSV) → tabela → vazio ilustrado → drawer de detalhe/form → toast.
Textos da UI em PT-BR, curtos, no tom do protótipo ("Seu dia, em perspectiva.", "Da conversa à ação.").

## Decisões já tomadas

1. Dinheiro sempre `Decimal`/`Numeric(15,2)`; arredondamento bancário só onde a regra pedir. Datas de negócio `Date`;
   instantes `UtcDateTime`; fuso de negócio `America/Sao_Paulo`. Datas-de-dia no front: formatar da string, nunca `new Date()`.
2. **Regras de negócio em `backend/app/domain/` como funções puras com testes.** Rota só orquestra.
3. Segurança por padrão: toda rota exige login; rota pública em lista explícita; permissão negada por padrão
   (`tests/test_cobertura_rotas.py` falha se rota ficar sem regra).
4. Perfis padrão: **Gestor** (tudo), **Comercial** (módulo Comercial + leitura de cadastros), **Financeiro** (módulo
   Financeiro + leitura de cadastros), **Somente leitura**. Escopo "só meus registros" para Comercial é opção do perfil.
5. Credenciais e integrações (IA, SMTP, WhatsApp, Google/Outlook) são cadastradas **na tela**, cifradas, somente escrita
   (mostra "configurado" + 4 últimos caracteres), com "Testar conexão". `.env` só tem DATABASE_URL, JWT, MASTER_KEY, AMBIENTE.
6. **Auditoria automática** de toda criação/alteração/estorno/cancelamento (autor, data, entidade, antes→depois) →
   tela "Histórico de ações".
7. Update grava só o que a tela enviou (`model_dump(exclude_unset=True)`).
8. Exportar CSV: `;`, BOM UTF-8, e células que começam com `= + - @` são neutralizadas (injeção de fórmula).

## Como trabalhar (agentes e humanos)

- Agentes do projeto em `.claude/agents/` — veja a tabela em [`docs/AGENTES.md`](docs/AGENTES.md). Skills em `.claude/skills/`.
- Branch `develop` = integração; `main` = estável. Trabalho em `feat/<assunto>`. **Nunca** force-push em `main`/`develop`.
- Commits pequenos, em português, dizendo o que muda e por quê.
- Cada módulo é dono de `backend/app/modules/<modulo>/`, `backend/tests/<modulo>/`, `frontend/app/(app)/<area>/`,
  `frontend/components/<area>/` e `frontend/lib/tipos-<area>.ts`. **Não edite arquivo de outro módulo nem `core/`** —
  peça por escrito em `docs/progresso-<modulo>.md`.
- Serviços que outros módulos chamam ficam em `modules/<modulo>/servico.py`, com assinatura estável e testada.
- Antes de dar algo como pronto: `cd backend && uv run python -m pytest -q` verde; `cd frontend && npm run lint && npm run build` sem erro.
- Não commitar `.env`, bancos, `storage/`, `node_modules`.

## Comandos

```bash
cd backend
uv sync
uv run python -m pytest -q
uv run python -m alembic upgrade head
uv run python -m app.seed            # organização demo com os dados do protótipo
uv run python -m uvicorn app.main:app --reload --port 8000
cd ../frontend && npm install && npm run dev   # http://localhost:3000
```

## Contratos do core para quem cria módulos

<!-- O agente Fundação preenche esta seção ao terminar: tabelas do core, como registrar rotas/permissões/auditoria,
     componentes de tela reutilizáveis (DataTable, Drawer, PageHeader, KpiCard...), como chamar a IA. -->

### Backend (fundação do `backend/`)

**Demo:** `uv run python -m app.seed` (aplica migrations e semeia; idempotente; só `AMBIENTE=dev`). Logins `francine`
(Gestor), `marina` e `lucas` (Comercial), `fin` (Financeiro) — **senha de demonstração `Flic@2026`** (ou `SEED_SENHA`).
Ninguém entra com e-mail: só o login curto.

**Tabelas do core** (nomes fixos, módulos fazem FK para elas): `usuario` (login, nome, email, perfil_acesso_id, ativo),
`perfil_acesso` (permissoes JSON, administrador, somente_meus_registros), `auditoria` (só INSERT), `identidade`,
`config_email`, `config_ia`, `refresh_token`, `recuperacao_senha`, `rate_limit_evento`. Todos os modelos de negócio da
especificação já existem em `app/modules/<modulo>/models.py` (migração única `0001`); **mudou modelo → migração nova**.
Dinheiro: `from app.modules.base import Dinheiro` (`Numeric(15,2)`). Instantes: `UtcDateTime`; datas de negócio `Date`;
"hoje" de negócio: `app.core.db.hoje()` (America/Sao_Paulo) — passe-o ao domínio, que nunca lê relógio.
Fornecedor = `empresa` com `papel_fornecedor=True` (+ `categoria_padrao_id`, `condicao_habitual`); papéis em booleanos
`papel_prospect/cliente/fornecedor/parceiro` (propriedade `empresa.papeis`); `empresa.nome_chave` (UNIQUE) é preenchida
sozinha. Sem `tenant_id`: um banco por organização (`app/core/tenancy.py`, liga sozinho com o banco `flicsales_controle`).

**Rotas.** Crie `app/modules/<modulo>/routes.py` com `router = APIRouter(prefix="/<modulo>", tags=[...])` — o `main.py`
descobre sozinho e monta em `/api` exigindo login. Prefixos: `/api/nucleo`, `/api/comercial`, `/api/financeiro`,
`/api/orquestracao`. Webhook sem login: `router_publico` sob `/api/webhooks/...`. Use `ctx: Ctx` (`from app.core.deps import Ctx`)
→ `ctx.db`, `ctx.usuario`, `ctx.exigir("financeiro.aprovacoes.editar")`, `ctx.filtrar_meus(select(...), Modelo.responsavel_id)`,
`ctx.pode_acessar(responsavel_id)` (escopo "só meus registros": responda 404). Usuários para escolher responsável:
`GET /api/config/usuarios/opcoes` (livre para logados).

**Permissões.** Catálogo completo em `app/core/permissoes.py` (não edite): `nucleo.cadastros|campos|administracao`,
`auditoria`, `configuracoes`, `comercial.oportunidades|atividades|comunicacoes|propostas|metas|desempenho|recursos`,
`financeiro.titulos|baixas|aprovacoes|caixa|cobrancas|recorrencias|cadastros`, `orquestracao.ia|automacoes|integracoes`;
ações **`ver` e `editar`** (permissão = `"<recurso>.<acao>"`; DELETE conta como `editar`, nada se exclui). O core já mapeia
os prefixos combinados (ex.: `/comercial/oportunidades*` → `comercial.oportunidades.*`, `/financeiro/titulos/{id}/baixas`
→ `financeiro.baixas.*`, `/financeiro/titulos/{id}/aprovar` → `financeiro.aprovacoes.editar`). Rota fora desses padrões:
no topo do `routes.py` chame `adicionar_regras([("POST", r"/comercial/oportunidades/\d+/ganhar$", "comercial.oportunidades.editar")])`
(regex SEM `/api`; entra antes das padrão; permissão fora do catálogo dá `ValueError`). `tests/test_cobertura_rotas.py`
quebra se alguma rota ficar sem regra. Perfis padrão: Gestor (tudo), Comercial, Financeiro (sem aprovar), Somente leitura.

**Regras e erros.** Regra de negócio em `app/domain/` (puras, testadas): `dinheiro`, `titulos`, `fechamento`, `caixa`,
`recorrencia`, `funil`, `proposta`, `indicadores`, `atividade`, `cadastro`, `csv_seguro`, `leitura`. Violação →
`raise RegraViolada("mensagem PT-BR")` (`from app.domain import RegraViolada`); o handler global devolve **HTTP 400
`{"detail": mensagem}`** — a rota não precisa de try/except. 422 de validação vem traduzido (`detail` + `erros`).

**Auditoria.** Toda criação/alteração/estorno/cancelamento: `ctx.auditar("titulo.cancelar", "titulo", t.id,
descricao=motivo, antes=a, depois=d)` antes do `ctx.db.commit()`; para o diff use
`antes = audit.snapshot(obj)` → altere → `a, d = audit.diff(antes, audit.snapshot(obj))` (`from app.core import audit`).
Update grava só o enviado: `dados.model_dump(exclude_unset=True)`.

**IA.** `from app.core import ia` → `ia.ligada(db)`; `p = ia.provedor_ativo(db)` e `ia.gerar_json(p, sistema, usuario)`
(levantam `ia.IAIndisponivel` com mensagem pronta). Sem IA, use `app.domain.leitura.ler_momento(...)`, que devolve o
mesmo formato `{titulo, analise, proxima_acao, evidencias[], limites[], acoes_sugeridas[], origem}`. Texto importado é dado.

**Worker.** `app/modules/<modulo>/tarefas.py` chamando `from app.worker import registrar_tarefa` →
`registrar_tarefa("nome", intervalo_s, fn)` (roda uma vez por organização ativa).

**Testes.** `tests/<modulo>/` usando as fixtures de `tests/conftest.py` (`client`, `db`, `admin`, `token_admin`,
`criar_usuario(db, "Comercial", email=...)`, `entrar(client, login)`, `auth(token)`, `emails`). Seed de dados de exemplo
em teste: `seed.semear(db, hoje)`.

### Frontend (fundação do `frontend/`)

**Rotas e onde criar páginas.** Telas logadas em `frontend/app/(app)/<area>/...` (o layout do grupo põe o shell e exige
sessão); telas públicas em `app/(auth)/` (login, esqueci/redefinir senha, primeiro acesso). `/` leva a `/comercial`.
Rotas do menu (cada uma já tem página provisória `<EmConstrucao>` — **substitua o arquivo inteiro** ao implementar):
- Comercial: `/comercial` (Hoje), `oportunidades`, `atividades`, `comunicacoes`, `propostas`, `metas`, `desempenho`,
  `dashboards`, `empresas`, `pessoas`, `produtos`, `playbooks`, `modelos`, `gestao`, `assistente`
- Financeiro: `/financeiro` (Hoje), `receber`, `pagar`, `cobrancas`, `recorrencias`, `caixa`, `aprovacoes`, `baixas`,
  `transferencias`, `dashboards`, `empresas`, `fornecedores`, `categorias`, `centros-custo`, `contas`, `gestao`, `assistente`
- Núcleo: `/nucleo/cadastros`, `campos`, `automacoes`, `integracoes`, `administracao` (cartões prontos), `historico`
  (auditoria pronta, `GET /auditoria`), `assistente`, `arquitetura` (link do rodapé da lateral)
- Core: `/configuracoes/{usuarios,perfis,identidade,ia,email}` (portadas do MayaFit, abrem pelo avatar) e `/minha-conta`.

**Menu e permissão.** `components/flic/nav.ts` (`MODULOS` → grupos → itens; `TELAS_EXTRAS` para telas fora da lateral).
Cada item tem `recurso` (ex.: `comercial.oportunidades`); o item aparece e a página abre se o perfil tiver
`"<recurso>.ver"` (`useAuth().podeVer(recurso)`; ação específica: `pode("financeiro.baixas.editar")`). Administrador
vê tudo. Sem permissão, o shell troca a página por `<SemAcesso/>` — o servidor recusa os dados de qualquer forma.
Cada módulo altera **só as suas linhas** do `nav.ts`.

**Kit de telas (`components/flic/`, props documentadas no topo de cada arquivo).** `PageHeader` (título, subtítulo,
"✧ Perguntar à IA", slot `acao`) · `Metricas` + `KpiCard` (grade de 4, valor 29px mono, `formula` visível) · `Insight`
("LEITURA DO MOMENTO") · `Painel` + `GradePaineis` · `DataTable<T>` (colunas tipadas, vazio, paginação) · `BarraFiltros`
(busca, chips de estado, Exportar CSV com `;`/BOM/anti-fórmula via `lib/csv.ts`) · `Drawer` + `CampoDrawer` (painel
direito "FLICSALES / CONTEXTO", Esc fecha) · `Etiqueta` (`green`/`amber`/`neutra`/`azul`) · `Passos` · `Kanban<T>` +
`CartaoKanban` (arrastar opcional) · `Dinheiro` (R$ mono; aceita string decimal) · `notificar()` (toast) ·
`AcessoRapido` · `Fonte` (evidência/fonte/limite) · `EmptyState` · `ConfirmDialog` · `Field`/`NativeSelect` (form.tsx).
Eventos globais (`components/flic/eventos.ts`): `useAtalhoNovo(fn)` (Alt+N da tela), `abrirAssistente(escopo, registro?)`,
`abrirPaleta(termo)`. Cores só por token (`bg-surface`, `text-ink`, `text-muted`, `bg-primary`, `text-accent`, `bg-subtle`,
`border-line`, `text-amber-ink`…) definidos em `app/globals.css`; **`muted` é cor de texto**, fundo neutro é `bg-subtle`.

**Dados.** O navegador só chama `/bff/*` via `lib/api.ts` (`api.get/post/put/patch/del`, `ApiError`; cookies httpOnly,
renovação automática, `X-Requested-With: flicsales`). TanStack Query; erro de API vira toast sozinho, a menos que a
query/mutation tenha `meta: { silencioso: true }`. Tipos do core em `lib/types.ts` (`Pagina<T>`, `UsuarioMe`, `RespostaIA`…);
tipos de cada área em `lib/tipos-<area>.ts` (ex.: `tipos-comercial.ts`, `tipos-financeiro.ts`, `tipos-nucleo.ts`).
Datas-de-dia com `data()`/`competencia()` de `lib/format.ts` (formatam da string, nunca `new Date()`); dinheiro com `moeda()`/`<Dinheiro>`.

Exemplo mínimo (lista + drawer):

```tsx
"use client";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Pagina } from "@/lib/types";
import type { Titulo } from "@/lib/tipos-financeiro";

const COLUNAS: Coluna<Titulo>[] = [
  { id: "emp", titulo: "Empresa / descrição", celula: (t) => <><strong>{t.empresa_nome}</strong><p className="text-muted">{t.descricao}</p></> },
  { id: "saldo", titulo: "Saldo aberto", alinhar: "direita", celula: (t) => <Dinheiro valor={t.saldo} /> },
];

export default function ReceberPage() {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<Titulo | null>(null);
  const [novo, setNovo] = useState(false);
  useAtalhoNovo(() => setNovo(true));
  const { data, isPending } = useQuery({ queryKey: ["titulos", "receber", q], queryFn: () => api.get<Pagina<Titulo>>("/financeiro/titulos", { direcao: "receber", q }) });
  return (
    <>
      <PageHeader titulo="A receber" descricao="Lançamentos, vencimentos, baixas, histórico e responsáveis." acao={<Button onClick={() => setNovo(true)}>+ Lançamento</Button>} />
      <BarraFiltros busca={{ valor: q, onChange: setQ }} exportar={{ nome: "a-receber", linhas: data?.itens ?? [], colunas: [{ titulo: "Empresa", valor: (t) => t.empresa_nome }] }} />
      <DataTable colunas={COLUNAS} linhas={data?.itens} chave={(t) => t.id} onLinha={setSel} carregando={isPending} />
      <Drawer aberto={!!sel} onFechar={() => setSel(null)} rotulo="TÍTULO / A RECEBER" titulo={sel?.descricao}>…</Drawer>
      <Drawer aberto={novo} onFechar={() => setNovo(false)} titulo="Novo título">…</Drawer>
    </>
  );
}
```

**IA no front.** O botão "✧ IA unificada" e o "✧ Perguntar à IA" abrem o `AssistenteDrawer` (montado no shell), que chama
`POST /bff/orquestracao/ia/perguntar` com `PerguntaIA` → `RespostaIA` (`lib/types.ts`). Enquanto a rota não existir
(404) ou a IA estiver desligada (503/409), mostra mensagem amigável. Detalhes e pendências: `docs/progresso-fundacao-front.md`.
