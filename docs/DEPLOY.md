# Deploy do FlicSales OS

Pacote em `deploy/`, adaptado do MayaFit (comprovado no mesmo servidor) e do ritual do flicsales antigo
(`.next-novo`, conferência de CSS, reexecução quando o `deploy.sh` muda no pull). **Nada aqui foi executado no
servidor**: este documento é o roteiro para quando o Jefferson mandar.

## O servidor

VPS compartilhada Ubuntu 24.04 (`ssh flicsales`, usuário `deploy` com sudo), PostgreSQL 16, nginx 1.24, Python 3.12,
Node 20. Também rodam: **flicsales ANTIGO** (`~/flicsales`, portas 10001/10002, site nginx `flicsales`, que tem o
`default_server`/catch-all da porta 80 e responde por flicsales.com.br), MayaJus (10021/22), MayaFit (10061/62) e outros.

Regra de convivência: tudo do OS se chama `flicsales-os*` (pasta, serviços, site nginx, cron, timer) ou `flicsalesos*`
(usuário e banco principal do PostgreSQL). Os scripts **nunca** reiniciam serviço que não seja `flicsales-os-*`,
**nunca** alteram o site `flicsales` (exceto `trocar-dominio.sh`, com ordem explícita) e sempre rodam `nginx -t` antes
de recarregar (se falhar, voltam o arquivo anterior). Certbot só para nomes deste sistema.

| | hml | prod |
|---|---|---|
| Pasta | `/home/deploy/flicsales-os/hml` | `/home/deploy/flicsales-os/prod` |
| Branch | `develop` | `main` + tag `vN` a cada deploy |
| API / web (127.0.0.1) | 10073 / 10074 | 10071 / 10072 |
| Acesso | **modo IP**: `http://2.25.130.240:10075` | **modo domínio**: `https://os.flicsales.com.br` → depois `https://flicsales.com.br` |
| Serviços | `flicsales-os-{api,worker,web}@hml` | `flicsales-os-{api,worker,web}@prod` (+ timer `flicsales-os-certificados@prod`) |
| Banco principal / usuário PG | `flicsalesos_hml` | `flicsalesos_prod` |
| Site nginx | `flicsales-os-hml` (porta 10075) | `flicsales-os-prod` (80/443, por nome) |
| Backup (cron) | 03:00 → `/home/deploy/backups/flicsales-os/hml` | 02:00 → `/home/deploy/backups/flicsales-os/prod` |

## Arquivos

| Arquivo | O que faz |
|---|---|
| `deploy/comum.sh` | nomes, portas e funções comuns (lido pelos outros; não roda sozinho) |
| `deploy/instalar.sh <amb>` | primeira instalação, idempotente (11 passos; detalhes no topo do arquivo) |
| `deploy/deploy.sh <amb> [--so-front] [--sem-tag]` | atualização nos 7 passos |
| `deploy/rollback.sh <amb> vN` / `--retomar` | volta para uma tag (não desfaz migration) |
| `deploy/backup.sh <amb>` | pg_dump de todos os bancos do ambiente + storage, retenção 30 dias |
| `deploy/certificados.sh <amb>` | gera o site nginx (modo IP ou domínio), certificados só dos nomes do OS |
| `deploy/trocar-dominio.sh` | troca flicsales.com.br para o OS (`--simular`, `CONFIRMO=sim`, `--reverter`) |
| `deploy/systemd/*` | modelos `flicsales-os-{api,worker,web,certificados}@.service` + timer |
| `deploy/nginx/flicsales-os-locations.conf` | o que cada endereço serve: páginas e `/bff/*` → Next; `/api/{health,webhooks,arquivos-publicos}` → API; resto de `/api/` = 404 |

Mudanças fora de `deploy/` feitas para o deploy: `frontend/next.config.ts` ganhou
`distDir: process.env.NEXT_DIST_DIR || ".next"` (build em `.next-novo` com o site no ar — testado localmente: os dois
builds passam) e o `.gitignore` ignora `.next-novo/`, `.next-anterior/` e `.rollback-ativo`. O Next reescreve o
`tsconfig.json` ao compilar em outra pasta; os scripts devolvem o arquivo ao estado do repositório após o build.

## Modos de acesso

**IP** (`MODO_ACESSO=ip`, o hml por decisão do Jefferson em 10/11/2026): um server nginx **só na porta própria**
(10075 no hml; 10076 reservada a prod), `server_name _` — é o único server dessa porta, então não interfere na porta 80
nem no `default_server` do antigo. Sem certbot, sem HSTS, `COOKIE_SECURE=false` no `frontend/.env.production`,
`FRONTEND_URL`/`CORS_ORIGINS` = `http://IP:10075`, `ALLOWED_HOSTS` = `["IP","127.0.0.1"]` (a API confere o Host sem a
porta). O nginx repassa `X-Forwarded-Host $http_host` (com a porta) porque o BFF compara o Origin com ele.
Multi-tenant por subdomínio não existe por IP: **uma organização só**, achada pelo catálogo de login (o instalador
recusa criar uma segunda nesse modo). A porta é liberada no `ufw` **só se o ufw estiver ativo**; o firewall do painel
da hospedagem (Hostinger) precisa liberar a 10075/tcp à parte, se houver.
Atenção: cookie não separa por porta. No mesmo IP, os cookies `flicsales_access`/`flicsales_refresh` do hml são
visíveis para outros sistemas servidos por esse IP (o antigo em http://IP). Aceitável para homologação; não use modo IP
em produção.

**Domínio** (`MODO_ACESSO=dominio`, prod e o futuro): `DOMINIO_PRINCIPAL` + `<slug>.DOMINIO_BASE` por organização,
HTTPS por certificado individual (desafio HTTP, webroot `/var/www/flicsales-os-acme`); o timer a cada 5 min pega
organizações novas (no máximo uma tentativa por hora por nome).

## DNS que precisa existir

- hml agora: **nenhum** (modo IP). Só a porta 10075 aberta.
- prod: `os.flicsales.com.br` A → IP da VPS e o coringa `*.os.flicsales.com.br` A → IP da VPS (o instalador confere
  `teste-dns.os.flicsales.com.br`).
- troca de domínio: `antigo.flicsales.com.br` A → IP da VPS; `flicsales.com.br` e `www` já apontam; para organizações
  em `<slug>.flicsales.com.br`, o coringa `*.flicsales.com.br` (registros específicos como `app`/`admin` do antigo
  continuam valendo por cima do coringa).
- hml com domínio no futuro: `hml.flicsales.com.br` e `*.hml.flicsales.com.br`.

## Nomes dos bancos (pendência do backend — bloqueia instalar prod)

O pedido era `flicsalesos_controle_<amb>` e `flicsalesos_<amb>_<slug>`. O backend hoje tem **nomes fixos**:
controle `flicsales_controle` (`app/core/tenancy.py: BANCO_CONTROLE`) e organização `flicsales_<slug>`
(`app/controle/service.py: nome_do_banco`), no mesmo servidor do `DATABASE_URL`. E o modo multi **liga sozinho** em
quem achar o banco de controle. Consequências no servidor compartilhado:

1. hml e prod no mesmo PostgreSQL leriam o **mesmo** controle. Por isso o `instalar.sh` lê os nomes do próprio código
   e **para** se o outro ambiente já estiver instalado com nome fixo. Hoje dá para instalar **um** ambiente (o hml);
   prod fica bloqueado até a correção abaixo. (O MayaFit resolveu do mesmo jeito: só um ambiente multi por servidor.)
2. O antigo usa os bancos `flicsales` e `flicsales_test`: uma organização com slug `test` cairia em `flicsales_test`.
   O instalador recusa banco existente de outro dono; o backup lista bancos **pelo dono** (o usuário do ambiente),
   nunca por `LIKE 'flicsales%'`.

**Correção proposta** (dono: Fundação/core; pequena e compatível com dev/testes):
`Settings.banco_controle: str = "flicsales_controle"` e `Settings.banco_prefixo: str = "flicsales_"`;
`tenancy.BANCO_CONTROLE` passa a vir de `settings.banco_controle`; `service.nome_do_banco` usa
`settings.banco_prefixo`. Quando entrar, o `instalar.sh` grava sozinho `BANCO_CONTROLE=flicsalesos_controle_<amb>` e
`BANCO_PREFIXO=flicsalesos_<amb>_` nos ambientes novos. O hml já instalado com nomes fixos migra assim (janela curta,
serviços do hml parados): `ALTER DATABASE flicsales_controle RENAME TO flicsalesos_controle_hml;`
`ALTER DATABASE flicsales_<slug> RENAME TO flicsalesos_hml_<slug>;` `UPDATE organizacao SET banco = ...` no controle;
acrescentar as duas chaves ao `.env`; subir os serviços. Sem isso, escrever as chaves num `.env` antigo desligaria o
multi em silêncio — por isso o instalador só as grava quando o código as entende.

## Primeira instalação — hml (modo IP)

No servidor, como `deploy` (o instalador clona o repositório sozinho em `/home/deploy/flicsales-os/hml`; para rodá-lo,
basta uma cópia descartável do repositório):

```bash
ssh flicsales
git clone -q -b develop https://github.com/Jeff1984Sor/flicsales_new.git /tmp/flicsales-os-instalador
sudo IP=2.25.130.240 ORG_SLUG=demo ORG_NOME="FlicSales Demo" \
     GESTOR_EMAIL=<email do Jefferson> GESTOR_LOGIN=jefferson GESTOR_NOME="Jefferson Fernandes" \
     bash /tmp/flicsales-os-instalador/deploy/instalar.sh hml
rm -rf /tmp/flicsales-os-instalador
```

O que acontece (para em qualquer erro; rodar de novo completa o que faltou):
1. confere portas 10073/10074/10075 livres, pasta, site nginx, banco — nada é alterado;
2. instala só pacotes que faltam (`--no-upgrade`), confere Node ≥ 20 e `uv`;
3. clona `develop`;
4. cria o usuário PG `flicsalesos_hml` (LOGIN CREATEDB, senha aleatória) e o banco `flicsalesos_hml`;
5. gera `backend/.env` (600) com `AMBIENTE`, `DATABASE_URL`, `JWT_SECRET`, `MASTER_KEY` aleatórios, hosts/CORS/URL do
   modo — **nenhuma credencial de integração** (IA, SMTP, WhatsApp vão nas telas) — e `frontend/.env.production`
   (`INTERNAL_API_URL`, `NEXT_PUBLIC_AMBIENTE`, `NEXT_PUBLIC_VERSAO`, `WEB_PORTA`, `COOKIE_SECURE=false`);
6. `uv sync --frozen` + `alembic upgrade head`;
7. confere os nomes de banco do código (seção acima) e `python -m app.controle.cli ativar` (cria o controle);
8. `cli nova-organizacao` (banco próprio + Gestor) com senha aleatória passada por stdin e **mostrada uma vez** no fim;
9. `npm ci` + `npm run build`;
10. instala e liga `flicsales-os-{api,worker,web}@hml`, cron de backup;
11. `certificados.sh hml` gera o site `flicsales-os-hml` na porta 10075 (`nginx -t` antes do reload) e abre a porta no
    ufw se ele estiver ativo. Confere `/api/health`, CSS e o acesso externo.

Depois: guarde a `MASTER_KEY` (`/home/deploy/flicsales-os/hml/backend/.env`) num cofre; entre em
`http://2.25.130.240:10075` com o Gestor e troque a senha; configure IA/e-mail nas telas.

## Primeira instalação — prod (modo domínio)

Pré-requisitos: correção dos nomes de banco (seção acima) integrada na `main`; DNS `os.flicsales.com.br` e
`*.os.flicsales.com.br`; o mesmo código conferido no hml; ordem do Jefferson.

```bash
git clone -q -b main https://github.com/Jeff1984Sor/flicsales_new.git /tmp/flicsales-os-instalador
sudo MODO=dominio ORG_SLUG=<slug> ORG_NOME="<Nome>" GESTOR_EMAIL=<email> GESTOR_LOGIN=<login> \
     EMAIL_LETSENCRYPT=<email> bash /tmp/flicsales-os-instalador/deploy/instalar.sh prod
```
Igual ao hml, mais: certificados de `os.flicsales.com.br` e `<slug>.os.flicsales.com.br` e o timer
`flicsales-os-certificados@prod`. Primeira tag sai no primeiro `deploy.sh prod`.

## Dia a dia

```bash
cd /home/deploy/flicsales-os/hml  && ./deploy/deploy.sh hml [--so-front]
cd /home/deploy/flicsales-os/prod && ./deploy/deploy.sh prod            # cria vN
./deploy/rollback.sh prod v7 ; ./deploy/rollback.sh prod --retomar
./deploy/backup.sh prod
```
`deploy.sh`: 1 situação (para com arquivo versionado alterado no servidor; HEAD solto pede confirmação) → 2 código
(`pull --ff-only`; se o próprio `deploy.sh` mudou, reexecuta a versão nova; reinstala unidades systemd se mudaram) →
3 testes (abortam antes de reiniciar) → 4 migrations do principal, do controle e de **cada organização**
(`cli migrar`) → 5 build em `.next-novo` (`npm ci` só se o lock mudou) → 6 tag vN só em prod → 7 troca as pastas,
reinicia só `flicsales-os-*@amb`, conferência de `/api/health` (versão) e do CSS servido de verdade; sem CSS, volta o
front anterior sozinho. Skills: `deploy-hml`, `deploy-prod`, `rollback`, `saude`; agente `publicador`.

### Do IP para o domínio (hml, quando houver DNS)
Com `hml.flicsales.com.br` e o coringa apontados: no `backend/.env` trocar `MODO_ACESSO=dominio`,
`DOMINIO_PRINCIPAL=DOMINIO_BASE=hml.flicsales.com.br`, `ALLOWED_HOSTS=["hml.flicsales.com.br","*.hml.flicsales.com.br","127.0.0.1"]`,
`CORS_ORIGINS`/`FRONTEND_URL` para `https://hml.flicsales.com.br`; tirar `COOKIE_SECURE=false` do
`frontend/.env.production`; `cli dominio --slug <slug> --host <slug>.hml.flicsales.com.br`;
`sudo bash deploy/certificados.sh hml` (gera o site por nome; o server da 10075 sai) e
`sudo systemctl enable --now flicsales-os-certificados@hml.timer`; reiniciar `flicsales-os-*@hml`; fechar a 10075 no ufw.

## Troca de flicsales.com.br (etapa separada, só com ordem explícita)

```bash
sudo bash /home/deploy/flicsales-os/prod/deploy/trocar-dominio.sh --simular         # mostra o plano, não altera nada
sudo CONFIRMO=sim bash /home/deploy/flicsales-os/prod/deploy/trocar-dominio.sh      # executa
sudo CONFIRMO=sim bash .../trocar-dominio.sh --reverter /home/deploy/flicsales-os/troca-dominio/<data>
```
Faz: conferências (prod no ar em modo domínio, `nginx -t` já passando, DNS de `antigo.flicsales.com.br`) → backup da
conf/links do site `flicsales`, do site do OS e do `.env` → site `flicsales-antigo` (`antigo.flicsales.com.br` →
10001/10002, certificado só desse nome) → `.env` do OS com `flicsales.com.br` (+ `www` e `os.` como extras) e
`<slug>.flicsales.com.br` em cada organização → **desativa** o site `flicsales` (só o link em `sites-enabled`; o arquivo
fica) e regera o site do OS (`nginx -t` antes) → reinicia só `flicsales-os-api@prod`/`worker@prod` → confere
`https://flicsales.com.br/api/health` e o antigo. Qualquer falha reverte sozinho. O `--simular` lista os `server_name`
e `location` do site antigo real: confira se o site de convivência (só `/` e `/api/`) cobre tudo antes de executar.
O sistema antigo em si não é parado; se ele recusar o host novo, ajuste o `.env` dele (fora deste pacote).
Fim da convivência: remover `/etc/nginx/sites-enabled/flicsales-antigo`, `nginx -t`, reload; depois desligar os
serviços do antigo (decisão à parte).

## Plano de migração do flicsales antigo (a decidir — nada executado)

O OS **não** é continuação do antigo (modelos e regras diferentes). Migrar é um projeto de dados, não um deploy.

1. **Inventário**: quais clientes/tenants o antigo atende hoje (banco `flicsales`), quantos usuários ativos, volume
   por entidade (empresas, contatos, oportunidades, títulos, baixas, anexos), integrações ligadas (e-mail, WhatsApp).
2. **Quem migra**: decidir por cliente — migra (vira organização no OS, `cli nova-organizacao`), recomeça do zero no
   OS, ou é encerrado. Clientes inativos não migram.
3. **O que migra** (por cliente): cadastros (empresas — atenção à unicidade de nome, `nome_chave` —, pessoas, produtos),
   pipeline aberto (oportunidades → funil/etapas do OS), financeiro em aberto (títulos com saldo; baixas como histórico?),
   usuários (login curto; senha não migra → convite/primeiro acesso), anexos. O que **não** migra: histórico de
   auditoria (vira export arquivado), configurações de integração (recadastrar nas telas, cifradas).
4. **ETL**: script próprio (fora do app, idempotente, por organização) lendo um dump do antigo e escrevendo pelo
   domínio/serviços do OS (para respeitar as regras: venda ≠ caixa, baixa ≤ saldo, nada apagado). Ensaios no hml com
   dump real anonimizado; relatório de conferência (contagens e somas por cliente: títulos abertos, saldo, pipeline).
5. **Janela de troca**: congelar o antigo (somente leitura) → dump final → ETL → conferência com o cliente →
   `trocar-dominio.sh` → antigo segue em `antigo.flicsales.com.br` (leitura) por um período combinado (ex.: 30–60 dias)
   → backup final e desligamento.
6. **Comunicação**: aviso aos clientes com antecedência (data, o que muda, novo login curto/primeiro acesso, onde fica o
   antigo durante a convivência), canal de suporte na semana da troca, e plano de volta (`--reverter`) combinado.
7. **Riscos**: subdomínios do antigo (`app.`, `admin.`) — o coringa do OS não os substitui enquanto houver registro
   específico; links salvos/bookmarks; webhooks externos apontando para o domínio antigo (repontar para
   `antigo.` ou para o OS).

## Pendências

- **Nomes de banco por ambiente no backend** (acima) — sem isso, prod não instala no mesmo PostgreSQL que o hml.
- Firewall do painel da hospedagem: liberar 10075/tcp para o hml por IP (o script só cuida do ufw).
- `BACKUP_BUCKET` (cópia fora do servidor) ainda não definido: o backup fica só local.
- A organização inicial do hml nasce vazia; o seed de demonstração só roda com `AMBIENTE=dev`. Se o Jefferson quiser os
  dados do protótipo no hml, é preciso um comando de seed por organização liberado para hml (mudança no backend).
- `/api/arquivos-publicos` e webhooks expostos direto pela API: confirmar que os links gerados usam `FRONTEND_URL`.
