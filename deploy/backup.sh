#!/usr/bin/env bash
# Backup diário do FlicSales OS: um pg_dump por banco do ambiente + os arquivos (storage). Retenção de 30 dias.
#
#   ./deploy/backup.sh hml        (como o usuário deploy)
#
# Cron (o instalar.sh já grava em /etc/cron.d/flicsales-os-backup-<amb>):
#   0 2 * * * deploy /home/deploy/flicsales-os/prod/deploy/backup.sh prod >> /home/deploy/flicsales-os/backup-prod.log 2>&1
#   0 3 * * * deploy /home/deploy/flicsales-os/hml/deploy/backup.sh hml   >> /home/deploy/flicsales-os/backup-hml.log 2>&1
#
# Quais bancos: TODOS os que pertencem ao usuário do PostgreSQL do ambiente (flicsalesos_<amb>): o principal, o de
# controle e o de cada organização (criados pelo próprio sistema com esse usuário). Nunca por LIKE 'flicsales%': o
# sistema antigo, no mesmo servidor, usa "flicsales" e "flicsales_test" e não é backup deste script.
#
# O .env (com a MASTER_KEY) NÃO vai junto: guarde a MASTER_KEY num cofre à parte. BACKUP_INCLUIR_ENV=1 grava um tar do
# .env (modo 600) só no servidor. Cópia para fora do servidor: BACKUP_BUCKET=gs://... com gcloud instalado.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/comum.sh
. "$AQUI/comum.sh"
definir_ambiente "${1:-}"
DESTINO="${BACKUP_DIR:-/home/$USUARIO_DEPLOY/backups/flicsales-os/$AMB}"
ENV_FILE="$DIR/backend/.env"
RETENCAO_DIAS="${RETENCAO_DIAS:-30}"

[ -f "$ENV_FILE" ] || { echo "Não achei $ENV_FILE."; exit 1; }
DATABASE_URL="$(val_env DATABASE_URL "$ENV_FILE")"
URL="${DATABASE_URL/+psycopg/}"            # pg_dump/psql não conhecem o "+psycopg" do SQLAlchemy
STORAGE="$(val_env STORAGE_DIR "$ENV_FILE")"
STORAGE="${STORAGE:-$DIR/backend/storage}"
umask 077
mkdir -p "$DESTINO"
QUANDO="$(date +%Y%m%d-%H%M)"

BANCOS="$(psql "$URL" -tAc "SELECT datname FROM pg_database
  WHERE pg_get_userbyid(datdba) = current_user AND NOT datistemplate ORDER BY 1")"
[ -n "$BANCOS" ] || { echo "Nenhum banco do usuário do ambiente encontrado. Backup abortado."; exit 1; }
N=0
for b in $BANCOS; do
  arq="$DESTINO/banco_${b}_$QUANDO.dump"
  pg_dump "${URL%/*}/$b" -Fc -f "$arq"
  pg_restore -l "$arq" >/dev/null   # um backup que não restaura não é backup
  N=$((N + 1))
done

if [ -d "$STORAGE" ]; then
  tar -czf "$DESTINO/arquivos_$QUANDO.tar.gz" -C "$(dirname "$STORAGE")" "$(basename "$STORAGE")"
  tar -tzf "$DESTINO/arquivos_$QUANDO.tar.gz" >/dev/null
  TAM="$(du -sh "$STORAGE" | cut -f1)"
else
  TAM="0 (pasta $STORAGE ainda não existe)"
fi
if [ "${BACKUP_INCLUIR_ENV:-0}" = "1" ]; then
  tar -czf "$DESTINO/env_$QUANDO.tar.gz" -C "$DIR/backend" .env
fi
if [ -n "${BACKUP_BUCKET:-}" ] && command -v gcloud >/dev/null; then
  gcloud storage cp -q "$DESTINO"/*_"$QUANDO".* "$BACKUP_BUCKET/$AMB/$QUANDO/"
fi
find "$DESTINO" -type f -mtime +"$RETENCAO_DIAS" -delete
echo "Backup $AMB $QUANDO ok: $N banco(s) [$(echo "$BANCOS" | paste -sd' ')] + $TAM de arquivos em $DESTINO"
