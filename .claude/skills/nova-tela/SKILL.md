---
name: nova-tela
description: Checklist para criar uma tela nova (ou cadastro) no FlicSales OS de ponta a ponta — modelo, domínio, rota com permissão e auditoria, testes, tipos, página, item de menu e paridade com o protótipo. Use sempre que for adicionar uma tela ou um CRUD.
---

# Nova tela — checklist

Argumento: nome da tela (como aparece no menu do protótipo).

1. **Protótipo**: ache a função JS da tela em `docs/prototipo/flicsales-prototipo.html` e a seção em `docs/ESPECIFICACAO.md`. Anote título, subtítulo, campos (obrigatórios com `*`), validações (`notify(...)`) e textos de limite.
2. **Modelo**: existe em `backend/app/modules/<modulo>/models.py`? Se não, crie e gere migração nova (`uv run python -m alembic revision --autogenerate -m "..."`) — revise o arquivo gerado.
3. **Regra**: validações que não são "campo obrigatório" vão para `backend/app/domain/` com teste de mesa.
4. **Rota**: `routes.py` do módulo, schemas Pydantic (`Criar`, `Atualizar` com tudo opcional, `Saida`), `adicionar_regras(...)` com o recurso de permissão, `ctx.auditar(...)` em criar/alterar/cancelar/estornar.
5. **Testes**: `backend/tests/<modulo>/test_<tela>.py` — sucesso, validação com mensagem, 403 por perfil, 404. Rode também `tests/test_cobertura_rotas.py`.
6. **Front**: tipos em `frontend/lib/tipos-<area>.ts`; página em `frontend/app/(app)/<area>/<tela>/page.tsx` usando PageHeader + barra de filtros + DataTable + Drawer; item do menu em `components/flic/nav.ts` (`planejado: false`).
7. **Verificar**: skill `verificar`. Depois peça ao agente `paridade` a conferência da tela.
8. Atualize `docs/progresso-<modulo>.md`.
