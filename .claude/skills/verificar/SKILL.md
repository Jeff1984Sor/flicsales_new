---
name: verificar
description: Roda a verificação completa do FlicSales OS localmente — testes do backend (pytest), lint e build do frontend — e resume o resultado. Use antes de commitar, de integrar um módulo ou quando o Jefferson perguntar "está tudo verde?".
---

# Verificar

1. Backend:
   ```bash
   cd backend && uv sync -q && uv run python -m pytest -q 2>&1 | tail -15
   ```
2. Frontend:
   ```bash
   cd frontend && npm run lint 2>&1 | tail -20 && npm run build 2>&1 | tail -25
   ```
3. Responda em 3 linhas: `backend: N passaram / M falharam`, `lint: ok|N erros`, `build: ok|erro`.
   Se algo falhou, mostre a primeira falha com `arquivo:linha` e a causa provável. Não esconda falha: verde parcial não é verde.
