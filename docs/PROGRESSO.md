# Progresso — FlicSales OS

## Fases
| Fase | Conteúdo | Estado |
|---|---|---|
| 0 | Governança: CLAUDE.md, especificação extraída do protótipo, agentes e skills | ✅ 10/11/2026 |
| 1 | Fundação: backend core (auth, perfis, permissões, auditoria, tenancy, IA plugável), todos os modelos + migração 0001, regras de domínio com testes, seed do protótipo; frontend shell com a identidade do protótipo | em andamento |
| 2 | Módulos em paralelo: Núcleo · Comercial · Financeiro · Orquestração (IA + automações + integrações) | — |
| 3 | QA, paridade com o protótipo e teste de ponta a ponta do critério de aceite | — |
| 4 | Admin FlicSales (organizações, planos, consumo de IA) e servidor (hml/prod) | aguardando decisão |

## Dúvidas para o Jefferson
- Portas e servidor de produção: a VPS compartilhada já usa 10001/10002 para o flicsales antigo. Sugestão: 10011 (API) / 10012 (web). Confirmar quando formos publicar.
- Domínio: o novo substitui `flicsales.com.br` ou roda em outro endereço até a migração?
- Provedor de IA padrão (OpenAI ou Gemini, ambos plugáveis na tela).
- Perfis Comercial e Financeiro: o CLAUDE.md diz "leitura de cadastros", mas os dois menus têm Empresas/Pessoas/Fornecedores
  e a empresa nasce dentro da oportunidade. A Fundação deu `nucleo.cadastros.editar` aos dois (ajustável na matriz de perfis).
  Confirmar. (docs/progresso-fundacao.md)
- Fornecedor = empresa com papel fornecedor (+ categoria padrão e condição habitual), sem tabela própria. Confirmar.

## Registro
- 10/11/2026 — Projeto criado. Protótipo salvo em `docs/prototipo/`. Especificação em `docs/ESPECIFICACAO.md`.
- 10/11/2026 — Fundação backend: core do MayaFit portado (auth, perfis, permissões, auditoria, IA, um banco por organização), todos os modelos + migração 0001, domínio com testes, seed do protótipo. Detalhes em `docs/progresso-fundacao.md`.
- 10/11/2026 — **Produção no ar em https://flicsales.com.br** (VPS compartilhada, /home/deploy/flicsales-os/prod, serviços
  flicsales-os-*@prod, API 10071 / web 10072, acesso de conferência http://2.25.130.240:10076). Organização `matriz`
  ("FlicSales"; `flicsales` é slug reservado), Gestor `jefferson`. Bancos flicsalesos_prod, flicsalesos_controle_prod,
  flicsalesos_prod_matriz. Troca de domínio feita à mão (não pelo trocar-dominio.sh): site nginx novo
  `flicsales-os-dominio` com flicsales.com.br + www (certificado existente); o site antigo `flicsales` ficou com
  app.flicsales.com.br, admin.flicsales.com.br e o IP. Backups: /home/deploy/backups/troca-flicsales-20261110-1522
  (banco flicsales + conf) e troca-flicsales-20261110-2014-nginx (conf antes da troca). Voltar: restaurar a conf do
  backup, remover o link sites-enabled/flicsales-os-dominio, nginx -t, reload.
  Pendências: COOKIE_SECURE=false no front de prod (herdado do modo IP; ligar e fechar a porta 10076 quando não precisar
  mais da conferência por IP); hml ainda não instalado; migração dos clientes do flicsales antigo.
- 10/11/2026 — Ajustes do Núcleo (backend, contrato `docs/contrato-nucleo-ajustes-11-2026.md`): migração
  `0005_nucleo_ajustes` (LGPD da pessoa, campos `multipla`/`link`, assinatura de e-mail por usuário).
  Pendências: bloqueio de envio automático para pessoa com opt-out — ainda não há envio real (automações de envio
  aguardam conector); regra pronta em `app.domain.cadastro.aceita_envio_automatico`, pedido em
  `docs/progresso-orquestracao.md`. Filtro de indicador por campo `multipla`: pedido em `docs/progresso-comercial.md`.
  Comunicações/cobranças/propostas ainda não enviam e-mail: quando enviarem, usar `email.enviar(..., remetente=usuario)`.

