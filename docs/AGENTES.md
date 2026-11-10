# Agentes e skills do FlicSales OS

Ficam em `.claude/agents/` e `.claude/skills/`. A sessão principal do Claude é o **coordenador**: quebra o trabalho,
dispara os agentes (em paralelo quando as pastas não se cruzam), integra e pede QA.

| Agente | Papel | Edita código? |
|---|---|---|
| `backend` | Rotas, schemas, serviços, permissões, auditoria e testes de um módulo | sim |
| `frontend` | Telas fiéis ao protótipo (Next + shadcn + TanStack Query) | sim |
| `dominio` | Regras de negócio puras em `app/domain/` com testes de mesa (dinheiro, baixas, recorrência, forecast) | sim |
| `ia-orquestrador` | Camada de IA unificada: gateway, ferramentas com permissão, evidências, leitura determinística | sim |
| `qa` | Caça defeito real com evidência; roda suíte + build; veredito APROVADO/REPROVADO | não |
| `paridade` | Compara tela × protótipo e dá placar do que falta | não |

| Skill | Quando |
|---|---|
| `verificar` | Antes de commitar/integrar: pytest + lint + build |
| `nova-tela` | Checklist para criar qualquer tela/CRUD de ponta a ponta |
| `demo` | Sobe o sistema local com os dados do protótipo e o roteiro do critério de aceite |

## Fluxo padrão de uma entrega
1. Coordenador escolhe telas da `ESPECIFICACAO.md` → `dominio` (se tem regra nova) → `backend` + `frontend` (podem ser paralelos com contrato de API combinado) → `paridade` → `qa` → commit.
2. Módulos diferentes rodam em paralelo (cada um dono das suas pastas; ver "Convenções" no `CLAUDE.md`).

## Futuro (quando houver servidor)
- `publicador`: deploy hml → prod com tag `vN` e conferência real (health, CSS, telas). Só depois que o Jefferson definir o servidor e as portas.
