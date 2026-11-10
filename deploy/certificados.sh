#!/usr/bin/env bash
#
# Endereços e HTTPS do FlicSales OS (um banco por organização). Roda como root, pelo instalar.sh, pelo deploy.sh e a
# cada 5 minutos pelo timer flicsales-os-certificados@<amb>.timer:
#
#   sudo bash deploy/certificados.sh hml
#
# 1. Lê os endereços: DOMINIO_PRINCIPAL e DOMINIOS_EXTRAS (do backend/.env) + os domínios das organizações não
#    inativas no banco de controle (<slug>.<DOMINIO_BASE> e domínios próprios).
# 2. Para cada endereço sem certificado, pede um ao Let's Encrypt pelo desafio HTTP (webroot). Só para ESTES
#    endereços: certificados de outros sistemas não são tocados. Quem falhar fica para a próxima volta (no máximo uma
#    tentativa por hora por endereço, para não estourar o limite do Let's Encrypt).
# 3. Regera /etc/nginx/sites-available/flicsales-os-<amb> (porta 80: desafio + redireciona; 443: um bloco por endereço
#    com certificado) e só recarrega o nginx se mudou E se o `nginx -t` aprovar; senão volta o arquivo anterior.
#    Sem `map` global, sem default_server: o servidor é compartilhado (o site "flicsales" do sistema antigo e os
#    demais ficam intactos).
#
# Modo IP (MODO_ACESSO=ip no .env, o hml por enquanto): sem certbot e sem domínio. Um server só, ouvindo na porta
# própria IP_PORTA (10075 no hml), sem server_name de domínio; o default_server da porta 80 (do flicsales antigo)
# não é tocado.
#
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/comum.sh
. "$AQUI/comum.sh"
definir_ambiente "${1:-}"
ENV="$DIR/backend/.env"
SITE="/etc/nginx/sites-available/$SITE_NGINX"
LINK="/etc/nginx/sites-enabled/$SITE_NGINX"
SNIPPET="/etc/nginx/snippets/$SITE_NGINX-locations.conf"
WEBROOT="/var/www/flicsales-os-acme"
ESTADO="/var/lib/flicsales-os-certificados/$AMB"

[ "$(id -u)" = "0" ] || { echo "Rode com sudo."; exit 1; }
[ -f "$ENV" ] || { echo "Não achei $ENV."; exit 1; }
API_PORTA="$(val_env API_PORTA "$ENV")"; WEB_PORTA="$(val_env WEB_PORTA "$ENV")"
PRINCIPAL="$(val_env DOMINIO_PRINCIPAL "$ENV")"; EXTRAS="$(val_env DOMINIOS_EXTRAS "$ENV")"
MODO="$(val_env MODO_ACESSO "$ENV")"; MODO="${MODO:-dominio}"
IP_PORTA_ENV="$(val_env IP_PORTA "$ENV")"
[ -n "$API_PORTA" ] && [ -n "$WEB_PORTA" ] && [ -n "$PRINCIPAL" ] || { echo "API_PORTA, WEB_PORTA e DOMINIO_PRINCIPAL no .env."; exit 1; }
# shellcheck disable=SC2016  # $host/$http_host são variáveis do nginx, não do bash
if [ "$MODO" = "ip" ]; then
  XFH='$http_host'; HSTS='# (sem HSTS: modo IP, http puro)'
  [ -n "$IP_PORTA_ENV" ] || { echo "Modo IP sem IP_PORTA no .env."; exit 1; }
else
  XFH='$host'; HSTS='add_header Strict-Transport-Security "max-age=31536000" always;'
fi
mkdir -p "$WEBROOT" "$ESTADO" /etc/nginx/snippets
[ -n "${EMAIL_LETSENCRYPT:-}" ] && echo "$EMAIL_LETSENCRYPT" > "$ESTADO/email"
EMAIL_LE="$(cat "$ESTADO/email" 2>/dev/null || true)"

# ---------------------------------------------------------------- endereços
HOSTS="$PRINCIPAL $EXTRAS"
ler_nomes_do_codigo
if banco_existe "$NOME_CONTROLE" && [ "$(dono_do_banco "$NOME_CONTROLE")" = "$ROLE" ]; then
  HOSTS="$HOSTS $(psql_su -d "$NOME_CONTROLE" -c \
    "SELECT d.host FROM dominio d JOIN organizacao o ON o.id = d.organizacao_id WHERE o.status <> 'inativo' ORDER BY d.id" | tr '\n' ' ')"
fi
HOSTS="$(echo "$HOSTS" | tr ' ' '\n' | grep -E '^[a-z0-9.-]+\.[a-z]{2,}$' | awk '!v[$0]++' | tr '\n' ' ')"

tem_cert() { [ -s "/etc/letsencrypt/live/$1/fullchain.pem" ]; }

gerar_ip() {  # modo IP: um server na porta própria, sem domínio
  local tmp; tmp="$(mktemp)"
  {
    echo "# FlicSales OS ($AMB) — GERADO por deploy/certificados.sh em $(date '+%d/%m/%Y %H:%M'). Não edite à mão."
    echo "# Modo IP: http://<IP>:$IP_PORTA_ENV (sem HTTPS). Para domínio: docs/DEPLOY.md › Do IP para o domínio."
    echo "limit_req_zone \$binary_remote_addr zone=flicsalesos_${AMB}_auth:10m rate=10r/m;"
    echo "limit_req_zone \$binary_remote_addr zone=flicsalesos_${AMB}_geral:10m rate=20r/s;"
    echo
    echo "server {"
    echo "    listen $IP_PORTA_ENV;"
    echo "    listen [::]:$IP_PORTA_ENV;"
    echo "    server_name _;   # único server desta porta; não afeta a porta 80 nem outros sites"
    echo "    include $SNIPPET;"
    echo "}"
  } > "$tmp"
  echo "$tmp"
}

gerar() {  # escreve o site com os certificados que existem agora
  local tmp h; tmp="$(mktemp)"
  {
    echo "# FlicSales OS ($AMB) — GERADO por deploy/certificados.sh em $(date '+%d/%m/%Y %H:%M'). Não edite à mão."
    echo "limit_req_zone \$binary_remote_addr zone=flicsalesos_${AMB}_auth:10m rate=10r/m;"
    echo "limit_req_zone \$binary_remote_addr zone=flicsalesos_${AMB}_geral:10m rate=20r/s;"
    echo
    echo "server {"
    echo "    listen 80;"
    echo "    listen [::]:80;"
    echo "    server_name $HOSTS;"
    echo "    server_tokens off;"
    echo "    location /.well-known/acme-challenge/ { root $WEBROOT; }"
    echo "    location / { return 301 https://\$host\$request_uri; }"
    echo "}"
    for h in $HOSTS; do
      tem_cert "$h" || continue
      echo
      echo "server {"
      echo "    listen 443 ssl http2;"     # nginx 1.24 do Ubuntu 24.04: http2 vai no listen
      echo "    listen [::]:443 ssl http2;"
      echo "    server_name $h;"
      echo "    ssl_certificate /etc/letsencrypt/live/$h/fullchain.pem;"
      echo "    ssl_certificate_key /etc/letsencrypt/live/$h/privkey.pem;"
      echo "    include /etc/letsencrypt/options-ssl-nginx.conf;"
      echo "    include $SNIPPET;"
      echo "}"
    done
  } > "$tmp"
  echo "$tmp"
}

aplicar() {  # troca o site só se mudou e o nginx aprovar; senão desfaz
  local novo="$1" antigo_bkp=""
  sed "s|__API__|$API_PORTA|g; s|__WEB__|$WEB_PORTA|g; s|__AMB__|$AMB|g; s|__XFH__|$XFH|g; s|__HSTS__|$HSTS|g"     "$DIR/deploy/nginx/flicsales-os-locations.conf" > "$SNIPPET.novo"
  if [ -f "$SITE" ] && cmp -s <(grep -v '^# FlicSales OS' "$SITE") <(grep -v '^# FlicSales OS' "$novo") \
     && [ -f "$SNIPPET" ] && cmp -s "$SNIPPET" "$SNIPPET.novo" && [ -L "$LINK" ]; then
    rm -f "$novo" "$SNIPPET.novo"; return 0
  fi
  if [ -f "$SITE" ]; then antigo_bkp="$(mktemp)"; cp "$SITE" "$antigo_bkp"; fi
  if [ -f "$SNIPPET" ]; then cp "$SNIPPET" "$SNIPPET.bkp"; fi
  mv "$SNIPPET.novo" "$SNIPPET"
  install -m 644 "$novo" "$SITE"; rm -f "$novo"
  ln -sf "$SITE" "$LINK"
  if nginx -t 2>"/tmp/$SITE_NGINX-nginx.txt"; then
    systemctl reload nginx
    echo "nginx recarregado ($SITE_NGINX: $(grep -c 'listen 443' "$SITE") endereço(s) com HTTPS)."
  else
    echo "O nginx recusou a configuração nova; voltei a anterior (os outros sites seguem intactos):"
    cat "/tmp/$SITE_NGINX-nginx.txt"
    if [ -n "$antigo_bkp" ]; then install -m 644 "$antigo_bkp" "$SITE"; else rm -f "$SITE" "$LINK"; fi
    if [ -f "$SNIPPET.bkp" ]; then mv "$SNIPPET.bkp" "$SNIPPET"; fi
    exit 1
  fi
}

# shellcheck disable=SC2016  # $host/$http_host são variáveis do nginx, não do bash
if [ "$MODO" = "ip" ]; then
  aplicar "$(gerar_ip)"
  exit 0
fi

[ -f /etc/letsencrypt/options-ssl-nginx.conf ] || { echo "Falta /etc/letsencrypt/options-ssl-nginx.conf (vem com python3-certbot-nginx)."; exit 1; }

# 1ª passada: garante a porta 80 com o desafio para todos os endereços
aplicar "$(gerar)"

# certificados que faltam (uma tentativa por hora por endereço; só os endereços deste ambiente)
for h in $HOSTS; do
  tem_cert "$h" && continue
  marca="$ESTADO/$h.tentativa"
  if [ -f "$marca" ] && [ "$(( $(date +%s) - $(stat -c %Y "$marca") ))" -lt 3600 ]; then continue; fi
  touch "$marca"
  if [ -n "$EMAIL_LE" ]; then CONTA=(-m "$EMAIL_LE"); else CONTA=(--register-unsafely-without-email); fi
  # a renovação automática do certbot recarrega o nginx (deploy-hook)
  if certbot certonly --webroot -w "$WEBROOT" -d "$h" --cert-name "$h" --non-interactive --agree-tos "${CONTA[@]}" \
       --quiet --deploy-hook "systemctl reload nginx"; then
    echo "certificado emitido: $h"; rm -f "$marca"
  else
    echo "sem certificado ainda para $h (DNS apontado para este servidor?); tento de novo em 1 hora"
  fi
done

# 2ª passada: blocos 443 para quem já tem certificado
aplicar "$(gerar)"
