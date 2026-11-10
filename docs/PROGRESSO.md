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
