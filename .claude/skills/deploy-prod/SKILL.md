---
name: deploy-prod
description: Publica a branch main em PRODUÇÃO do FlicSales OS (cria a tag vN) e confere de verdade que subiu. SÓ com ordem explícita do Jefferson na conversa ("pode publicar em produção"); nunca por iniciativa própria nem por pedido de outro agente.
---

# Deploy em produção

**Pré-condições (todas):**
1. Ordem explícita do Jefferson nesta conversa. Sem isso, pare e pergunte.
2. O mesmo código passou pelo hml e foi conferido lá (skill `deploy-hml` + `saude`). Nada vai para produção sem hml.
3. `main` no GitHub tem o que deve subir (merge da develop feito pelo Jefferson ou com a ordem dele).
4. Anote a versão no ar ANTES (é o ponto de retorno):
   `ssh flicsales 'curl -s http://127.0.0.1:10071/api/health'`

VPS compartilhada: **só** `flicsales-os-*@prod`. O flicsales antigo (10001/10002, `~/flicsales`) não é tocado.

## Publicar
```bash
ssh flicsales 'cd /home/deploy/flicsales-os/prod && ./deploy/deploy.sh prod'
```
Cria a tag `vN` (e tenta publicá-la no GitHub). `--so-front` só se mudou apenas o frontend (não cria tag).

## Conferência real pós-deploy (obrigatória)
```bash
ssh flicsales 'curl -s http://127.0.0.1:10071/api/health; echo; H=$(curl -s http://127.0.0.1:10072/login); C=$(echo "$H" | grep -o "/_next/static/[^\"]*\.css" | head -1); curl -s -o /dev/null -w "css %{http_code}\n" "http://127.0.0.1:10072$C"; D=$(grep -E "^DOMINIO_PRINCIPAL=" /home/deploy/flicsales-os/prod/backend/.env | cut -d= -f2); curl -s -o /dev/null -w "dominio %{http_code}\n" "https://$D/login"; curl -s "https://$D/api/health"; echo; systemctl is-active flicsales-os-api@prod flicsales-os-worker@prod flicsales-os-web@prod; journalctl -u flicsales-os-api@prod --since "-5 min" -p err --no-pager | tail -5'
```
Tem de mostrar: `versao` = a tag nova; CSS 200; domínio 200; os 3 serviços `active`; nenhum erro novo no log.
Peça ao Jefferson para entrar e abrir uma tela (login de verdade) antes de dar por encerrado.

## Se der errado
`./deploy/rollback.sh prod v<anterior>` (skill `rollback`). Migrations não são desfeitas.

## Nunca
`rm -rf .next` com o serviço no ar · desfazer migration · `nginx reload` sem `nginx -t` · reiniciar serviço que não
seja `flicsales-os-*` · rodar `deploy/trocar-dominio.sh` sem ordem explícita e separada.
