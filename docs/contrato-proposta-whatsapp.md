# Contrato — Proposta automatizada + PDF e WhatsApp pela Evolution API (11/11/2026)

Três frentes em paralelo (backend proposta, backend WhatsApp, frontend). Mudou → atualize aqui na seção "Entregue" da
sua parte. **A migração `0008_proposta_whatsapp` e os modelos já estão prontos** (não crie outra migração):
- `comercial.models.ModeloProposta` (`modelo_proposta`: nome, padrao, introducao, termos, rodape, validade_dias=15,
  condicao_padrao, ativo) e `Proposta.modelo_proposta_id` (FK null).
- `orquestracao.models.Integracao` ganhou `provedor` (String 20), `url` (String 300), `instancia` (String 100).

---------------------------------------------------------------------------------------------------------------------
## A. Proposta automatizada + PDF (backend: módulo comercial)

### A1. Modelos de proposta (Gestão comercial › Modelos de proposta) — permissão `comercial.recursos.*`
- `GET /api/comercial/modelos-proposta` → `ModeloPropostaOut[]` `{id, nome, padrao, introducao, termos, rodape,
  validade_dias, condicao_padrao, ativo, variaveis: str[]}`; `?incluir_inativos=true`.
- `POST` / `PATCH /api/comercial/modelos-proposta/{id}`. Regras (domínio puro + teste): nome obrigatório e único
  (sem diferenciar maiúsculas), `validade_dias` 1–365, condição ∈ condições aceitas na proposta. Marcar `padrao=true`
  desmarca os outros. Não se exclui: `ativo=false` (o padrão não pode ser inativado). Auditoria
  `modelo_proposta.criar|atualizar`.
- Seed/migração de dados: se não houver nenhum, a primeira leitura cria (ou o seed cria) "Proposta comercial padrão"
  com textos curtos em PT-BR usando variáveis.
- Variáveis aceitas nos textos: `empresa.nome`, `empresa.cnpj`, `contato.nome`, `oportunidade.titulo`,
  `proposta.titulo`, `proposta.total`, `proposta.validade`, `proposta.condicao`, `responsavel.nome`, `hoje`.
  Reaproveitar `regras.renderizar_modelo`.

### A2. Proposta automática a partir da oportunidade
`POST /api/comercial/oportunidades/{id}/proposta-automatica` (`comercial.propostas.editar`)
`{modelo_proposta_id?: int, produto_id?: int, usar_ia?: bool = false}` → `PropostaOut` (201) em **rascunho**:
- versão = próxima da oportunidade; `titulo` = "Proposta — <oportunidade.titulo>"; `empresa_id` da oportunidade;
  produto = informado ou o da oportunidade (se houver campo) → `preco_unitario` = preço do produto, senão
  `valor` da oportunidade; quantidade 1; desconto 0; `validade` = hoje + `validade_dias` do modelo;
  `condicao` = `condicao_padrao` do modelo ou "à vista"; `escopo` = descrição do produto + nome; `modelo_proposta_id`.
- `usar_ia=true` e IA ligada → a IA redige o `escopo` (2–5 parágrafos) a partir do produto, da oportunidade, das
  comunicações e atividades dela (texto importado é DADO). IA desligada/indisponível → segue sem IA e a resposta traz
  aviso (`aviso: str | null` em `PropostaOut` ou cabeçalho; documente). Nada de número inventado: valores vêm do
  cadastro.
- Respeita escopo "só meus" (oportunidade de outro → 404). Auditoria `proposta.criar` com `descricao="automática"`.

### A3. PDF da proposta
`GET /api/comercial/propostas/{id}/pdf` (`comercial.propostas.ver`) → `application/pdf`
(`Content-Disposition: inline; filename="proposta-<id>-v<versao>.pdf"`). Gerar com **fpdf2** (já usado em
`app/modules/nucleo/comprovante.py`; fonte com acentos). Conteúdo:
- Cabeçalho: logo e nome da Identidade (`Identidade.logo_path`, `nome_exibicao`, `cor_destaque`); "PROPOSTA
  COMERCIAL", título, versão, data de emissão, validade.
- Cliente: empresa (nome, CNPJ, endereço se houver) e contato da oportunidade.
- Introdução do modelo (renderizada), Escopo, tabela (produto/serviço, quantidade, valor unitário, desconto %, total),
  mensalidade adicional se > 0, condição de pagamento, Termos do modelo, responsável (nome, e-mail) e rodapé.
- Marca d'água/faixa "RASCUNHO — não enviar" se status `rascunho` ou `em_aprovacao` com desconto > 0.
- Função reutilizável `gerar_pdf_proposta(db, proposta) -> bytes` em `app/modules/comercial/servico.py` (a frente
  WhatsApp chama).
- `POST /propostas/{id}/enviar-email` com `anexar_pdf=true` passa a anexar o PDF de verdade (`registro` deixa de dizer
  que não há PDF).

---------------------------------------------------------------------------------------------------------------------
## B. WhatsApp pela Evolution API (backend: orquestração + core notificador + rotas de envio)

### B1. Configuração (Integrações › WhatsApp) — permissão `orquestracao.integracoes.*`
Usa a linha `Integracao(tipo="whatsapp")` com `provedor="evolution"`, `url`, `instancia`, apikey em `segredo_cifrado`
(somente escrita: mostra "configurado ••••abcd"). Catálogo do WhatsApp passa a descrever a Evolution API
("API do WhatsApp no seu servidor (Evolution)").
- `GET /api/orquestracao/integracoes/whatsapp/evolution` → `{configurado, provedor, url, instancia, chave_final,
  estado, numero?, testado_em, ultimo_erro}`.
- `PUT  …/whatsapp/evolution` `{url, apikey?, instancia?}` (url http(s), sem barra final; apikey vazia = mantém).
  Auditoria sem a chave.
- `POST …/whatsapp/evolution/instancias` `{url?, apikey?}` (usa o salvo se vazio) → `[{nome, estado, numero}]`
  via `GET {url}/instance/fetchInstances` (header `apikey`).
- `POST …/whatsapp/evolution/testar` → `GET {url}/instance/connectionState/{instancia}`; `open` → estado `conectado`,
  senão `desconectado` com mensagem; erro → `erro` + `ultimo_erro` (sem a chave). Devolve `{ok, estado, mensagem}`.
- `POST …/whatsapp/evolution/qrcode` → `GET {url}/instance/connect/{instancia}` → `{base64?, codigo_pareamento?}`
  para conectar o número pela tela (se a instância não existir, `POST {url}/instance/create`
  `{instanceName, integration: "WHATSAPP-BAILEYS", qrcode: true}`).
- Cliente HTTP em `app/modules/orquestracao/evolution.py` (httpx, timeout 15s), **testes com transporte falso**
  (httpx.MockTransport) — nunca chamar a Evolution real nos testes.
- Registrar um `Notificador` Evolution no core (`definir_notificador`) que lê a config do banco da organização na hora
  do envio, para o código de recuperação de senha por WhatsApp funcionar.

### B2. Envio por um usuário — `app/core/envio.py` ganha `enviar_whatsapp_por_usuario(db, usuario, *, para:
list[str], texto: str, documento: tuple[nome, bytes, mime] | None = None)`
- Telefones normalizados para dígitos com DDI 55 (aceita "(11) 99999-0000", "+55 11 …"); inválido → RegraViolada.
  Máx. 10 por vez. Texto obrigatório (até 4000).
- **Opt-out**: telefone de `Pessoa` com `opt_out` → RegraViolada "<Nome> pediu para não receber comunicações
  (opt-out)." (reusar `app.domain.envio`).
- Sem WhatsApp configurado/conectado → RegraViolada "Configure o WhatsApp em Núcleo › Integrações.".
- Envio: `POST {url}/message/sendText/{instancia}` `{number, text}`; com documento
  `POST {url}/message/sendMedia/{instancia}` `{number, mediatype: "document", mimetype, media: <base64>, fileName,
  caption: texto}`. Falha → RegraViolada "Não foi possível enviar pelo WhatsApp: <motivo curto>.".
- Texto ganha no fim "— <nome do usuário>" (assinatura curta).
- `GET /api/auth/me/envio` ganha `whatsapp: {pode_enviar: bool, numero?: str}`.

### B3. Rotas de envio (mesmas permissões do e-mail) — corpo `EnvioWhatsAppIn = {para: str[], texto: str,
modelo_id?: int}`, saída `EnvioWhatsAppOut = {ok, enviado_para: str[], registro: str}`
- `POST /api/comercial/comunicacoes/enviar-whatsapp` (+ `empresa_id?`, `oportunidade_id?`) → cria `Comunicacao`
  canal `whatsapp` (conteúdo "Para: …\n\n"+texto). Auditoria `comunicacao.enviar_whatsapp`.
- `POST /api/comercial/propostas/{id}/enviar-whatsapp` (+ `anexar_pdf: bool = true`) → manda o PDF como documento
  (`servico.gerar_pdf_proposta`); status como no e-mail. Auditoria `proposta.enviar_whatsapp`.
- `POST /api/financeiro/cobrancas/{id}/enviar-whatsapp` → linha no histórico "dd/mm/aaaa — WhatsApp enviado para …
  por …". Auditoria `cobranca.enviar_whatsapp`.
- Modelos com `canal=whatsapp` servem de texto (prévia já existe; usar `conteudo`).
- Automações `enviar_whatsapp`: se hoje ficam "pendente de conector", passam a enviar quando a Evolution estiver
  conectada, usando `envio.destinatarios_liberados` (pula opt-out). Se for grande demais, registre como pendência.

---------------------------------------------------------------------------------------------------------------------
## C. Front
- **Propostas** (drawer da proposta): botões "Baixar PDF" (abre `/bff/comercial/propostas/{id}/pdf` em nova aba),
  "✉ Enviar e-mail" (já existe; checkbox de PDF agora anexa de fato) e "WhatsApp" (drawer de envio). Na tela de
  Propostas e no drawer da Oportunidade: "✧ Gerar proposta" → mini-form (modelo de proposta, produto opcional,
  "Redigir escopo com IA" se a IA estiver ligada) → cria e abre o drawer da proposta criada.
- **Gestão comercial**: card/aba "Modelos de proposta" (lista + drawer com nome, padrão, validade em dias, condição
  padrão, introdução, termos, rodapé; lista das variáveis clicáveis para inserir).
- **WhatsApp**: componente `components/flic/enviar-whatsapp.tsx` (para = telefones das pessoas da empresa, opt-out
  desabilitado; modelo canal whatsapp; texto; "Enviar pelo número <numero>"); botões "WhatsApp" em Comunicações,
  Proposta (com "Anexar PDF") e Cobrança — só com permissão `editar` e `whatsapp.pode_enviar`.
- **Integrações › WhatsApp**: formulário Evolution (URL da API, API key somente escrita, botão "Buscar instâncias" →
  lista para escolher, "Testar conexão", "Conectar número (QR code)" mostrando a imagem base64 e atualizando o estado).
- Tipos em `lib/tipos-comercial.ts` / `lib/tipos-nucleo.ts` (ou da área de orquestração) e `lib/types.ts`.

## Entregue — A (proposta)
Arquivos: `app/domain/modelo_proposta.py` (regras puras), `app/modules/comercial/rotas_proposta_documento.py`
(rotas novas), `app/modules/comercial/pdf_proposta.py` (desenho fpdf2), `servico.py` (funções no fim do arquivo),
`schemas.py`, `routes.py` (regras de permissão), `rotas_gestao.py` (só enviar-email e PATCH da proposta).
Testes: `tests/comercial/test_modelo_proposta_regras.py`, `tests/comercial/test_proposta_documento.py`.

**A1 — modelos de proposta** (`comercial.recursos.*`, regra `("*", "/comercial/modelos-proposta", …)`)
- `GET /api/comercial/modelos-proposta?incluir_inativos=` → `ModeloPropostaOut[]` (padrão primeiro, depois nome).
  A primeira leitura cria "Proposta comercial padrão" se a tabela estiver vazia (o seed NÃO foi alterado).
- `GET /api/comercial/modelos-proposta/{id}` (extra, para o drawer) · `POST` (201) · `PATCH /{id}` (grava só o enviado).
- Campos de entrada: `nome, padrao, introducao, termos, rodape, validade_dias (padrão 15), condicao_padrao, ativo`.
- `condicao_padrao` ∈ `"À vista" | "2 parcelas" | "3 parcelas" | "Recorrente mensal"` (vazio = null).
- Divergência/regra extra: além de "o padrão não pode ser inativado", **o padrão não pode ser desmarcado** direto
  (`padrao=false` no padrão → 400 "Sempre há um modelo padrão: marque outro modelo como padrão para trocar."). Para
  trocar, marque outro com `padrao=true` (desmarca os demais).
- `variaveis` = as 10 do contrato (constante `app.domain.modelo_proposta.VARIAVEIS`).

**A2 — proposta automática** `POST /api/comercial/oportunidades/{id}/proposta-automatica` (201)
- Entrada `{modelo_proposta_id?, produto_id?, usar_ia=false}`; sem modelo usa o padrão. Modelo inexistente/inativo
  ou produto inexistente/inativo → 400. Oportunidade sem empresa → 400. "Só meus" → 404.
- Oportunidade não tem campo de produto: produto só vem de `produto_id`.
- Preço: `preco_referencia` do produto; sem produto (ou sem preço) = `valor_unico` da oportunidade.
  **Extra:** `mensalidade_adicional` = `valor_recorrente_mensal` da oportunidade (0 se o produto for recorrente,
  para não somar duas vezes).
- Escopo sem IA: "nome do produto\n\ndescrição"; sem produto: "título da oportunidade\n\nNecessidade: …".
- Responsável: o da oportunidade (se ativo; senão quem gerou; com "só meus", quem gerou).
- `PropostaOut` ganhou `modelo_proposta_id` e **`aviso: str | null`** (só preenchido na resposta da automática:
  IA desligada, IA indisponível ou resposta fora do formato; a proposta é criada mesmo assim com o escopo do cadastro).
- IA: `app.core.ia.ligada/provedor_ativo/gerar_json`; resposta esperada `{"paragrafos": [...]}` (2–5, aceita também
  `{"escopo": "..."}`). Comunicações vão no campo `comunicacoes_DADOS_IMPORTADOS` e o prompt manda não seguir
  instruções delas. A IA só escreve o escopo; valores vêm do cadastro.
- Auditoria `proposta.criar` com `descricao="automática"` (+ `usar_ia`, `escopo_ia` no depois); evento "proposta" no
  histórico da oportunidade.
- `PATCH /propostas/{id}` aceita `modelo_proposta_id` (null = volta ao padrão; inexistente → 400).

**A3 — PDF** `GET /api/comercial/propostas/{id}/pdf` (`comercial.propostas.ver`; "só meus" → 404)
- `application/pdf`, `Content-Disposition: inline; filename="proposta-<id>-v<versao>.pdf"`.
- `servico.gerar_pdf_proposta(db, proposta) -> bytes` (não grava nada; usa o modelo da proposta, senão o padrão,
  senão os textos iniciais em memória). Fonte Helvetica latin-1 (acentos ok; travessão/aspas curvas/✧ viram ASCII).
- Faixa "RASCUNHO - não enviar" + marca d'água quando `rascunho` ou `em_aprovacao` com desconto > 0.
- `POST /propostas/{id}/enviar-email` com `anexar_pdf=true` (padrão) anexa `proposta-<id>-v<versao>.pdf`; o
  `registro` diz "PDF anexado: <arquivo>." (com `anexar_pdf=false` não fala de PDF).

## Entregue — B (WhatsApp)
Arquivos: `app/modules/orquestracao/evolution.py` (cliente httpx + config + `NotificadorEvolution`),
`rotas_integracoes.py` (rotas `/whatsapp/evolution*`), `schemas.py`, `integracoes.py` (catálogo e "Testar" genérico),
`motor.py` (automação envia de verdade), `routes.py` (registra o notificador); core: `app/core/envio.py`,
`app/core/schemas.py`, `app/core/routes/auth.py`, `app/core/notificador.py` (docstring); domínio `app/domain/envio.py`;
`app/modules/comercial/rotas_whatsapp.py` (arquivo novo, incluído em `comercial/routes.py`); `financeiro/routes.py`
(só a rota da cobrança). Sem migração (usa a 0008). Testes: `tests/domain/test_envio_whatsapp.py`,
`tests/orquestracao/test_whatsapp_evolution.py`, `tests/comercial/test_envio_whatsapp.py`,
`tests/financeiro/test_cobranca_whatsapp.py`; Evolution falsa em `tests/evolution_falsa.py` (httpx.MockTransport).

**B1. Configuração** (`orquestracao.integracoes.ver` no GET; `…editar` no resto — POST conta como editar, inclusive
`instancias`):
- `GET  /api/orquestracao/integracoes/whatsapp/evolution` → `EvolutionOut {configurado, provedor, url, instancia,
  chave_final: "••••••abcd"|null, estado: desconectado|conectado|erro, numero: str|null (dígitos com DDI),
  testado_em, ultimo_erro}`. `configurado` = provedor evolution + url + instância + chave.
- `PUT  …/evolution` `{url (obrigatória), apikey?, instancia?}` → `EvolutionOut`. URL http(s) com servidor; a barra
  final é retirada. apikey ausente/vazia = mantém; < 8 caracteres → 400. instância: letras, números, `. - _` e espaço
  (ausente = mantém). Mudou url/chave/instância → estado volta a `desconectado` (precisa testar). Auditoria
  `integracao.configurar` (descrição "WhatsApp (Evolution) · API key alterada"; a chave nunca entra).
- `POST …/evolution/instancias` `{url?, apikey?}` (corpo opcional) → `[{nome, estado: conectado|conectando|
  desconectado, numero}]` (aceita formato v2 `name/connectionStatus/ownerJid` e o v1 `instance.instanceName`).
- `POST …/evolution/testar` → `{ok, estado, mensagem}`. `open` → `conectado` e o número (do fetchInstances) fica em
  `integracao.conta`; outro estado → `desconectado` com instrução do QR code; falha → `erro` + `ultimo_erro`.
  Auditoria `integracao.testar`. O "Testar conexão" genérico (`POST /integracoes/whatsapp/testar`) também usa a
  Evolution quando `provedor="evolution"` (sem provedor continua só validando formato).
- `POST …/evolution/qrcode` → `{base64 ("data:image/png;base64,…" como a Evolution devolve) | null,
  codigo_pareamento | null, estado: conectando|conectado, mensagem}`. 404 da Evolution → `POST /instance/create`
  `{instanceName, integration: "WHATSAPP-BAILEYS", qrcode: true}` e usa o QR da criação. Já conectada → `base64`
  null, estado `conectado`. Erro → 400 "Não foi possível gerar o QR code: …". Auditoria `integracao.qrcode`.
- Catálogo: descrição "API do WhatsApp no seu servidor (Evolution)", rótulo do segredo "API key da Evolution",
  requisitos novos. Escopos mantidos (evita invalidar dados salvos).
- Erros do cliente: curtos em PT-BR ("a API key foi recusada pela Evolution", "instância não encontrada na
  Evolution", "a API do WhatsApp não respondeu a tempo (15 s)", "não foi possível conectar à URL…", "a Evolution
  respondeu HTTP 500 (…)"); a chave é mascarada até se o servidor ecoá-la. Testado em resposta, auditoria, log e
  `ultimo_erro`.
- Notificador: `definir_notificador(NotificadorEvolution())` ao carregar `orquestracao/routes.py`. Abre
  `SessionLocal()` (segue a organização do pedido via `tenancy`), só envia se a Evolution estiver **conectada**;
  falha → `False` + log sem texto (o código) e sem chave.

**B2. Core** — `app.core.envio`:
- `enviar_whatsapp_por_usuario(db, usuario, *, para, texto, documento=None) -> MensagemWhatsApp` (para = dígitos com
  DDI; texto já assinado "\n\n— <nome>"). Ordem: valida → opt-out (recusa tudo) → conectado? → envia um a um.
- `via_whatsapp(db) -> ViaWhatsApp(pode_enviar, numero)`; `telefones_liberados(db, telefones, origem=)` (automático:
  pula opt-out e inválidos, registra no log). `contatos_com_opt_out` agora traz os telefones (principal + lista).
- `GET /api/auth/me/envio` ganhou `whatsapp: {pode_enviar, numero}` (`WhatsAppMeOut` em `core/schemas.py`).
- Domínio (`app.domain.envio`, puro): `normalizar_whatsapp` ((11) 99999-0000, 11999990000, +55 11 …, 0xx; celular com
  11 dígitos precisa do 9; DDD sem zero; número estrangeiro aceito só com "+" explícito — **divergência**: o contrato
  falava só em DDI 55), `validar_mensagem_whatsapp` (1–10 telefones, texto até 4000), `assinar_whatsapp`,
  `telefones_bloqueados`/`conferir_opt_out_telefones`/`filtrar_opt_out_telefones`, `formatar_whatsapp`
  ("+55 (11) 99999-0000"), `conteudo_comunicacao_whatsapp`, `linha_historico_cobranca_whatsapp`.

**B3. Rotas de envio** — `EnvioWhatsAppIn {para: str[], texto, modelo_id?}` / `EnvioWhatsAppOut {ok, enviado_para
(dígitos com DDI), registro}` em `app/core/schemas.py`. Permissões pelo mapa padrão (iguais às do e-mail).
- `POST /api/comercial/comunicacoes/enviar-whatsapp` (+ `empresa_id?`, `oportunidade_id?`): Comunicação canal
  `whatsapp`, título "WhatsApp: <1ª linha>", conteúdo "Para: +55 (11) …\n\n<texto assinado>"; evento na
  oportunidade "WhatsApp enviado para …"; "só meus" exige oportunidade própria. Auditoria `comunicacao.enviar_whatsapp`.
- `POST /api/comercial/propostas/{id}/enviar-whatsapp` (+ `anexar_pdf=true`): PDF de `servico.gerar_pdf_proposta`
  vai por `sendMedia` (legenda = texto assinado, `fileName` = `proposta-<id>-v<versao>.pdf`); sem PDF → `sendText`.
  Comunicação "Proposta <título> v<n>", status pela mesma regra do e-mail. Auditoria `proposta.enviar_whatsapp`
  (`depois` traz `para`, `pdf`, `comunicacao_id`).
- `POST /api/financeiro/cobrancas/{id}/enviar-whatsapp`: linha "dd/mm/aaaa — WhatsApp enviado para +55 (11) … por
  <usuário>" no histórico. Auditoria `cobranca.enviar_whatsapp`.
- `modelo_id` é conferido como no e-mail (existe e é da área); o texto vem pronto da tela (prévia já existente).
- Falha da Evolution com vários telefones: o erro diz para quem já foi ("Já enviado para …; envie de novo só para os
  demais.") e nada é registrado (a transação volta).

**Automações `enviar_whatsapp`**: com a Evolution conectada, o motor envia de verdade (texto renderizado, sem
assinatura). Destinatário `contato_principal` = contato da oportunidade ou 1º contato ativo da empresa (telefone tipo
WhatsApp › celular › principal); ou telefones escritos na automação (separados por vírgula). Opt-out/inválido →
resultado `ignorada` (sem envio); sem contato/telefone ou falha → `falhou` (com retentativas). Envio registra
Comunicação canal whatsapp (`registro_criado = "comunicacao:<id>"`) + auditoria `comunicacao.enviar_whatsapp`.
Sem conexão: continua `pendente_conector`. `enviar_email` automático continua pendente (fora do escopo B).

**Fora / pendências**: receber respostas (webhook da Evolution) não foi feito; envio com vários telefones não é
atômico (a Evolution não tem transação); o número conectado só é atualizado no "Testar conexão".
