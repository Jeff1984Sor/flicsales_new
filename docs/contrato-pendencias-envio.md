# Contrato — Pendências finais: envio de e-mail, modelos no Financeiro, opt-out, SMTP por usuário, arrastar (11/11/2026)

Backend e frontend trabalham em paralelo a partir deste contrato. Mudou → atualize aqui (seção "Backend entregue").
Migração nova: `0007_envio_email` (revisa `0006_nucleo_parte2`).

## 1. SMTP por usuário (opcional) — core
- Tabela `config_email_usuario`: `usuario_id` PK/FK usuario, `remetente_nome` String(150), `remetente_email` String(200),
  `smtp_host` String(200), `smtp_porta` Integer default 587, `smtp_usuario` String(200) null,
  `smtp_senha_cifrada` LargeBinary null (segredos.cifrar_texto), `ativo` Boolean default True, Timestamped.
- Rotas (logado, cada um só o seu; sem permissão especial — adicionar em lista de rotas "livres para logados" do core):
  - `GET /api/auth/me/email` → `{configurado: bool, ativo, remetente_nome, remetente_email, smtp_host, smtp_porta,
    smtp_usuario, senha_final: "••••abcd" | null}` (nunca a senha).
  - `PUT /api/auth/me/email` `{remetente_nome, remetente_email, smtp_host, smtp_porta, smtp_usuario, smtp_senha?, ativo}`
    (senha ausente/vazia = mantém a salva). Audita `email_usuario.alterar` (sem senha).
  - `DELETE /api/auth/me/email` → volta a usar o SMTP da organização.
  - `POST /api/auth/me/email/testar` → faz login SMTP (não envia nada) → `{ok: bool, mensagem}`.
- `app.core.email.enviar(..., remetente=usuario)`: se o usuário tem `config_email_usuario` ativo → usa esse SMTP e
  `From` = dele; senão o SMTP da organização (`ConfigEmail` id=1) com `Reply-To` = e-mail do usuário (se tiver).
  E-mails do sistema continuam no SMTP da organização.

## 2. Serviço único de envio por um usuário — `app/core/envio.py`
`enviar_por_usuario(db, usuario, *, para: list[str], cc: list[str] = [], assunto: str, corpo: str,
anexos=None) -> None` (levanta `RegraViolada` em PT-BR):
- `para` ≥ 1, e-mails válidos (máx. 20 no total); assunto e corpo obrigatórios.
- **Opt-out**: qualquer destinatário (para/cc) que seja e-mail de uma `Pessoa` com `opt_out` em
  `permissoes_comunicacao` → `RegraViolada("<Nome> pediu para não receber comunicações (opt-out).")`. Usar
  `app.domain.cadastro.aceita_envio_automatico` (ou função pura nova `pode_receber_email(permissoes)` com teste).
- Sem SMTP (nem do usuário nem da organização) em hml/prod → `RegraViolada("Configure o e-mail de envio em
  Configurações › E-mail ou em Minha conta.")`. Falha de entrega → `RegraViolada("Não foi possível enviar o e-mail: …")`
  (mensagem curta, sem senha). Dev sem SMTP grava no outbox (como hoje).
- Assinatura do usuário (ou da Identidade) sempre acrescentada (`remetente=usuario`).
- `GET /api/auth/me/envio` (logado) → `{pode_enviar: bool, via: "usuario" | "organizacao" | "outbox" | null,
  remetente: "Nome <email>" | null}` — a tela usa para habilitar o botão e mostrar "Enviar como …".

## 3. Envio nas telas (cada módulo chama o serviço; tudo auditado; a mensagem vira registro)
Corpo comum `EnvioEmailIn = {para: str[], cc?: str[], assunto: str, corpo: str, modelo_id?: int}`.
Saída comum `EnvioEmailOut = {ok: true, enviado_para: str[], registro: "<texto curto do que foi registrado>"}`.
- **Comunicações** `POST /api/comercial/comunicacoes/enviar-email` (`comercial.comunicacoes.editar`) com
  `empresa_id?`, `oportunidade_id?` (vínculo conferido com o escopo "só meus") → envia e cria `Comunicacao`
  canal `email`, `titulo=assunto`, `conteudo` = "Para: …\n\n" + corpo, `data=hoje()`. Audita `comunicacao.enviar_email`.
- **Propostas** `POST /api/comercial/propostas/{id}/enviar-email` (`comercial.propostas.editar`) com
  `anexar_pdf: bool = true` (se já existir geração de PDF da proposta, anexa; senão ignora e diz no `registro`).
  Status `aprovada_internamente` ou `rascunho` → passa a `enviada` **só se** a regra de status atual permitir; senão
  mantém. Cria `Comunicacao` email vinculada à oportunidade. Audita `proposta.enviar_email`.
- **Cobranças** `POST /api/financeiro/cobrancas/{id}/enviar-email` (`financeiro.cobrancas.editar`) → envia e acrescenta
  ao `historico` da cobrança a linha "dd/mm/aaaa — E-mail enviado para … por <usuário>: <assunto>". Audita
  `cobranca.enviar_email`.
- Destinatários sugeridos: `GET` de cada registro já traz a empresa; a tela busca as pessoas da empresa
  (`GET /api/nucleo/pessoas?empresa_id=`) e marca as com opt-out como indisponíveis.

## 4. Modelos no Financeiro
- `GET /api/financeiro/cobrancas/modelos?canal=email` (`financeiro.cobrancas.ver`) → mesmo formato `ModeloOut` do
  comercial, só `financeiro` + `geral`, ativos, ordenados por nome. (Resolve: perfil Financeiro não lia
  `/comercial/modelos`.)
- `POST /api/financeiro/cobrancas/{id}/modelos/{modelo_id}/previa` (`financeiro.cobrancas.ver`) → `PreviaModeloOut`
  preenchendo `empresa.nome`, `contato.nome` (primeira pessoa da empresa, se houver), `titulo.valor` (saldo aberto em
  BRL), `titulo.vencimento` (dd/mm/aaaa), `titulo.descricao`. Modelo comercial → 404.
- Comunicações/propostas no Comercial continuam usando `GET /comercial/modelos?contexto=comercial` e
  `POST /comercial/modelos/{id}/previa`.

## 5. Opt-out em envios automáticos
Se alguma automação/tarefa do worker envia mensagem (procurar `email.enviar`/notificador em `modules/` e `tarefas.py`),
ela passa pelo mesmo bloqueio (pula a pessoa e registra no log/auditoria). Se não houver, registrar em
`docs/PROGRESSO.md` que todo envio passa por `app/core/envio.py`.

## 6. Front
- Componente `components/flic/enviar-email.tsx` (`<EnviarEmailDrawer aberto onFechar destino={{tipo, id}}
  empresaId? modelos="comercial"|"financeiro" contexto? />`): para/cc (chips; sugestões das pessoas da empresa, opt-out
  desabilitado com etiqueta "Opt-out"), escolher modelo (preenche assunto/corpo pela prévia; mostra variáveis que
  faltaram), assunto, corpo, "Enviar como <remetente>" (de `/auth/me/envio`), botão Enviar (desabilitado se
  `pode_enviar=false`, com link para Minha conta). Sucesso → toast + invalida as queries do registro.
- Botões "✉ Enviar e-mail": tela Comunicações (cabeçalho e drawer da empresa/oportunidade se fizer sentido), drawer da
  Proposta, drawer da Cobrança. Só aparecem com a permissão `editar` do recurso.
- Cobranças passam a listar modelos de `/financeiro/cobrancas/modelos` (financeiro+geral).
- Minha conta: seção "E-mail de envio" (opcional): explica "Sem configurar, seus e-mails saem pelo e-mail da
  organização com resposta para você"; formulário SMTP (senha somente escrita, "configurado ••••abcd"), Testar
  conexão, Remover.
- Opções de lista (`components/governanca/tela-opcoes-lista.tsx` e onde houver ↑↓): **arrastar para reordenar**
  (HTML5 drag-and-drop, alça ⋮⋮), mantendo ↑↓ para teclado. Salva a nova ordem pela mesma rota de hoje.

## Backend entregue
Entregue em 11/11/2026 (migração `0007_envio_email` revisando `0006_nucleo_parte2`; tabela `config_email_usuario`
exatamente como na §1). Todas as rotas abaixo exigem login; erros de regra = **HTTP 400 `{detail}`** em PT-BR; corpo
mal formado = 422.

**Minha conta (livre para logados, cada um só o seu)**
- `GET /api/auth/me/email` → `{configurado, ativo, remetente_nome, remetente_email, smtp_host, smtp_porta,
  smtp_usuario, senha_final}`. Sem configuração: `{configurado: false, ativo: false, smtp_porta: 587, demais null}`.
  `senha_final` = `"••••••abcd"` (6 pontos + 4 últimos, `segredos.mascarar`) ou null. A senha nunca volta.
- `PUT /api/auth/me/email` corpo `{remetente_nome (1–150), remetente_email (e-mail), smtp_host (obrigatório),
  smtp_porta (1–65535, padrão 587), smtp_usuario?, smtp_senha?, ativo (padrão true)}` → mesmo formato do GET.
  Senha ausente/vazia mantém a salva. Audita `email_usuario.alterar` (sem senha). Porta 465 = SSL; outras = STARTTLS.
- `DELETE /api/auth/me/email` → `{configurado: false, …}`; 404 se não havia. Audita `email_usuario.remover`.
- `POST /api/auth/me/email/testar` → `{ok, mensagem}` (sempre 200 quando testou; só login, nada é enviado).
  **Extra:** aceita, opcionalmente, o MESMO corpo do PUT para testar o formulário antes de salvar (senha vazia = usa a
  salva). Sem corpo e sem configuração salva → 400 "Salve o e-mail de envio antes de testar.".
- `GET /api/auth/me/envio` → `{pode_enviar, via: "usuario"|"organizacao"|"outbox"|null, remetente}`. `remetente` é o
  `From` que sairia: o do usuário (via usuario) ou o da organização (via organizacao/outbox). Em dev sem SMTP:
  `via: "outbox"`, `pode_enviar: true`. Em hml/prod sem SMTP: `{false, null, null}`. SMTP próprio com `ativo: false`
  é ignorado (volta para a organização).

**Envio** — corpo comum `EnvioEmailIn = {para: str[], cc?: str[], assunto: str, corpo: str, modelo_id?: int}`;
saída comum `EnvioEmailOut = {ok: true, enviado_para: str[], registro: str}`. `enviado_para` = para + cc já
normalizados (minúsculos, sem repetição; quem está em "para" sai do "cc"). Mensagens de 400 do serviço:
"Informe ao menos um destinatário em “Para”.", "E-mail inválido: “x”.", "Envie para no máximo 20 destinatários por
vez.", "Informe o assunto do e-mail.", "Escreva a mensagem do e-mail.", "<Nome> pediu para não receber comunicações
(opt-out). Retire o e-mail e envie de novo." (vários: "A e B pediram …"), "Configure o e-mail de envio em
Configurações › E-mail ou em Minha conta.", "Não foi possível enviar o e-mail: <motivo curto>.". O opt-out confere
TODOS os e-mails da pessoa (principal e adicionais), em para e cc. Nada é registrado se o envio falhar.
- `POST /api/comercial/comunicacoes/enviar-email` (`comercial.comunicacoes.editar`) com `empresa_id?`,
  `oportunidade_id?`. Cria `Comunicacao` canal `email`, `titulo=assunto`, `conteudo="Para: …[
Cc: …]

"+corpo`,
  `data=hoje()`; com oportunidade grava evento "E-mail enviado para …: <assunto>" no histórico dela. Escopo "só meus":
  exige `oportunidade_id` própria (400 "Vincule o e-mail a uma das suas oportunidades."; de outro → 400
  "Oportunidade não encontrada."). `modelo_id` precisa ser comercial/geral (senão 400). `registro` =
  "Comunicação #<id> registrada (e-mail).". Audita `comunicacao.enviar_email`.
- `POST /api/comercial/propostas/{id}/enviar-email` (`comercial.propostas.editar`) com `anexar_pdf: bool = true`.
  **Não existe geração de PDF da proposta**: nada é anexado e, se `anexar_pdf`, o `registro` diz "PDF não anexado: a
  geração de PDF da proposta ainda não está disponível.". Status: `aprovada_internamente` → `enviada`; `rascunho` →
  `enviada` só sem desconto (com desconto exige aprovação interna, mantém); demais mantêm. `registro` = "Comunicação
  #<id> registrada na oportunidade. Proposta marcada como Enviada." ou "… Status mantido: <Rótulo>." Evento
  "proposta" na oportunidade. 404 se a proposta não existe/fora do escopo. Audita `proposta.enviar_email`.
- `POST /api/financeiro/cobrancas/{id}/enviar-email` (`financeiro.cobrancas.editar`) → acrescenta ao `historico`
  (em nova linha) "dd/mm/aaaa — E-mail enviado para <para e cc> por <nome do usuário>: <assunto>". `registro` =
  "Histórico da cobrança atualizado: <linha>". `modelo_id` comercial/inexistente → 404. Audita `cobranca.enviar_email`.

**Modelos no Financeiro**
- `GET /api/financeiro/cobrancas/modelos?canal=email` (`financeiro.cobrancas.ver`) → `ModeloOut[]` (mesmo formato do
  Comercial, com `variaveis`), só `financeiro` + `geral`, ativos, por nome. `canal` opcional
  (email|whatsapp|ligacao|reuniao; outro valor → 422).
- `POST /api/financeiro/cobrancas/{id}/modelos/{modelo_id}/previa` (`financeiro.cobrancas.ver`, sem corpo) →
  `PreviaModeloOut {assunto, conteudo, faltando, aviso}` com `empresa.nome`, `contato.nome` (primeira pessoa da empresa,
  ativas primeiro), `titulo.valor` (saldo aberto "R$ 6.000,00"), `titulo.vencimento` (dd/mm/aaaa),
  `titulo.descricao`. Modelo comercial/inexistente → 404 "Modelo não encontrado."; cobrança → 404.

**Divergências do texto original:** (1) `testar` aceita corpo opcional (acima); (2) a mensagem de opt-out ganhou o
complemento "Retire o e-mail e envie de novo." (o começo é o do contrato); (3) `enviar_por_usuario` devolve a
mensagem normalizada (`app.domain.envio.Mensagem`) em vez de `None`; (4) PDF da proposta não é anexado (não existe
gerador). §5: não há envio automático real hoje — registrado em `docs/PROGRESSO.md`; para quando houver:
`app.core.envio.destinatarios_liberados(db, para)` pula opt-out e registra no log.
