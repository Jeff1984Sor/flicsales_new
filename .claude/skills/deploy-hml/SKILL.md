---
name: deploy-hml
description: Publica a branch develop no hml do FlicSales OS (VPS compartilhada, http://2.25.130.240:10075 enquanto o hml for por IP) pelo deploy/deploy.sh e confere de verdade que subiu. Use quando o Jefferson pedir "sobe no hml", "publica em homologação" ou depois de integrar algo na develop.
---

# Deploy no hml

O hml é onde tudo passa antes de produção. Mesmo assim a VPS é compartilhada (flicsales antigo, MayaJus, MayaFit…):
**só** os serviços `flicsales-os-*@hml` podem ser reiniciados, e nada fora de `/home/deploy/flicsales-os/hml`.

## Antes
1. O que vai subir está na `develop` do GitHub (`git log origin/develop -5`)? O servidor só puxa do GitHub.
2. Localmente verde: skill `verificar` (pytest + lint + build). O deploy roda os testes de novo, mas falhar lá custa 4–8 min.

## Publicar
```bash
ssh flicsales 'cd /home/deploy/flicsales-os/hml && ./deploy/deploy.sh hml'
# só mudou o frontend:
ssh flicsales 'cd /home/deploy/flicsales-os/hml && ./deploy/deploy.sh hml --so-front'
```
Os 7 passos: situação → código → testes (abortam ANTES de reiniciar) → migrations (principal, controle e cada
organização) → build em `.next-novo` com o site no ar → versão `hml-<commit>` (sem tag) → troca + reinício + conferência
de `/api/health` e do CSS (reverte o front sozinho se o CSS não vier).

Parou no passo 1 por "arquivos versionados alterados no servidor": veja `git diff` lá. Se for só o que o build gera
(tsconfig.json), traga para o repositório ou descarte com `git checkout -- frontend/tsconfig.json` — nunca descarte
mudança que você não entendeu. HEAD solto (rollback anterior): `VOLTAR_PARA_BRANCH=sim ./deploy/deploy.sh hml`.

## Conferir de verdade
Use a skill `saude` (hml) ou:
```bash
ssh flicsales 'curl -s http://127.0.0.1:10073/api/health; echo; H=$(curl -s http://127.0.0.1:10074/login); C=$(echo "$H" | grep -o "/_next/static/[^\"]*\.css" | head -1); curl -s -o /dev/null -w "css %{http_code}\n" "http://127.0.0.1:10074$C"; curl -s -o /dev/null -w "externo %{http_code}\n" http://2.25.130.240:10075/login'
```
`versao` no health tem de ser `hml-<commit novo>`. HTTP 200 sozinho não prova nada (a página de erro do Next é 200).

## Devolva
Commit publicado, commits que entraram, resultado das conferências. Falhou: passo, mensagem e o que fazer.
