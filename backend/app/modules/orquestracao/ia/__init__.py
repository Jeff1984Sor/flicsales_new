"""IA unificada: UMA camada (não um agente por tela).

- `gateway`     provedor plugável (usa app.core.ia; nos testes, um gerador falso injetável).
- `formato`     resposta única validada por Pydantic + saneamento (ações só da lista permitida).
- `ferramentas` leitura por domínio, cada uma checando a permissão `*.ver` do usuário (a IA nunca amplia acesso).
- `contexto`    escopo (registro/módulo/tudo) → quais ferramentas, foco e montagem do prompt anti-injeção.
- `heuristica`  análise de comunicação por regras (sem IA).
- `servico`     perguntar, leitura do momento e análise de comunicação (com retentativa e queda para as regras).
"""
