#!/usr/bin/env bash
# Volta um ambiente para uma versão anterior:      ./deploy/rollback.sh prod v7
# Depois de resolver o problema, volta para a branch: ./deploy/rollback.sh prod --retomar
#
# NÃO desfaz migrations (nem do principal, nem do controle, nem das organizações): se a versão nova criou colunas ou
# tabelas, elas ficam e o código antigo as ignora. Se a migration nova for incompatível com o código antigo, rollback
# não resolve: corrija para a frente (deploy novo).
#
# O rollback deixa o repositório com HEAD solto na tag (é o que "estar na versão vN" significa). Para não esquecer:
#   - grava .rollback-ativo (com a branch de origem) e imprime um aviso;
#   - o próximo ./deploy/deploy.sh avisa e volta sozinho para a branch;
#   - --retomar volta para a branch sem fazer deploy novo.
# Só os serviços flicsales-os-*@<amb> são reiniciados.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/comum.sh
. "$AQUI/comum.sh"
definir_ambiente "${1:-}"
ARG="${2:?versão (ex.: v7) ou --retomar}"
APP="${APP_DIR:-$DIR}"
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
[ "$(id -un)" = "$USUARIO_DEPLOY" ] || { echo "Rode como o usuário $USUARIO_DEPLOY."; exit 1; }
cd "$APP"

if [ "$ARG" = "--retomar" ]; then
  ORIGEM="$(cut -d' ' -f1 .rollback-ativo 2>/dev/null || echo "$BRANCH")"
  git checkout -q "$ORIGEM"
  rm -f .rollback-ativo
  echo "Repositório de volta na branch $ORIGEM. Rode ./deploy/deploy.sh $AMB para publicar o que está nela."
  exit 0
fi

VERSAO="$ARG"
if ! git rev-parse -q --verify "refs/tags/$VERSAO" >/dev/null; then
  git fetch -q origin --tags 2>/dev/null || true
fi
if ! git rev-parse -q --verify "refs/tags/$VERSAO" >/dev/null; then
  echo "Tag $VERSAO não existe. Últimas:"
  git tag --list 'v*' | sort -V | tail -5
  exit 1
fi
if [ -n "$(git status --porcelain -uno)" ]; then
  echo "Arquivos versionados alterados no servidor; resolva antes:"; git status --short -uno; exit 1
fi
ANTES="$(cat backend/VERSION 2>/dev/null || echo '?')"
COMMIT_ANTES="$(git rev-parse HEAD)"
ORIGEM="$(git symbolic-ref -q --short HEAD || cut -d' ' -f1 .rollback-ativo 2>/dev/null || echo "$BRANCH")"
echo "=== Rollback $AMB: $ANTES -> $VERSAO (migrations NÃO são desfeitas) ==="
git checkout -q "$VERSAO"
echo "$ORIGEM $VERSAO" > .rollback-ativo

echo "--- backend: dependências da $VERSAO"
(cd backend && "$UV" sync --frozen -q)

echo "--- frontend: build da $VERSAO em .next-novo (o site segue no ar)"
cd frontend
if [ ! -d node_modules ] || ! git diff --quiet "$COMMIT_ANTES" HEAD -- package-lock.json; then
  npm ci --silent >/dev/null 2>&1
fi
rm -rf .next-novo
if ! NEXT_DIST_DIR=.next-novo NEXT_PUBLIC_VERSAO="$VERSAO" npm run build > "/tmp/flicsales-os-$AMB-build.log" 2>&1; then
  rm -rf .next-novo
  git checkout -q -- tsconfig.json 2>/dev/null || true
  echo "Build da $VERSAO falhou (/tmp/flicsales-os-$AMB-build.log). O frontend segue no anterior; o código está em $VERSAO."
  exit 1
fi
git checkout -q -- tsconfig.json 2>/dev/null || true
rm -rf .next-anterior
[ -d .next ] && mv .next .next-anterior
mv .next-novo .next
cd ..

echo "$VERSAO" > backend/VERSION
# shellcheck disable=SC2086
sudo systemctl restart $SERVICOS
API_PORTA="$(val_env API_PORTA backend/.env)"
WEB_PORTA="$(val_env WEB_PORTA backend/.env)"
CODIGO="$(esperar_200 "http://127.0.0.1:$API_PORTA/api/health")"
read -r CSS CSS_COD <<<"$(conferir_css "$WEB_PORTA")"
echo "/api/health: HTTP $CODIGO  $(curl -s "http://127.0.0.1:$API_PORTA/api/health" || true)"
echo "CSS $CSS: HTTP $CSS_COD"
echo
echo "================================================================"
echo " ATENÇÃO: $AMB está em $VERSAO com o repositório em HEAD SOLTO."
echo " Não faça commits aqui. Quando o problema for resolvido:"
echo "     ./deploy/rollback.sh $AMB --retomar    (volta para a branch $ORIGEM)"
echo "     ./deploy/deploy.sh $AMB                (publica a versão corrigida)"
echo "================================================================"
[ "$CODIGO" = "200" ] || { echo "A API não respondeu após o rollback. Confira: journalctl -u flicsales-os-api@$AMB -n 50"; exit 1; }
[ "$CSS_COD" = "200" ] || { echo "O site não serve o CSS após o rollback. Confira: journalctl -u flicsales-os-web@$AMB -n 50"; exit 1; }
