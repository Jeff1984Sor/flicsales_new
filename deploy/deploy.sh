#!/usr/bin/env bash
#
# Deploy do FlicSales OS no servidor (VPS compartilhada: flicsales antigo, MayaJus, MayaFit e outros).
# Sempre os mesmos 7 passos, na mesma ordem. Em produção cria a tag vN (ponto de retorno do rollback).
# Nada vai para produção sem ter passado pela homologação.
#
# Uso (no servidor, como o usuário deploy):
#     cd /home/deploy/flicsales-os/hml  && ./deploy/deploy.sh hml              # branch develop
#     cd /home/deploy/flicsales-os/prod && ./deploy/deploy.sh prod             # branch main, cria a tag vN
#     ./deploy/deploy.sh prod --sem-tag      # publica sem criar versão
#     ./deploy/deploy.sh hml --so-front      # só recompila e troca o frontend (sem testes, migrations nem tag)
#
# Garantias:
#   - teste falhou        -> aborta ANTES de tocar em qualquer serviço
#   - build falhou        -> o site segue na versão anterior (compila em .next-novo)
#   - CSS não veio        -> volta o frontend anterior sozinho
#   - API não respondeu   -> diz exatamente como voltar (rollback.sh)
#   - só os serviços flicsales-os-* são reiniciados; nenhum outro sistema da VPS é tocado
#
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/comum.sh
. "$AQUI/comum.sh"
definir_ambiente "${1:-}"
shift || true

CRIAR_TAG=0
[ "$AMB" = "prod" ] && CRIAR_TAG=1
SO_FRONT=0
for a in "$@"; do
  case "$a" in
    --sem-tag) CRIAR_TAG=0 ;;
    --so-front) SO_FRONT=1; CRIAR_TAG=0 ;;
    *) echo "Opção desconhecida: $a (use --sem-tag ou --so-front)"; exit 1 ;;
  esac
done
BRANCH="${BRANCH_DEPLOY:-$BRANCH}"
APP="${APP_DIR:-$DIR}"
BACK="$APP/backend"
FRONT="$APP/frontend"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
LOG_TESTES="/tmp/flicsales-os-$AMB-testes.log"
LOG_BUILD="/tmp/flicsales-os-$AMB-build.log"

falha() { echo "    FALHOU: $1"; exit 1; }
[ "$(id -un)" = "$USUARIO_DEPLOY" ] || falha "rode como o usuário $USUARIO_DEPLOY (não root)"
cd "$APP" || falha "pasta $APP não existe (primeira vez? sudo bash deploy/instalar.sh $AMB)"
[ -f "$BACK/.env" ] || falha "$BACK/.env não existe (primeira vez? sudo bash deploy/instalar.sh $AMB)"
API_PORTA="$(val_env API_PORTA "$BACK/.env")"
WEB_PORTA="$(val_env WEB_PORTA "$BACK/.env")"

# ------------------------------------------------------------------------------------------------------------------
echo "=== 1/7  Situação atual ($AMB) ==="
VERSAO_ANTERIOR="$(cat "$BACK/VERSION" 2>/dev/null || echo sem-versao)"
COMMIT_ANTERIOR="$(git rev-parse --short HEAD)"
echo "    no ar: $VERSAO_ANTERIOR ($COMMIT_ANTERIOR)"
# HEAD solto = um rollback deixou o servidor numa tag. O deploy volta para a branch do ambiente.
if ! git symbolic-ref -q HEAD >/dev/null; then
  echo "    ATENÇÃO: HEAD solto (rollback anterior: $(cat .rollback-ativo 2>/dev/null || echo '?')). O deploy volta para '$BRANCH'."
  if [ -t 0 ]; then
    read -r -p "    Continuar? [s/N] " r
    [ "$r" = "s" ] || exit 1
  elif [ "${VOLTAR_PARA_BRANCH:-}" != "sim" ]; then
    falha "sem terminal: confirme com VOLTAR_PARA_BRANCH=sim ./deploy/deploy.sh $AMB"
  fi
fi
if [ -n "$(git status --porcelain -uno)" ]; then
  echo "    arquivos versionados alterados direto no servidor:"
  git status --short -uno | sed 's/^/      /'
  falha "resolva antes (git diff no servidor) — o pull sobrescreveria essas mudanças. Nada foi alterado."
fi

# ------------------------------------------------------------------------------------------------------------------
echo "=== 2/7  Código ($BRANCH) ==="
git fetch -q origin --tags || falha "git fetch"
git checkout -q "$BRANCH" || falha "git checkout $BRANCH"
git pull -q --ff-only origin "$BRANCH" || falha "git pull (histórico divergiu?)"
rm -f .rollback-ativo
COMMIT_NOVO="$(git rev-parse --short HEAD)"
# o bash lê o script enquanto executa: se este pull trouxe um deploy.sh (ou comum.sh) novo, o resto da execução seria
# a versão ANTIGA. Reinicia com a nova (lição do flicsales antigo, 25/10).
if [ -z "${DEPLOY_REEXEC:-}" ] && [ "$COMMIT_NOVO" != "$COMMIT_ANTERIOR" ] \
   && ! git diff --quiet "$COMMIT_ANTERIOR" "$COMMIT_NOVO" -- deploy/deploy.sh deploy/comum.sh; then
  echo "    deploy.sh mudou neste pull — reiniciando com a versão nova"
  DEPLOY_REEXEC=1 exec bash "$APP/deploy/deploy.sh" "$AMB" "$@"
fi
if [ "$COMMIT_NOVO" = "$COMMIT_ANTERIOR" ]; then
  echo "    nada novo em $BRANCH (republica $COMMIT_NOVO)"
else
  git log --oneline "$COMMIT_ANTERIOR..$COMMIT_NOVO" | sed 's/^/      /'
fi
# serviços: se os modelos do systemd mudaram neste pull, reinstala SÓ os flicsales-os-* (o restart vem no passo 7)
if [ "$COMMIT_NOVO" != "$COMMIT_ANTERIOR" ] && ! git diff --quiet "$COMMIT_ANTERIOR" "$COMMIT_NOVO" -- deploy/systemd; then
  NODE_DIR="$(dirname "$(command -v npm)")"
  for svc in api worker web certificados; do
    sed "s|__BASE__|$BASE_OS|g; s|__USUARIO__|$USUARIO_DEPLOY|g; s|__NODE_DIR__|$NODE_DIR|g" \
      "deploy/systemd/flicsales-os-$svc@.service" | sudo tee "/etc/systemd/system/flicsales-os-$svc@.service" >/dev/null
  done
  sed "s|__BASE__|$BASE_OS|g" deploy/systemd/flicsales-os-certificados@.timer \
    | sudo tee /etc/systemd/system/flicsales-os-certificados@.timer >/dev/null
  sudo systemctl daemon-reload
  echo "    unidades systemd flicsales-os-* atualizadas"
fi

# ------------------------------------------------------------------------------------------------------------------
if [ "$SO_FRONT" = "0" ]; then
  echo "=== 3/7  Backend: dependências e testes (gate: falhou, nada é reiniciado) ==="
  cd "$BACK" || falha "backend"
  "$UV" sync --frozen -q || falha "uv sync"
  if ! "$UV" run python -m pytest -q -x > "$LOG_TESTES" 2>&1; then
    tail -25 "$LOG_TESTES" | sed 's/^/      /'
    falha "testes — deploy abortado, NADA foi reiniciado (log: $LOG_TESTES)"
  fi
  echo "    $(tail -1 "$LOG_TESTES")"

  echo "=== 4/7  Migrations (principal, controle e o banco de CADA organização) ==="
  # (o .env é lido pela própria aplicação; não dar `source`: o bash corrompe valores com colchetes/aspas)
  "$UV" run python -m alembic check >/dev/null 2>&1 || echo "    (aviso: há modelo sem migration gerada, confira)"
  "$UV" run python -m alembic upgrade head || falha "alembic upgrade (banco principal) — nada foi reiniciado"
  "$UV" run python -m app.controle.cli migrar | sed 's/^/    /'
  [ "${PIPESTATUS[0]}" = "0" ] || falha "migração do controle/organizações — nada foi reiniciado; veja a mensagem acima"
  cd "$APP" || falha "pasta $APP"
else
  echo "=== 3-4/7  (só frontend: testes e migrations pulados) ==="
fi

# ------------------------------------------------------------------------------------------------------------------
if [ "$CRIAR_TAG" = "1" ]; then
  ULTIMA="$(git tag --list 'v[0-9]*' | sed 's/^v//' | grep -E '^[0-9]+$' | sort -n | tail -1)"
  VERSAO_NOVA="v$(( ${ULTIMA:-0} + 1 ))"
else
  VERSAO_NOVA="$AMB-$COMMIT_NOVO"
fi

echo "=== 5/7  Frontend: build em .next-novo (o site segue no ar) ==="
cd "$FRONT" || falha "frontend"
# npm ci apaga node_modules (que o site no ar usa): só quando o lock mudou ou a pasta não existe
if [ ! -d node_modules ] || { [ "$COMMIT_NOVO" != "$COMMIT_ANTERIOR" ] \
     && ! git -C "$APP" diff --quiet "$COMMIT_ANTERIOR" "$COMMIT_NOVO" -- frontend/package-lock.json; }; then
  echo "    package-lock mudou: npm ci"
  npm ci --silent >/dev/null 2>&1 || falha "npm ci"
fi
rm -rf .next-novo
if ! NEXT_DIST_DIR=.next-novo NEXT_PUBLIC_VERSAO="$VERSAO_NOVA" npm run build > "$LOG_BUILD" 2>&1; then
  sed 's/\x1b\[[0-9;]*m//g' "$LOG_BUILD" \
    | grep -E "Type error|Failed to compile|Error:|^\./|Unexpected" -A 4 | head -30 | sed 's/^/      /'
  rm -rf .next-novo
  git checkout -q -- tsconfig.json 2>/dev/null || true
  falha "build — o site SEGUE NO AR na versão anterior (log: $LOG_BUILD)"
fi
# o Next acrescenta o distDir ao tsconfig.json; devolve ao estado do repositório (senão o próximo deploy para no passo 1)
git checkout -q -- tsconfig.json 2>/dev/null || true
[ -f .next-novo/BUILD_ID ] || falha "build terminou sem BUILD_ID — nada foi trocado"
cd "$APP" || falha "pasta $APP"

# ------------------------------------------------------------------------------------------------------------------
echo "=== 6/7  Versão ==="
if [ "$CRIAR_TAG" = "1" ]; then
  git -c user.name="Deploy FlicSales OS" -c user.email="deploy@flicsales.com.br" \
    tag -a "$VERSAO_NOVA" -m "Deploy $VERSAO_NOVA ($AMB) em $(date '+%d/%m/%Y %H:%M')" || falha "git tag $VERSAO_NOVA"
  if git push -q origin "$VERSAO_NOVA" 2>/dev/null; then
    echo "    tag $VERSAO_NOVA publicada"
  else
    echo "    tag $VERSAO_NOVA só local (o rollback funciona igual)"
  fi
else
  echo "    sem tag: $VERSAO_NOVA"
fi
echo "$VERSAO_NOVA" > "$BACK/VERSION"

# ------------------------------------------------------------------------------------------------------------------
echo "=== 7/7  Trocando e reiniciando (só flicsales-os-*@$AMB) ==="
cd "$FRONT" || falha "pasta $FRONT"
rm -rf .next-anterior
[ -d .next ] && mv .next .next-anterior
mv .next-novo .next
cd "$APP" || falha "pasta $APP"

if [ "$SO_FRONT" = "0" ]; then
  # shellcheck disable=SC2086
  sudo systemctl restart $SERVICOS
  # endereços e HTTPS: aplica mudanças de deploy/nginx (só recarrega o nginx se mudou e o `nginx -t` aprovar)
  sudo bash "$APP/deploy/certificados.sh" "$AMB" || echo "    (aviso: certificados.sh falhou; o nginx segue com a configuração anterior)"
else
  sudo systemctl restart "flicsales-os-web@$AMB"
fi

API="$(esperar_200 "http://127.0.0.1:$API_PORTA/api/health")"
SAUDE="$(curl -s "http://127.0.0.1:$API_PORTA/api/health" 2>/dev/null || true)"
read -r CSS CSS_COD <<<"$(conferir_css "$WEB_PORTA")"
echo "    API /api/health: HTTP $API  $SAUDE"
echo "    site CSS $CSS: HTTP $CSS_COD"

if [ "$CSS" = "sem-css" ] || [ "$CSS_COD" != "200" ]; then
  echo "    frontend novo não serve o CSS — voltando o frontend para o anterior"
  if [ -d "$FRONT/.next-anterior" ]; then
    (cd "$FRONT" && rm -rf .next && mv .next-anterior .next)
    sudo systemctl restart "flicsales-os-web@$AMB"
    falha "frontend revertido para o anterior; investigar $LOG_BUILD e journalctl -u flicsales-os-web@$AMB -n 50"
  fi
  falha "frontend sem CSS e sem versão anterior para voltar: journalctl -u flicsales-os-web@$AMB -n 50"
fi
if [ "$API" != "200" ]; then
  falha "a API não respondeu (journalctl -u flicsales-os-api@$AMB -n 50). Para voltar: ./deploy/rollback.sh $AMB $VERSAO_ANTERIOR"
fi
if [ "$SO_FRONT" = "0" ] && ! echo "$SAUDE" | grep -q "\"$VERSAO_NOVA\""; then
  echo "    (aviso: /api/health não mostra $VERSAO_NOVA — a API reiniciou mesmo? systemctl status flicsales-os-api@$AMB)"
fi
# shellcheck disable=SC2086
systemctl is-active $SERVICOS | paste -sd' ' | sed 's/^/    serviços: /'
echo "    OK: $VERSAO_NOVA no ar em $AMB ($COMMIT_NOVO). Antes: $VERSAO_ANTERIOR."
