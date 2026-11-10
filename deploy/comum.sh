# shellcheck shell=bash
#
# Nomes e endereços do FlicSales OS no servidor. Lido (source) pelos outros scripts de deploy/; não rode direto.
#
# Servidor compartilhado: roda também o flicsales ANTIGO (~/flicsales, portas 10001/10002, site nginx "flicsales"),
# MayaJus, MayaFit e outros. Tudo que é deste sistema começa com "flicsales-os" (pasta, serviços, site nginx, cron)
# ou "flicsalesos" (bancos e usuário do PostgreSQL). Nada fora desses nomes é alterado.

USUARIO_DEPLOY=deploy
BASE_OS=/home/$USUARIO_DEPLOY/flicsales-os            # NÃO é ~/flicsales (esse é o sistema antigo)
export REPO_PADRAO=https://github.com/Jeff1984Sor/flicsales_new.git

# definir_ambiente hml|prod -> AMB BRANCH API_PORTA WEB_PORTA IP_PORTA MODO_PADRAO DOMINIO_PADRAO DIR BANCO ROLE SITE_NGINX SERVICOS
definir_ambiente() {
  AMB="${1:-}"
  # MODO_PADRAO: "ip" = acesso por http://<IP>:<IP_PORTA> (nginx numa porta própria, sem domínio nem HTTPS);
  #              "dominio" = endereços com HTTPS (certbot) e organizações em <slug>.<domínio>.
  # hml sobe por IP (decisão do Jefferson, 10/11/2026); prod e o futuro usam domínio.
  case "$AMB" in
    hml)  BRANCH=develop; API_PORTA=10073; WEB_PORTA=10074; IP_PORTA=10075; MODO_PADRAO=ip
          DOMINIO_PADRAO=hml.flicsales.com.br ;;
    # prod nasce em os.flicsales.com.br; flicsales.com.br só depois de deploy/trocar-dominio.sh (ordem explícita)
    prod) BRANCH=main;    API_PORTA=10071; WEB_PORTA=10072; IP_PORTA=10076; MODO_PADRAO=dominio
          DOMINIO_PADRAO=os.flicsales.com.br ;;
    *) echo "Ambiente inválido: '${AMB}' (use hml ou prod)."; exit 1 ;;
  esac
  DIR="$BASE_OS/$AMB"
  BANCO="flicsalesos_$AMB"          # banco principal (DATABASE_URL); no modo multi fica praticamente vazio
  ROLE="flicsalesos_$AMB"           # usuário do PostgreSQL deste ambiente (com CREATEDB)
  SITE_NGINX="flicsales-os-$AMB"
  SERVICOS="flicsales-os-api@$AMB flicsales-os-worker@$AMB flicsales-os-web@$AMB"
  # exportadas para os scripts que fazem source deste arquivo (shellcheck não vê o uso entre arquivos)
  export AMB BRANCH API_PORTA WEB_PORTA IP_PORTA MODO_PADRAO DOMINIO_PADRAO DIR BANCO ROLE SITE_NGINX SERVICOS
}

# valor de uma chave num arquivo .env (sem dar `source`: o bash corrompe valores com colchetes e aspas)
val_env() { grep -E "^$1=" "$2" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' || true; }

# grava/troca CHAVE=valor num .env, preservando o resto do arquivo
definir_env() {  # definir_env ARQUIVO CHAVE VALOR
  local arq="$1" chave="$2" valor="$3" tmp
  tmp="$(mktemp)"
  grep -vE "^$chave=" "$arq" > "$tmp" || true
  printf '%s=%s\n' "$chave" "$valor" >> "$tmp"
  cat "$tmp" > "$arq"   # mantém dono e permissão (600) do original
  rm -f "$tmp"
}

# Nomes de banco que o BACKEND usa de fato (lidos do código, não do que gostaríamos):
#   NOME_CONTROLE  banco de controle (organizações, domínios, catálogo de logins)
#   PREFIXO_ORG    prefixo do banco de cada organização (<prefixo><slug com _>)
# Hoje o código tem nomes fixos (flicsales_controle / flicsales_<slug>); ver docs/DEPLOY.md › "Nomes dos bancos".
# Precisa do venv e do backend/.env do ambiente prontos.
ler_nomes_do_codigo() {  # ler_nomes_do_codigo [usuario]
  local saida py="$DIR/backend/.venv/bin/python"
  local cmd="cd '$DIR/backend' && '$py' -c 'from app.core import tenancy; from app.controle import service; print(tenancy.BANCO_CONTROLE, service.nome_do_banco(\"x\")[:-1])'"
  if [ "$(id -un)" = "$USUARIO_DEPLOY" ]; then
    saida="$(bash -c "$cmd")"
  else
    saida="$(sudo -u "$USUARIO_DEPLOY" -H bash -c "$cmd")"
  fi
  NOME_CONTROLE="${saida%% *}"
  PREFIXO_ORG="${saida##* }"
  [ -n "$NOME_CONTROLE" ] && [ -n "$PREFIXO_ORG" ] || { echo "Não consegui ler os nomes de banco do backend."; exit 1; }
  export NOME_CONTROLE PREFIXO_ORG
}

# psql como superusuário local (só leitura de catálogo ou criação dos objetos deste sistema)
psql_su() { sudo -u postgres psql -v ON_ERROR_STOP=1 -tA "$@"; }
banco_existe() { psql_su -c "SELECT 1 FROM pg_database WHERE datname='$1'" | grep -q 1; }
dono_do_banco() { psql_su -c "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='$1'"; }

# Bancos deste ambiente: principal + controle + o de cada organização registrada no controle.
# (Lista explícita, nunca LIKE 'flicsales%': o sistema antigo usa "flicsales" e "flicsales_test" no mesmo servidor.)
bancos_do_ambiente() {
  echo "$BANCO"
  if banco_existe "$NOME_CONTROLE" && [ "$(dono_do_banco "$NOME_CONTROLE")" = "$ROLE" ]; then
    echo "$NOME_CONTROLE"
    psql_su -d "$NOME_CONTROLE" -c "SELECT banco FROM organizacao WHERE banco IS NOT NULL ORDER BY id"
  fi
}

# espera a URL responder 200 (até ~60 s): serviço recém-reiniciado leva alguns segundos para subir
esperar_200() {  # esperar_200 URL -> imprime o último código HTTP
  local cod=000 _i
  for _i in $(seq 1 30); do
    cod="$(curl -s -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || true)"
    [ "$cod" = "200" ] && break
    sleep 2
  done
  echo "${cod:-000}"
}

# confere que a página de login referencia um CSS e que ele é servido (HTTP 200 sozinho não prova nada:
# a página de erro do Next também é 200). Imprime "<caminho do css> <código>".
conferir_css() {  # conferir_css PORTA_WEB
  local html css="" cod=000 _i
  for _i in $(seq 1 30); do
    html="$(curl -s "http://127.0.0.1:$1/login" 2>/dev/null || true)"
    css="$(echo "$html" | grep -o '/_next/static/[^"]*\.css' | head -1 || true)"
    if [ -n "$css" ]; then
      cod="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$1$css" 2>/dev/null || true)"
      [ "$cod" = "200" ] && break
    fi
    sleep 2
  done
  echo "${css:-sem-css} ${cod:-000}"
}
