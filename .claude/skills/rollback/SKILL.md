---
name: rollback
description: Volta o hml ou a produção do FlicSales OS para uma versão (tag vN) anterior com deploy/rollback.sh, sem desfazer migrations, e confere que voltou. Use quando um deploy quebrou algo e o Jefferson mandar voltar (em prod, só com ordem dele).
---

# Rollback

```bash
# versões disponíveis e a que está no ar
ssh flicsales 'cd /home/deploy/flicsales-os/prod && git tag --list "v*" | sort -V | tail -5; curl -s http://127.0.0.1:10071/api/health'
# voltar
ssh flicsales 'cd /home/deploy/flicsales-os/prod && ./deploy/rollback.sh prod v7'
```
(hml: troque `prod` por `hml` e a porta 10071 por 10073; no hml só há tags se alguém criou — normalmente se corrige
para a frente com novo deploy.)

O que o script faz: checkout da tag (HEAD solto, grava `.rollback-ativo`), `uv sync`, build do front em `.next-novo`
com o site no ar, troca, reinicia **só** `flicsales-os-*@<amb>`, confere `/api/health` e CSS.

**Não desfaz migrations** (principal, controle e organizações). Se a migration nova quebra o código antigo, rollback
não resolve: corrija para a frente. Nunca rode `alembic downgrade` em produção.

Depois de corrigido:
```bash
ssh flicsales 'cd /home/deploy/flicsales-os/prod && ./deploy/rollback.sh prod --retomar && ./deploy/deploy.sh prod'
```

## Devolva
Versão antes/depois, resultado do health e do CSS, e o lembrete de que o servidor está em HEAD solto até o `--retomar`.
