#!/usr/bin/env bash
#
# Primeira instalação do FlicSales OS (um banco por organização) num servidor que JÁ RODA outros sistemas,
# inclusive o flicsales ANTIGO. Regra: não atualizar, reiniciar nem reconfigurar nada que já exista. Só acrescentar.
# Idempotente: rodar de novo completa o que faltou e não refaz o que já está pronto (não troca segredos, não recria
# banco, não cria a organização de novo).
#
# Dois modos de acesso (MODO=ip | dominio; padrão: hml=ip, prod=dominio):
#
#   ip       http://<IP>:<porta própria> — hml 10075, prod 10076. Um server nginx só nessa porta (o default_server da
#            porta 80 é do flicsales antigo e não é tocado), sem certbot, cookies sem Secure. Uma organização só,
#            resolvida pelo catálogo de login (sem subdomínio). Abre a porta no ufw se o ufw estiver ativo.
#
#     sudo IP=2.25.130.240 ORG_SLUG=demo ORG_NOME="FlicSales Demo" GESTOR_EMAIL=voce@exemplo.com \
#          GESTOR_LOGIN=jefferson GESTOR_NOME="Jefferson" bash /tmp/flicsales-os-instalador/deploy/instalar.sh hml
#
#   dominio  https://<DOMINIO> e https://<slug>.<DOMINIO> (DNS e coringa apontados ANTES; certbot só nesses nomes):
#            hml.flicsales.com.br / os.flicsales.com.br (prod; flicsales.com.br só com deploy/trocar-dominio.sh).
#
#     sudo MODO=dominio ORG_SLUG=... ORG_NOME=... GESTOR_EMAIL=... GESTOR_LOGIN=... bash .../deploy/instalar.sh prod
#
# (o script pode rodar de um clone qualquer: ele clona o repositório em /home/deploy/flicsales-os/<amb>.)
# Opcionais: DOMINIO, IP, REPO, EMAIL_LETSENCRYPT, PULAR_DNS=1 (não confere DNS; o HTTPS fica para o timer).
#
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/comum.sh
. "$AQUI/comum.sh"
definir_ambiente "${1:-}"

MODO="${MODO:-$MODO_PADRAO}"
case "$MODO" in ip|dominio) ;; *) echo "MODO inválido: $MODO (ip ou dominio)"; exit 1 ;; esac
REPO="${REPO:-$REPO_PADRAO}"
ORG_SLUG="${ORG_SLUG:-}"
ORG_NOME="${ORG_NOME:-}"
GESTOR_EMAIL="${GESTOR_EMAIL:-}"
GESTOR_LOGIN="${GESTOR_LOGIN:-}"
GESTOR_NOME="${GESTOR_NOME:-}"
if [ "$MODO" = "ip" ]; then
  IP="${IP:-$(hostname -I | awk '{print $1}')}"
  [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "IP inválido: '$IP' (informe IP=...)"; exit 1; }
  ENDERECO="http://$IP:$IP_PORTA"
  DOMINIO=""
else
  DOMINIO="${DOMINIO:-$DOMINIO_PADRAO}"
  ENDERECO="https://$DOMINIO"
fi

[ "$(id -u)" = "0" ] || { echo "Rode com sudo."; exit 1; }
id "$USUARIO_DEPLOY" >/dev/null 2>&1 || { echo "Usuário $USUARIO_DEPLOY não existe."; exit 1; }
como() { sudo -u "$USUARIO_DEPLOY" -H bash -lc "$1"; }
ja_instalado() { [ -f "$DIR/backend/.env" ]; }

echo "=== FlicSales OS ($AMB, modo $MODO) -> $DIR · $ENDERECO · API $API_PORTA / web $WEB_PORTA ==="

# ------------------------------------------------------------------------------------------------------------------
echo "--- 1/11 Conferindo o servidor (nada é alterado nesta etapa)"
PORTAS="$API_PORTA $WEB_PORTA"
[ "$MODO" = "ip" ] && PORTAS="$PORTAS $IP_PORTA"
for p in $PORTAS; do
  if ss -ltn "( sport = :$p )" | grep -q LISTEN; then
    if [ "$p" = "$IP_PORTA" ] && grep -qs "listen $IP_PORTA" "/etc/nginx/sites-available/$SITE_NGINX"; then
      echo "    Porta $p já é do nginx deste ambiente: reinstalação, sigo."
    elif systemctl is-active --quiet "flicsales-os-api@$AMB" || systemctl is-active --quiet "flicsales-os-web@$AMB"; then
      echo "    Porta $p em uso pelo próprio FlicSales OS ($AMB): reinstalação, sigo."
    else
      echo "    Porta $p já está em uso por outro sistema. Abortado sem alterar nada."; exit 1
    fi
  fi
done
if [ -e "$DIR" ] && [ ! -d "$DIR/.git" ]; then
  echo "    $DIR existe e não é um clone do repositório. Abortado."; exit 1
fi
if [ -d "$DIR/.git" ]; then
  ORIGEM="$(git -C "$DIR" remote get-url origin 2>/dev/null || true)"
  [ "$ORIGEM" = "$REPO" ] || { echo "    $DIR aponta para '$ORIGEM' (esperado $REPO). Abortado."; exit 1; }
fi
if [ -e "/etc/nginx/sites-available/$SITE_NGINX" ] && ! grep -q "GERADO por deploy/certificados.sh" "/etc/nginx/sites-available/$SITE_NGINX"; then
  echo "    O site nginx $SITE_NGINX existe e não foi gerado por este sistema. Abortado."; exit 1
fi
if banco_existe "$BANCO" && [ "$(dono_do_banco "$BANCO")" != "$ROLE" ]; then
  echo "    O banco $BANCO existe com outro dono ($(dono_do_banco "$BANCO")). Abortado (não mexo em banco alheio)."; exit 1
fi
if [ "$MODO" = "dominio" ] && [ "${PULAR_DNS:-0}" != "1" ]; then
  for h in "$DOMINIO" "teste-dns.$DOMINIO"; do
    getent hosts "$h" >/dev/null || { echo "    O DNS de $h ainda não resolve (falta o registro ou o coringa *.$DOMINIO). Abortado."; exit 1; }
  done
fi
if ! ja_instalado; then
  : "${ORG_SLUG:?informe ORG_SLUG (identificador da organização inicial: minúsculas, números e hífen)}"
  : "${ORG_NOME:?informe ORG_NOME (nome da organização inicial)}"
  : "${GESTOR_EMAIL:?informe GESTOR_EMAIL (e-mail do Gestor da organização inicial)}"
  : "${GESTOR_LOGIN:?informe GESTOR_LOGIN (login curto do Gestor, sem e-mail)}"
else
  MODO_GRAVADO="$(val_env MODO_ACESSO "$DIR/backend/.env")"
  if [ -n "$MODO_GRAVADO" ] && [ "$MODO_GRAVADO" != "$MODO" ]; then
    echo "    Já instalado no modo '$MODO_GRAVADO' (pedido: '$MODO'). Para mudar de modo, siga docs/DEPLOY.md › Do IP para o domínio."
    exit 1
  fi
fi
echo "    Portas, pasta, site nginx e banco conferidos. OK."

# ------------------------------------------------------------------------------------------------------------------
echo "--- 2/11 Pacotes: instala só o que falta, sem atualizar o que existe"
FALTAM=""
PACOTES="git curl openssl nginx postgresql-client"
[ "$MODO" = "dominio" ] && PACOTES="$PACOTES certbot python3-certbot-nginx"
for pkg in $PACOTES; do
  dpkg -s "$pkg" >/dev/null 2>&1 || FALTAM="$FALTAM $pkg"
done
if [ -n "$FALTAM" ]; then
  echo "    instalando:$FALTAM"
  # shellcheck disable=SC2086
  apt-get install -y -qq --no-upgrade $FALTAM >/dev/null
fi
NPM_BIN="$(como 'command -v npm' || true)"
NODE_VER="$(como 'node -v' 2>/dev/null || echo v0)"
{ [ -n "$NPM_BIN" ] && [ "$(echo "$NODE_VER" | cut -d. -f1 | tr -d v)" -ge 20 ]; } || {
  echo "    Node.js >= 20 necessário para o usuário $USUARIO_DEPLOY (encontrado: $NODE_VER). Abortado."; exit 1; }
NODE_DIR="$(dirname "$NPM_BIN")"
echo "    Node $NODE_VER ($NODE_DIR)"
como 'command -v uv >/dev/null || [ -x ~/.local/bin/uv ] || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null'
UV="/home/$USUARIO_DEPLOY/.local/bin/uv"
[ -x "$UV" ] || UV="$(como 'command -v uv')"
echo "    uv $(como "'$UV' --version" | awk '{print $2}')"

# ------------------------------------------------------------------------------------------------------------------
echo "--- 3/11 Código ($BRANCH)"
if [ -d "$DIR/.git" ]; then
  echo "    já clonado em $DIR (atualizações: ./deploy/deploy.sh $AMB)"
else
  como "mkdir -p '$BASE_OS' && git clone -q -b '$BRANCH' '$REPO' '$DIR'"
  echo "    clonado em $DIR ($(git -C "$DIR" rev-parse --short HEAD))"
fi

# ------------------------------------------------------------------------------------------------------------------
echo "--- 4/11 PostgreSQL: usuário $ROLE (CREATEDB: o sistema cria o banco de cada organização) e banco $BANCO"
SENHA_BANCO=""
if psql_su -c "SELECT 1 FROM pg_roles WHERE rolname='$ROLE'" | grep -q 1; then
  if ja_instalado; then
    echo "    usuário $ROLE já existe (senha mantida, está no .env)"
    psql_su -q -c "ALTER ROLE $ROLE WITH LOGIN CREATEDB" >/dev/null
  else
    SENHA_BANCO="$(openssl rand -hex 24)"
    psql_su -q -c "ALTER ROLE $ROLE WITH LOGIN CREATEDB PASSWORD '$SENHA_BANCO'" >/dev/null
    echo "    usuário $ROLE já existia sem .env: senha nova gerada"
  fi
else
  SENHA_BANCO="$(openssl rand -hex 24)"
  psql_su -q -c "CREATE ROLE $ROLE WITH LOGIN CREATEDB PASSWORD '$SENHA_BANCO'" >/dev/null
  echo "    usuário $ROLE criado"
fi
if banco_existe "$BANCO"; then
  echo "    banco $BANCO já existe"
else
  psql_su -q -c "CREATE DATABASE $BANCO OWNER $ROLE ENCODING 'UTF8' TEMPLATE template0" >/dev/null
  echo "    banco $BANCO criado"
fi

# ------------------------------------------------------------------------------------------------------------------
echo "--- 5/11 Configuração de servidor (.env só com o que é de servidor; integrações e IA ficam nas telas)"
if ja_instalado; then
  echo "    backend/.env já existe: mantido (segredos não são trocados)"
  if [ -n "$SENHA_BANCO" ]; then   # o usuário do banco foi recriado: atualiza só a senha
    definir_env "$DIR/backend/.env" DATABASE_URL "postgresql+psycopg://$ROLE:$SENHA_BANCO@127.0.0.1:5432/$BANCO"
  fi
else
  if [ "$MODO" = "ip" ]; then
    # sem domínio: o Host é o IP (a porta não entra na conferência); sem subdomínio de organização
    HOSTS_JSON="[\"$IP\",\"127.0.0.1\"]"; BASE_DOM=""; PRINCIPAL="$IP"
  else
    HOSTS_JSON="[\"$DOMINIO\",\"*.$DOMINIO\",\"127.0.0.1\"]"; BASE_DOM="$DOMINIO"; PRINCIPAL="$DOMINIO"
  fi
  JWT="$(openssl rand -hex 48)"
  MASTER_KEY="$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  como "umask 077 && cat > '$DIR/backend/.env'" <<ENV
# Gerado por deploy/instalar.sh em $(date '+%d/%m/%Y %H:%M'). Credenciais de integração (IA, SMTP, WhatsApp...)
# NÃO entram aqui: são cadastradas nas telas, cifradas com a MASTER_KEY. GUARDE a MASTER_KEY num cofre.
AMBIENTE=$AMB
DEBUG=false
API_PORTA=$API_PORTA
WEB_PORTA=$WEB_PORTA
# acesso: ip (http://IP:IP_PORTA, sem HTTPS) ou dominio (HTTPS + <slug>.DOMINIO_BASE)
MODO_ACESSO=$MODO
IP_PUBLICO=${IP:-}
IP_PORTA=$IP_PORTA
DOMINIO_PRINCIPAL=$PRINCIPAL
DOMINIO_BASE=$BASE_DOM
DOMINIOS_EXTRAS=
ALLOWED_HOSTS=$HOSTS_JSON
CORS_ORIGINS=["$ENDERECO"]
FRONTEND_URL=$ENDERECO
DATABASE_URL=postgresql+psycopg://$ROLE:$SENHA_BANCO@127.0.0.1:5432/$BANCO
STORAGE_DIR=$DIR/backend/storage
JWT_SECRET=$JWT
MASTER_KEY=$MASTER_KEY
RATE_LIMIT_ATIVO=true
WORKER_EMBUTIDO=false
MIGRAR_NA_SUBIDA=false
ENV
  # Nomes de banco por ambiente: só quando o backend souber lê-los (docs/DEPLOY.md › Nomes dos bancos). Escrever num
  # ambiente já instalado com os nomes fixos desligaria o modo multi em silêncio.
  if grep -qi "banco_controle" "$DIR/backend/app/core/config.py"; then
    definir_env "$DIR/backend/.env" BANCO_CONTROLE "flicsalesos_controle_$AMB"
    definir_env "$DIR/backend/.env" BANCO_PREFIXO "flicsalesos_${AMB}_"
  fi
  echo "    backend/.env criado (modo 600)"
fi
# o frontend lê no build (NEXT_PUBLIC_*) e na execução (INTERNAL_API_URL, COOKIE_SECURE, WEB_PORTA pelo systemd)
COOKIE_LINHA=""
[ "$MODO" = "ip" ] && COOKIE_LINHA="COOKIE_SECURE=false"   # http puro: cookie Secure não seria gravado pelo navegador
como "umask 077 && cat > '$DIR/frontend/.env.production'" <<ENV
INTERNAL_API_URL=http://127.0.0.1:$API_PORTA/api
NEXT_PUBLIC_AMBIENTE=$AMB
NEXT_PUBLIC_VERSAO=$AMB
WEB_PORTA=$WEB_PORTA
$COOKIE_LINHA
ENV
como "mkdir -p '$DIR/backend/storage'"

# ------------------------------------------------------------------------------------------------------------------
echo "--- 6/11 Backend: dependências e migrations do banco principal"
como "cd '$DIR/backend' && '$UV' sync --frozen -q && '$UV' run python -m alembic upgrade head"

# ------------------------------------------------------------------------------------------------------------------
echo "--- 7/11 Banco de controle (liga o modo um banco por organização)"
ler_nomes_do_codigo
echo "    o backend usa: controle '$NOME_CONTROLE', organizações '${PREFIXO_ORG}<slug>'"
if [ "$NOME_CONTROLE" != "flicsalesos_controle_$AMB" ]; then
  # Nome fixo: o controle é do SERVIDOR, não do ambiente (o modo multi liga sozinho em quem achar o banco).
  for outro in hml prod; do
    [ "$outro" = "$AMB" ] && continue
    if [ -f "$BASE_OS/$outro/backend/.env" ]; then
      echo "    PARADO: o backend ainda usa o nome fixo '$NOME_CONTROLE' e o ambiente '$outro' já está instalado neste"
      echo "    PostgreSQL. Os dois ambientes passariam a ler o MESMO controle (organizações de um no outro)."
      echo "    Antes de instalar '$AMB', o backend precisa ler BANCO_CONTROLE/BANCO_PREFIXO do .env"
      echo "    (docs/DEPLOY.md › Nomes dos bancos). Nada do banco de controle foi alterado."
      exit 1
    fi
  done
fi
if banco_existe "$NOME_CONTROLE" && [ "$(dono_do_banco "$NOME_CONTROLE")" != "$ROLE" ]; then
  echo "    O banco $NOME_CONTROLE existe com outro dono ($(dono_do_banco "$NOME_CONTROLE")). Abortado."; exit 1
fi
como "cd '$DIR/backend' && '$UV' run python -m app.controle.cli ativar"

# ------------------------------------------------------------------------------------------------------------------
echo "--- 8/11 Organização inicial e Gestor"
if [ -z "$ORG_SLUG" ]; then
  echo "    ORG_SLUG não informado: nenhuma organização criada agora (organizações atuais abaixo)."
elif como "cd '$DIR/backend' && '$UV' run python -m app.controle.cli listar" | awk '{print $1}' | grep -qx "$ORG_SLUG"; then
  echo "    organização $ORG_SLUG já existe: nada a fazer"
else
  if [ "$MODO" = "ip" ] && [ "$(como "cd '$DIR/backend' && '$UV' run python -m app.controle.cli listar" | grep -c .)" -gt 0 ]; then
    echo "    Modo IP: já existe uma organização e o acesso por IP comporta só uma (sem subdomínio). Nada criado."
    ORG_SLUG=""
  fi
fi
if [ -n "$ORG_SLUG" ] && ! como "cd '$DIR/backend' && '$UV' run python -m app.controle.cli listar" | awk '{print $1}' | grep -qx "$ORG_SLUG"; then
  BANCO_ORG="${PREFIXO_ORG}${ORG_SLUG//-/_}"
  if banco_existe "$BANCO_ORG" && [ "$(dono_do_banco "$BANCO_ORG")" != "$ROLE" ]; then
    echo "    O banco $BANCO_ORG já existe e é de outro sistema ($(dono_do_banco "$BANCO_ORG")). Escolha outro ORG_SLUG."; exit 1
  fi
  : "${GESTOR_EMAIL:?informe GESTOR_EMAIL}"; : "${GESTOR_LOGIN:?informe GESTOR_LOGIN}"; : "${ORG_NOME:?informe ORG_NOME}"
  SENHA_GESTOR="Fs$(openssl rand -hex 7)9"   # letras e números (política da senha); o Gestor troca no primeiro acesso
  # grava ANTES de passar o dono: com fs.protected_regular (padrão no Ubuntu) o root não abre para escrita, em /tmp,
  # um arquivo de outro usuário
  ARQ_SENHA="$(mktemp)"; chmod 600 "$ARQ_SENHA"
  printf '%s\n' "$SENHA_GESTOR" > "$ARQ_SENHA"
  chown "$USUARIO_DEPLOY" "$ARQ_SENHA"
  # a senha vai pela entrada padrão (nunca na linha de comando, que aparece no `ps`)
  como "cd '$DIR/backend' && '$UV' run python -m app.controle.cli nova-organizacao --slug '$ORG_SLUG' \
    --nome '$ORG_NOME' --admin-email '$GESTOR_EMAIL' --admin-login '$GESTOR_LOGIN' --admin-nome '$GESTOR_NOME' \
    --senha-stdin < '$ARQ_SENHA'"
  rm -f "$ARQ_SENHA"
fi
como "cd '$DIR/backend' && '$UV' run python -m app.controle.cli listar" | sed 's/^/      /'

# ------------------------------------------------------------------------------------------------------------------
echo "--- 9/11 Frontend: dependências e build"
como "cd '$DIR/frontend' && npm ci --silent && npm run build >/dev/null"
[ -f "$DIR/frontend/.next/BUILD_ID" ] || { echo "    build terminou sem .next/BUILD_ID. Abortado."; exit 1; }
# o build reescreve o tsconfig.json; devolve ao estado do repositório (senão o deploy.sh para no passo 1)
como "cd '$DIR' && git checkout -q -- frontend/tsconfig.json 2>/dev/null || true"

# ------------------------------------------------------------------------------------------------------------------
echo "--- 10/11 Serviços (systemd): só flicsales-os-*; nenhum outro serviço é tocado"
for svc in api worker web certificados; do
  sed "s|__BASE__|$BASE_OS|g; s|__USUARIO__|$USUARIO_DEPLOY|g; s|__NODE_DIR__|$NODE_DIR|g" \
    "$DIR/deploy/systemd/flicsales-os-$svc@.service" > "/etc/systemd/system/flicsales-os-$svc@.service"
done
sed "s|__BASE__|$BASE_OS|g" "$DIR/deploy/systemd/flicsales-os-certificados@.timer" \
  > /etc/systemd/system/flicsales-os-certificados@.timer
systemctl daemon-reload
# shellcheck disable=SC2086
systemctl enable -q $SERVICOS
# shellcheck disable=SC2086
systemctl restart $SERVICOS
HORA=2; [ "$AMB" = "hml" ] && HORA=3
echo "0 $HORA * * * $USUARIO_DEPLOY $DIR/deploy/backup.sh $AMB >> $BASE_OS/backup-$AMB.log 2>&1" \
  > "/etc/cron.d/flicsales-os-backup-$AMB"
chmod 644 "/etc/cron.d/flicsales-os-backup-$AMB"
echo "    $SERVICOS ativos; backup diário às 0$HORA:00 (/etc/cron.d/flicsales-os-backup-$AMB)"

# ------------------------------------------------------------------------------------------------------------------
echo "--- 11/11 nginx (site $SITE_NGINX; o site 'flicsales' do sistema antigo e o default_server não são tocados)"
EMAIL_LETSENCRYPT="${EMAIL_LETSENCRYPT:-${GESTOR_EMAIL:-}}" bash "$DIR/deploy/certificados.sh" "$AMB"
if [ "$MODO" = "dominio" ]; then
  systemctl enable -q --now "flicsales-os-certificados@$AMB.timer"
else
  if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "$IP_PORTA/tcp" comment "flicsales-os $AMB" >/dev/null
    echo "    ufw ativo: porta $IP_PORTA/tcp liberada"
  else
    echo "    ufw inativo: nada a liberar no servidor (confira o firewall do painel da hospedagem)"
  fi
fi

CODIGO="$(esperar_200 "http://127.0.0.1:$API_PORTA/api/health")"
read -r CSS CSS_COD <<<"$(conferir_css "$WEB_PORTA")"
EXTERNO="$(curl -s -o /dev/null -w '%{http_code}' "$ENDERECO/api/health" || echo 000)"
echo
echo "=== Pronto: FlicSales OS $AMB (modo $MODO) ==="
echo "    API interna  /api/health -> HTTP $CODIGO"
echo "    Front        CSS $CSS -> HTTP $CSS_COD"
echo "    Externo      $ENDERECO/api/health -> HTTP $EXTERNO"
[ "$MODO" = "dominio" ] && [ "$EXTERNO" != "200" ] && echo "                 (certificado ainda não saiu? o timer tenta a cada 5 min)"
[ "$MODO" = "ip" ] && [ "$EXTERNO" != "200" ] && echo "                 (porta $IP_PORTA fechada no firewall da hospedagem?)"
if [ -n "${SENHA_GESTOR:-}" ]; then
  echo
  echo "    ================================================================"
  echo "    Gestor da organização $ORG_SLUG"
  if [ "$MODO" = "ip" ]; then
    echo "      endereço: $ENDERECO"
  else
    echo "      endereço: https://$ORG_SLUG.$DOMINIO  (ou $ENDERECO)"
  fi
  echo "      login:    $GESTOR_LOGIN"
  echo "      senha:    $SENHA_GESTOR"
  echo "    Mostrada SÓ AGORA (não foi gravada em lugar nenhum). Troque no primeiro acesso."
  echo "    ================================================================"
fi
echo "    GUARDE a MASTER_KEY (em $DIR/backend/.env) num cofre: sem ela os segredos cifrados precisam ser recadastrados."
echo "    Atualizações daqui em diante: cd $DIR && ./deploy/deploy.sh $AMB"
