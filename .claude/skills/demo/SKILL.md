---
name: demo
description: Sobe o FlicSales OS localmente com a organização de demonstração do protótipo (Aurora, Vértice, Horizonte, Atlas…) — recria o banco SQLite de dev, aplica migrações, roda o seed e inicia backend (8000) e frontend (3000). Use quando o Jefferson quiser ver o sistema rodando ou mostrar para alguém.
---

# Demo local

1. Backend (em segundo plano):
   ```bash
   cd backend && uv sync -q && rm -f data/flicsales.db && uv run python -m alembic upgrade head && uv run python -m app.seed
   uv run python -m uvicorn app.main:app --port 8000
   ```
2. Frontend (em segundo plano): `cd frontend && npm install --silent && npm run dev`
3. Confira `curl -s http://127.0.0.1:8000/api/health` e `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/login`.
4. Informe: endereço `http://localhost:3000`, logins do seed (gestor `francine`, comercial `marina`/`lucas`, financeiro `fin`) e a senha definida em `app/seed.py`.
5. Roteiro sugerido para mostrar (critério de aceite): Comercial › Oportunidades › Aurora → Marcar como ganha (2 parcelas) → Financeiro › A receber → Revisar e confirmar → Registrar recebimento parcial → Caixa → Núcleo › Histórico de ações.
