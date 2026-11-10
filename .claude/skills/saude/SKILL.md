---
name: saude
description: Checagem SÓ LEITURA do FlicSales OS no servidor (hml e/ou prod) — serviços, /api/health e versão, CSS servido, disco, backups e últimos erros. Não reinicia nem altera nada. Use quando o Jefferson perguntar "está no ar?", "como está o servidor?" ou depois de um deploy.
---

# Saúde (só leitura)

Esta skill **não altera nada**: sem restart, sem deploy, sem editar arquivo, sem `nginx reload`. Achou problema →
relate e sugira o próximo passo (`deploy-hml`, `rollback`…), não conserte por conta própria.

Portas: prod API 10071 / web 10072; hml API 10073 / web 10074 / acesso por IP 10075.

```bash
ssh flicsales 'for A in hml prod; do
  D=/home/deploy/flicsales-os/$A; [ -f $D/backend/.env ] || { echo "== $A: não instalado"; continue; }
  AP=$(grep -E "^API_PORTA=" $D/backend/.env | cut -d= -f2); WP=$(grep -E "^WEB_PORTA=" $D/backend/.env | cut -d= -f2)
  echo "== $A (modo $(grep -E "^MODO_ACESSO=" $D/backend/.env | cut -d= -f2))"
  systemctl is-active flicsales-os-api@$A flicsales-os-worker@$A flicsales-os-web@$A | paste -sd" "
  curl -s -m 5 http://127.0.0.1:$AP/api/health; echo
  C=$(curl -s -m 5 http://127.0.0.1:$WP/login | grep -o "/_next/static/[^\"]*\.css" | head -1)
  curl -s -m 5 -o /dev/null -w "css %{http_code}\n" "http://127.0.0.1:$WP$C"
  echo "git: $(git -C $D rev-parse --abbrev-ref HEAD) $(git -C $D log -1 --format="%h %cr %s")"; [ -f $D/.rollback-ativo ] && echo "ROLLBACK ATIVO: $(cat $D/.rollback-ativo)"
  echo "último backup: $(ls -t /home/deploy/backups/flicsales-os/$A 2>/dev/null | head -1)"
  journalctl -u flicsales-os-api@$A -u flicsales-os-worker@$A -u flicsales-os-web@$A --since "-1 day" -p err --no-pager | tail -8
done; echo "== disco"; df -h / | tail -1; du -sh /home/deploy/backups/flicsales-os 2>/dev/null
systemctl list-timers "flicsales-os-*" --no-pager | head -5'
```

Externo: hml `curl -s -o /dev/null -w "%{http_code}" http://2.25.130.240:10075/login`; prod
`https://<DOMINIO_PRINCIPAL do .env>/login`.

## Devolva (curto)
Por ambiente: serviços, versão no ar, health, CSS, erros das últimas 24 h (resumidos), último backup; disco.
Destaque o que está fora do normal (serviço inativo, CSS ≠ 200, rollback ativo, backup com mais de 1 dia, disco > 85%).
