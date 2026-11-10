#!/usr/bin/env bash
#
# Troca de flicsales.com.br para o FlicSales OS (prod). SÓ COM ORDEM EXPLÍCITA DO JEFFERSON.
#
#   sudo bash deploy/trocar-dominio.sh --simular                 # só mostra o que faria (não altera nada)
#   sudo CONFIRMO=sim bash deploy/trocar-dominio.sh              # executa
#   sudo CONFIRMO=sim bash deploy/trocar-dominio.sh --reverter /home/deploy/flicsales-os/troca-dominio/<data>
#
# O que a execução faz, nesta ordem (para em qualquer erro; o que já mudou é revertido):
#   1. confere: prod do OS no ar (modo domínio, /api/health 200), site nginx "flicsales" (antigo) existe, DNS de
#      antigo.flicsales.com.br resolve, nginx -t passa ANTES de qualquer mudança;
#   2. backup em /home/deploy/flicsales-os/troca-dominio/<data>/: conf e link do site "flicsales", site e snippet do
#      OS prod, backend/.env do OS prod;
#   3. publica o site novo "flicsales-antigo" (antigo.flicsales.com.br -> portas 10001/10002 do sistema antigo) e pede o
#      certificado SÓ desse nome; o sistema antigo continua acessível por ele durante o período de convivência;
#   4. no .env do OS prod: DOMINIO_PRINCIPAL=flicsales.com.br, DOMINIO_BASE=flicsales.com.br, DOMINIOS_EXTRAS com www e
#      os.flicsales.com.br, ALLOWED_HOSTS/CORS/FRONTEND_URL; acrescenta <slug>.flicsales.com.br a cada organização;
#   5. DESATIVA o site "flicsales" (remove só o link em sites-enabled; o arquivo fica em sites-available e no backup)
#      e roda deploy/certificados.sh prod, que gera o site do OS com flicsales.com.br, testa (nginx -t) e recarrega;
#   6. reinicia SÓ flicsales-os-api@prod e flicsales-os-worker@prod e confere https://flicsales.com.br/api/health e
#      https://antigo.flicsales.com.br.
# Nenhum serviço do sistema antigo é parado ou reiniciado. O certbot só é chamado para nomes novos.
#
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/comum.sh
. "$AQUI/comum.sh"
definir_ambiente prod

NOVO="${NOVO_DOMINIO:-flicsales.com.br}"
ANTIGO_HOST="${ANTIGO_HOST:-antigo.flicsales.com.br}"
ANTIGO_API="${ANTIGO_API_PORTA:-10001}"
ANTIGO_WEB="${ANTIGO_WEB_PORTA:-10002}"
SITE_ANTIGO=/etc/nginx/sites-available/flicsales
SITE_CONVIVENCIA=/etc/nginx/sites-available/flicsales-antigo
ENV="$DIR/backend/.env"
WEBROOT="/var/www/flicsales-os-acme"
BACKUPS="$BASE_OS/troca-dominio"

SIMULAR=0; REVERTER=""
case "${1:-}" in
  --simular) SIMULAR=1 ;;
  --reverter) REVERTER="${2:?informe a pasta do backup}" ;;
  "") ;;
  *) echo "Uso: --simular | --reverter <pasta> | (sem argumento, com CONFIRMO=sim)"; exit 1 ;;
esac
[ "$(id -u)" = "0" ] || { echo "Rode com sudo."; exit 1; }
if [ "$SIMULAR" = "0" ] && [ "${CONFIRMO:-}" != "sim" ]; then
  echo "Isto troca o domínio de PRODUÇÃO ($NOVO). Rode antes com --simular e, com ordem explícita, CONFIRMO=sim."
  exit 1
fi
links_do_antigo() {  # links em sites-enabled que apontam para o site antigo
  find /etc/nginx/sites-enabled -maxdepth 1 -type l -lname "*sites-available/flicsales" 2>/dev/null || true
}
nginx_ok() { nginx -t 2>/tmp/flicsales-os-troca-nginx.txt || { cat /tmp/flicsales-os-troca-nginx.txt; return 1; }; }

# ------------------------------------------------------------------------------------------------- reverter
if [ -n "$REVERTER" ]; then
  [ -f "$REVERTER/backend.env" ] || { echo "Backup inválido: $REVERTER"; exit 1; }
  echo "=== Revertendo a troca a partir de $REVERTER ==="
  install -m 600 -o "$USUARIO_DEPLOY" -g "$USUARIO_DEPLOY" "$REVERTER/backend.env" "$ENV"
  if [ -f "$REVERTER/site-flicsales-antigo.conf" ]; then
    install -m 644 "$REVERTER/site-flicsales-antigo.conf" "$SITE_CONVIVENCIA"
  else  # o site de convivência nasceu nesta troca: sai do ar (o arquivo fica para consulta)
    rm -f /etc/nginx/sites-enabled/flicsales-antigo
  fi
  while read -r link; do
    [ -n "$link" ] && ln -sf "$SITE_ANTIGO" "$link"
  done < "$REVERTER/links-antigo.txt"
  # o site do OS volta só com os nomes do .env restaurado (certificados.sh testa e recarrega)
  bash "$DIR/deploy/certificados.sh" prod
  nginx_ok && systemctl reload nginx
  systemctl restart "flicsales-os-api@prod" "flicsales-os-worker@prod"
  echo "Revertido: $NOVO voltou para o sistema antigo; o OS segue em $(val_env DOMINIO_PRINCIPAL "$ENV")."
  echo "(Os domínios <slug>.$NOVO acrescentados às organizações ficam no controle; não atrapalham.)"
  exit 0
fi

# ------------------------------------------------------------------------------------------------- 1. conferências
echo "=== Troca de domínio: $NOVO -> FlicSales OS prod  ($([ "$SIMULAR" = 1 ] && echo SIMULAÇÃO || echo EXECUÇÃO)) ==="
echo "--- 1/6 Conferências (nada é alterado)"
ERROS=0
[ -f "$ENV" ] || { echo "    FALTA: OS prod não instalado ($ENV)."; exit 1; }
[ "$(val_env MODO_ACESSO "$ENV")" = "dominio" ] || { echo "    FALTA: prod precisa estar no modo domínio."; ERROS=1; }
ATUAL="$(val_env DOMINIO_PRINCIPAL "$ENV")"
[ "$ATUAL" = "$NOVO" ] && { echo "    O OS prod já está em $NOVO. Nada a fazer."; exit 0; }
SAUDE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$API_PORTA/api/health" || true)"
echo "    OS prod hoje em $ATUAL; /api/health interno: HTTP $SAUDE"
[ "$SAUDE" = "200" ] || { echo "    FALTA: a API do OS prod não responde."; ERROS=1; }
if [ -f "$SITE_ANTIGO" ]; then
  echo "    site antigo $SITE_ANTIGO; links ativos: $(links_do_antigo | paste -sd' ')"
  echo "    server_name do antigo:"; grep -E '^\s*server_name' "$SITE_ANTIGO" | sed 's/^/      /'
  echo "    locations do antigo (o site de convivência cobre / e /api/; confira se falta alguma):"
  grep -E '^\s*location' "$SITE_ANTIGO" | sed 's/^/      /'
else
  echo "    FALTA: $SITE_ANTIGO não existe."; ERROS=1
fi
for h in "$ANTIGO_HOST" "$NOVO" "www.$NOVO"; do
  if getent hosts "$h" >/dev/null; then echo "    DNS $h -> $(getent hosts "$h" | awk '{print $1}' | head -1)"
  else echo "    FALTA: DNS de $h não resolve."; ERROS=1; fi
done
for h in "$NOVO" "www.$NOVO" "$ANTIGO_HOST"; do
  if [ -s "/etc/letsencrypt/live/$h/fullchain.pem" ]; then echo "    certificado existente: $h"
  else echo "    certificado a emitir: $h"; fi
done
nginx_ok || { echo "    FALTA: o nginx -t já falha HOJE; não mexo em nada."; ERROS=1; }
[ "$ERROS" = "0" ] || { echo "Conferências falharam. Nada foi alterado."; exit 1; }

ORGS="$(sudo -u "$USUARIO_DEPLOY" -H bash -c "cd '$DIR/backend' && .venv/bin/python -m app.controle.cli listar" | awk '$2!="inativo"{print $1}')"
EXTRAS="www.$NOVO $ATUAL"
if [ "$SIMULAR" = "1" ]; then
  cat <<PLANO
--- O que a execução faria
    2. backup em $BACKUPS/<data>/ (site flicsales + links, site/snippet do OS prod, backend/.env)
    3. cria $SITE_CONVIVENCIA: $ANTIGO_HOST -> 127.0.0.1:$ANTIGO_WEB (/) e :$ANTIGO_API (/api/, sem o prefixo)
       e pede certificado só para $ANTIGO_HOST
    4. .env do OS prod: DOMINIO_PRINCIPAL=$NOVO, DOMINIO_BASE=$NOVO, DOMINIOS_EXTRAS="$EXTRAS",
       ALLOWED_HOSTS=["$NOVO","*.$NOVO","127.0.0.1"], CORS/FRONTEND_URL=https://$NOVO
       domínios novos nas organizações: $(for o in $ORGS; do printf '%s.%s ' "$o" "$NOVO"; done)
    5. remove os links do site antigo: $(links_do_antigo | paste -sd' ') (o arquivo fica)
       e regera o site do OS com $NOVO + $EXTRAS (nginx -t antes do reload)
    6. reinicia flicsales-os-api@prod e flicsales-os-worker@prod; confere https://$NOVO e https://$ANTIGO_HOST
    Nada disso foi feito (simulação).
PLANO
  exit 0
fi

# ------------------------------------------------------------------------------------------------- 2. backup
QUANDO="$(date +%Y%m%d-%H%M%S)"
BK="$BACKUPS/$QUANDO"
mkdir -p "$BK"; chmod 700 "$BK"
echo "--- 2/6 Backup em $BK"
cp -a "$SITE_ANTIGO" "$BK/site-flicsales.conf"
links_do_antigo > "$BK/links-antigo.txt"
[ -f "/etc/nginx/sites-available/$SITE_NGINX" ] && cp -a "/etc/nginx/sites-available/$SITE_NGINX" "$BK/"
[ -f "/etc/nginx/snippets/$SITE_NGINX-locations.conf" ] && cp -a "/etc/nginx/snippets/$SITE_NGINX-locations.conf" "$BK/"
[ -f "$SITE_CONVIVENCIA" ] && cp -a "$SITE_CONVIVENCIA" "$BK/site-flicsales-antigo.conf"
cp -a "$ENV" "$BK/backend.env"
chown -R "$USUARIO_DEPLOY" "$BK"
echo "    para desfazer: sudo CONFIRMO=sim bash $DIR/deploy/trocar-dominio.sh --reverter $BK"

reverter_e_sair() {
  echo "    ERRO: $1 — revertendo"
  CONFIRMO=sim bash "$DIR/deploy/trocar-dominio.sh" --reverter "$BK" || true
  exit 1
}

# ------------------------------------------------------------------------------------------------- 3. convivência
echo "--- 3/6 Site de convivência $ANTIGO_HOST -> sistema antigo ($ANTIGO_WEB/$ANTIGO_API)"
mkdir -p "$WEBROOT"
escrever_convivencia() {  # $1 = com_https (0|1)
  {
    echo "# flicsales ANTIGO em $ANTIGO_HOST durante a convivência — GERADO por deploy/trocar-dominio.sh ($QUANDO)."
    echo "# Remover quando o sistema antigo for desligado (docs/DEPLOY.md › Migração)."
    echo "server {"
    echo "    listen 80; listen [::]:80;"
    echo "    server_name $ANTIGO_HOST;"
    echo "    location /.well-known/acme-challenge/ { root $WEBROOT; }"
    if [ "$1" = "1" ]; then echo "    location / { return 301 https://\$host\$request_uri; }"; fi
    echo "}"
    if [ "$1" = "1" ]; then
      echo "server {"
      echo "    listen 443 ssl http2; listen [::]:443 ssl http2;"
      echo "    server_name $ANTIGO_HOST;"
      echo "    ssl_certificate /etc/letsencrypt/live/$ANTIGO_HOST/fullchain.pem;"
      echo "    ssl_certificate_key /etc/letsencrypt/live/$ANTIGO_HOST/privkey.pem;"
      echo "    include /etc/letsencrypt/options-ssl-nginx.conf;"
      echo "    client_max_body_size 25M;"
      echo "    location /api/ {"
      echo "        proxy_pass http://127.0.0.1:$ANTIGO_API/;"
      echo "        proxy_http_version 1.1;"
      echo "        proxy_set_header Host \$host;"
      echo "        proxy_set_header X-Real-IP \$remote_addr;"
      echo "        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
      echo "        proxy_set_header X-Forwarded-Proto \$scheme;"
      echo "        proxy_read_timeout 120s;"
      echo "    }"
      echo "    location / {"
      echo "        proxy_pass http://127.0.0.1:$ANTIGO_WEB;"
      echo "        proxy_http_version 1.1;"
      echo "        proxy_set_header Upgrade \$http_upgrade;"
      echo "        proxy_set_header Connection \"upgrade\";"
      echo "        proxy_set_header Host \$host;"
      echo "        proxy_set_header X-Real-IP \$remote_addr;"
      echo "        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
      echo "        proxy_set_header X-Forwarded-Proto \$scheme;"
      echo "    }"
      echo "}"
    fi
  } > "$SITE_CONVIVENCIA"
  ln -sf "$SITE_CONVIVENCIA" /etc/nginx/sites-enabled/flicsales-antigo
  nginx_ok || reverter_e_sair "nginx -t recusou o site de convivência"
  systemctl reload nginx
}
escrever_convivencia 0
if [ ! -s "/etc/letsencrypt/live/$ANTIGO_HOST/fullchain.pem" ]; then
  EMAIL_LE="$(cat /var/lib/flicsales-os-certificados/prod/email 2>/dev/null || true)"
  if [ -n "$EMAIL_LE" ]; then CONTA=(-m "$EMAIL_LE"); else CONTA=(--register-unsafely-without-email); fi
  certbot certonly --webroot -w "$WEBROOT" -d "$ANTIGO_HOST" --cert-name "$ANTIGO_HOST" --non-interactive \
    --agree-tos "${CONTA[@]}" --quiet --deploy-hook "systemctl reload nginx" \
    || reverter_e_sair "certificado de $ANTIGO_HOST não saiu (DNS?)"
fi
escrever_convivencia 1
echo "    https://$ANTIGO_HOST publicado"

# ------------------------------------------------------------------------------------------------- 4. .env do OS
echo "--- 4/6 .env do OS prod -> $NOVO"
definir_env "$ENV" DOMINIO_PRINCIPAL "$NOVO"
definir_env "$ENV" DOMINIO_BASE "$NOVO"
definir_env "$ENV" DOMINIOS_EXTRAS "$EXTRAS"
definir_env "$ENV" ALLOWED_HOSTS "[\"$NOVO\",\"*.$NOVO\",\"127.0.0.1\"]"
definir_env "$ENV" CORS_ORIGINS "[\"https://$NOVO\",\"https://www.$NOVO\",\"https://$ATUAL\"]"
definir_env "$ENV" FRONTEND_URL "https://$NOVO"
for o in $ORGS; do
  sudo -u "$USUARIO_DEPLOY" -H bash -c "cd '$DIR/backend' && .venv/bin/python -m app.controle.cli dominio --slug '$o' --host '$o.$NOVO'" \
    || echo "    (aviso: $o.$NOVO não entrou — já existia?)"
done

# ------------------------------------------------------------------------------------------------- 5. nginx
echo "--- 5/6 Desativando o site antigo (só o link) e publicando o OS em $NOVO"
while read -r link; do [ -n "$link" ] && rm -f "$link"; done < "$BK/links-antigo.txt"
bash "$DIR/deploy/certificados.sh" prod || reverter_e_sair "certificados.sh falhou"

# ------------------------------------------------------------------------------------------------- 6. reinício
echo "--- 6/6 Reiniciando só flicsales-os-api@prod e flicsales-os-worker@prod"
systemctl restart "flicsales-os-api@prod" "flicsales-os-worker@prod"
API="$(esperar_200 "http://127.0.0.1:$API_PORTA/api/health")"
NOVO_COD="$(curl -s -o /dev/null -w '%{http_code}' "https://$NOVO/api/health" || echo 000)"
ANTIGO_COD="$(curl -s -o /dev/null -w '%{http_code}' "https://$ANTIGO_HOST/" || echo 000)"
echo "    API interna HTTP $API | https://$NOVO/api/health HTTP $NOVO_COD | https://$ANTIGO_HOST HTTP $ANTIGO_COD"
if [ "$API" != "200" ] || [ "$NOVO_COD" != "200" ]; then reverter_e_sair "o OS não respondeu em https://$NOVO"; fi
[ "$ANTIGO_COD" != "000" ] || echo "    AVISO: o antigo não respondeu em $ANTIGO_HOST (o .env do sistema antigo aceita esse host?)"
echo
echo "=== Troca feita: https://$NOVO é o FlicSales OS; o sistema antigo segue em https://$ANTIGO_HOST ==="
echo "    Desfazer: sudo CONFIRMO=sim bash $DIR/deploy/trocar-dominio.sh --reverter $BK"
echo "    Fim da convivência: remover /etc/nginx/sites-enabled/flicsales-antigo (nginx -t && reload)."
