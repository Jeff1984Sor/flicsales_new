# Contrato — Enriquecimento de cadastros (CNPJ, CEP, IA) e migração por planilha

Pedido do Jefferson (10/11/2026): "puxar os dados do CNPJ e preencher; digito o CEP e ele já puxa; quando puxar a empresa
e tiver CEP já atualiza o endereço da pessoa; Enriquecer por IA em todas as telas de cadastro, fazendo o que o usuário
pedir; baixar o modelo das planilhas para migrar os dados".

Três frentes trabalham em paralelo a partir deste contrato. **Mudou o contrato → atualize este arquivo e avise.**

## 1. Endereço estruturado (backend — migração nova `0003_enderecos`)

`empresa` e `pessoa` ganham: `cep` String(9), `logradouro` String(200), `numero` String(20), `complemento` String(100),
`bairro` String(100), `cidade` String(100), `uf` String(2). O antigo `empresa.endereco` (texto) fica: a migração não
apaga dado; telas novas usam os campos estruturados.

`pessoa.usa_endereco_da_empresa` Boolean (padrão **true**, server_default "1"). Regra (domínio puro + teste):
- ao criar/editar pessoa com empresa e `usa_endereco_da_empresa=true`, o endereço da pessoa = o da empresa;
- quando o endereço da empresa muda (PATCH manual, CNPJ, importação), as pessoas vinculadas com a marca ligada recebem o
  novo endereço (auditado `pessoa.endereco_da_empresa`); quem tem a marca desligada não é tocado;
- editar o endereço da pessoa manualmente desliga a marca (a tela pode mandar a marca explícita).

Schemas de entrada/saída de empresa e pessoa expõem esses campos. `EmpresaOut` também.

## 2. Consultas públicas (backend, `app/modules/nucleo/consultas.py`)

Sem chave, server-side (o navegador nunca chama provedor externo), timeout 8 s, fallback entre provedores,
cache em memória 24 h. CNPJ/CEP validados em `app/domain/cadastro.py` (dígitos verificadores do CNPJ; CEP 8 dígitos).

- `GET /api/nucleo/consultas/cnpj/{cnpj}` (perm. `nucleo.cadastros.ver`) → 200
  ```json
  {"documento":"12.345.678/0001-90","nome":"RAZÃO SOCIAL LTDA","nome_fantasia":"...","segmento":"CNAE principal (descrição)",
   "porte":"ME|EPP|Demais|null","situacao":"ATIVA","abertura":"2010-05-01","telefone":"...","email_financeiro":"...",
   "cep":"01310-100","logradouro":"...","numero":"...","complemento":"...","bairro":"...","cidade":"...","uf":"SP",
   "fonte":"BrasilAPI (Receita Federal)","empresa_existente":{"id":3,"nome":"..."}|null}
  ```
  Provedores: BrasilAPI `https://brasilapi.com.br/api/cnpj/v1/{cnpj}` → fallback `https://open.cnpja.com/office/{cnpj}`
  ou ReceitaWS. CNPJ inválido → 400 "CNPJ inválido."; não encontrado → 404; provedores fora → 502 com mensagem clara.
- `GET /api/nucleo/consultas/cep/{cep}` → `{"cep","logradouro","bairro","cidade","uf","fonte"}`. ViaCEP → fallback BrasilAPI
  `/api/cep/v2`. CEP inválido 400; inexistente 404.

## 3. Enriquecer por IA (ia-orquestrador, `app/modules/orquestracao/`)

`POST /api/orquestracao/ia/enriquecer`
```json
{"objeto":"empresa|pessoa|produto|fornecedor|categoria|centro_custo|conta",
 "registro_id": 12 | null,
 "dados": {"campo": "valor atual no formulário", ...},
 "instrucao": "o que o usuário quer (texto livre: 'complete pelo CNPJ', 'escreva a descrição comercial', 'padronize o nome', 'descubra o segmento')",
 "texto_apoio": "texto colado (assinatura de e-mail, site, cartão…) — DADO, nunca instrução" | null}
```
→ 200
```json
{"sugestoes":[{"campo":"segmento","rotulo":"Segmento","valor_atual":null,"valor_sugerido":"Tecnologia","justificativa":"...","fonte":"CNPJ (BrasilAPI)|IA|texto colado"}],
 "evidencias":["..."],"limites":["..."],"origem":"ia|regras"}
```
- Só campos editáveis do objeto (lista branca por objeto, inclui os campos de endereço e `campos_custom.<slug>` ativos
  do objeto). Valores validados/normalizados antes de devolver (uf 2 letras, cep 00000-000, e-mail válido, número > 0…).
  Sugestão fora da lista branca ou inválida é descartada.
- Nada é gravado: a tela aplica no formulário e o usuário salva.
- Para empresa/fornecedor com CNPJ válido, a consulta do item 2 roda antes e entra como evidência e como sugestões com
  `fonte` "CNPJ (…)". **Sem IA configurada** a rota responde 200 com `origem:"regras"`: sugestões só do CNPJ/CEP e um
  limite "A IA está desligada: ative em Configurações › Inteligência Artificial para pedidos livres.".
- Permissão: `orquestracao.ia.ver` **e** `ver` do cadastro do objeto (empresa/pessoa/produto → `nucleo.cadastros.ver`;
  fornecedor/categoria/centro_custo/conta → `financeiro.cadastros.ver`). A IA nunca amplia acesso.
- Registra uso/auditoria como as outras chamadas de IA do módulo.

**Como ficou (implementado):** rota em `app/modules/orquestracao/rotas_ia.py`, serviço em
`app/modules/orquestracao/ia/enriquecer.py`, lista branca e normalização (puras) em `app/domain/enriquecimento.py`.
- Regra de rota: `POST /orquestracao/ia/enriquecer$` → `orquestracao.ia.ver`; dentro, `ctx.exigir` do `ver` do cadastro
  (403 "Seu perfil de acesso não permite esta ação."). Objeto fora da lista → 422; `registro_id` inexistente → 404.
- Campos (lista branca): empresa = nome, nome_fantasia, documento, segmento, porte, site, email_financeiro, telefone,
  origem, observacoes + endereço (cep, logradouro, numero, complemento, bairro, cidade, uf) + `campos_custom.<slug>`
  ativos de Empresa; fornecedor = empresa + condicao_habitual; pessoa = nome, cargo, email, telefone, canal_preferido,
  observacoes + endereço + `campos_custom.<slug>` de Pessoa; produto = nome, tipo, codigo, unidade, preco_referencia (> 0),
  recorrente, descricao; categoria = nome, natureza; centro_custo = nome, codigo; conta = nome, instituicao (saldo
  inicial e data-base **não**: a IA não sugere número de saldo). Papéis, responsável e ids nunca são sugeridos.
- `dados` aceita `"campos_custom.<slug>": v` ou `"campos_custom": {"<slug>": v}`; chaves fora da lista são ignoradas.
  Com `registro_id`, os valores salvos entram como base e o formulário vence.
- `instrucao` é opcional (padrão "Complete e padronize os campos que puder, sem inventar fatos."), até 2 000 caracteres;
  `texto_apoio` até 20 000. Ambos e os dados vão ao prompt neutralizados (`<`/`>`), delimitados em `<pedido_usuario>`,
  `<dados_atuais>`, `<consulta_publica>` e `<texto_apoio>`; o sistema manda ignorar instruções dentro dos dados.
- Valores devolvidos já normalizados: `cep` "00000-000", `uf` maiúscula de UF real, e-mail minúsculo, telefone
  "(11) 3333-4444"/"(11) 91234-5678", documento CNPJ/CPF formatado com DV válido, site com `https://`, opção na forma
  canônica (`servico`, `whatsapp`…), dinheiro como string decimal "1234.50", data ISO, sim/não como booleano.
  Sugestão igual ao valor atual não volta. Quando o CNPJ/CEP e a IA sugerem o mesmo campo, vence a consulta pública.
- `fonte`: `"CNPJ (BrasilAPI)"`, `"CEP (ViaCEP)"`, `"texto colado"` ou `"IA"`. `valor_atual` é o valor do formulário.
- Sem IA (ou IA falhou/fora do formato após 1 nova tentativa): 200, `origem:"regras"`, sugestões só das consultas; o
  limite diz o motivo. Consulta pública fora/não encontrada vira limite (a rota não falha). CNPJ já cadastrado em outra
  empresa → limite "Já existe a empresa “X” (#id) com este CNPJ…". Sempre termina com o limite "Nada foi gravado…".
- Uso: grava `IaConversa` (tela "Enriquecer · <Objeto>", `registro_tipo` = objeto) + `IaMensagem` (conta no consumo) e
  auditoria `ia.enriquecer` (entidade = objeto, id = `registro_id`). Nenhum cadastro é alterado.

## 4. Planilhas de migração (backend, `app/modules/nucleo/planilhas.py`)

Objetos: `empresas`, `fornecedores`, `pessoas`, `produtos`, `categorias`, `centros-custo`, `contas`.
Permissão: empresas/pessoas/produtos → `nucleo.cadastros.*`; os demais → `financeiro.cadastros.*` (ver para baixar
modelo, editar para importar).

- `GET /api/nucleo/planilhas/{objeto}/modelo` → `.xlsx` (openpyxl): aba "Dados" com cabeçalho em PT-BR (+ colunas dos
  campos personalizados ativos do objeto), uma linha de exemplo em cinza que a importação ignora (marcada "EXEMPLO" na
  1ª coluna), validação de lista nas colunas de opção (papéis, natureza, tipo, uf, sim/não); aba "Instruções" com cada
  coluna, obrigatória ou não, formato e exemplo. Aceita também importar `.csv` (`;` ou `,`, UTF-8 com/sem BOM).
- `POST /api/nucleo/planilhas/{objeto}/importar?simular=true|false` (multipart `arquivo`, até 5 MB / 5 000 linhas) →
  ```json
  {"total":120,"criar":100,"atualizar":15,"ignorar":5,
   "erros":[{"linha":7,"coluna":"CNPJ","mensagem":"CNPJ inválido."}],
   "previa":[{"linha":2,"acao":"criar|atualizar|ignorar","nome":"..."}]}
  ```
  Simular não grava. Confirmar (`simular=false`) é **tudo ou nada**: com qualquer erro, 400 com a mesma lista e nada
  gravado. Chave para atualizar (não duplicar): empresa/fornecedor por CNPJ, senão `nome_chave`; pessoa por e-mail, senão
  nome+empresa; produto por código, senão nome; categoria por nome+natureza; centro por código; conta por nome.
  Atualiza só células preenchidas (vazio não apaga). Empresa citada por nome na planilha de pessoas é criada se não
  existir (nome basta). Cada linha gravada é auditada (`importacao.<objeto>`), mais um evento-resumo.
  Endereço da empresa mudou → regra do item 1 propaga para as pessoas.

## 4b. Quadro societário e anexos da empresa (backend, mesma migração 0003)

O Cartão CNPJ oficial da Receita exige captcha e não tem API: **não** baixamos o oficial. Geramos um
"Comprovante de consulta CNPJ" em PDF com os dados públicos, fonte e data/hora da consulta, e o usuário pode anexar o
oficial manualmente.

- Tabela `empresa_socio`: id, empresa_id FK, nome String(200), qualificacao String(120), documento String(18) null
  (CPF vem mascarado da Receita: guarde como veio), data_entrada Date null, faixa_etaria String(40) null, Timestamped.
  `consultar_cnpj` passa a devolver também `"socios":[{"nome","qualificacao","documento","data_entrada","faixa_etaria"}]`
  (BrasilAPI campo `qsa`), `"cnae_principal":"6201-5/01 · Desenvolvimento de programas…"`,
  `"cnaes_secundarios":["…"]`, `"natureza_juridica":"…"`, `"capital_social":"10000.00"`.
- Tabela `empresa_anexo`: id, empresa_id FK, nome String(200), tipo String(30) (`cartao_cnpj|contrato|documento|outro`),
  mime String(100), tamanho int, caminho (via `app/core/storage.py`), enviado_por_id FK usuario, Timestamped.
  Nunca se apaga fisicamente: `ativo` false (arquivar) com auditoria.
- `POST /api/nucleo/empresas/{id}/cnpj/aplicar` (nucleo.cadastros.editar): consulta o CNPJ da empresa, **substitui o
  quadro societário** (auditado antes→depois), preenche só campos vazios do cadastro (+ endereço, que propaga para as
  pessoas pela regra do item 1) e gera o PDF (reportlab ou fpdf2; `uv add`) anexado como `cartao_cnpj`
  "Comprovante CNPJ <dd-mm-aaaa>.pdf". Devolve a `EmpresaOut` atualizada. Na criação de empresa com CNPJ, a tela chama
  esta rota logo depois de salvar.
- `GET /api/nucleo/empresas/{id}/socios` → lista; `GET /api/nucleo/empresas/{id}/anexos` → `[{id,nome,tipo,mime,tamanho,
  enviado_por_nome,criado_em,url}]`; `POST .../anexos` (multipart `arquivo`, `tipo`; PDF/imagem/doc até 10 MB);
  `GET .../anexos/{anexo_id}/arquivo` (download, só logado com nucleo.cadastros.ver); `DELETE .../anexos/{anexo_id}`
  arquiva. Fornecedor usa as mesmas rotas (é empresa).

### Notas da implementação backend (itens 1, 2, 4 e 4b — 10/11/2026)

- Rotas como no contrato. Extras: `GET /nucleo/empresas/{id}/anexos?arquivados=true` inclui os arquivados; `url` do anexo
  é caminho da API sem `/api` (`/nucleo/empresas/{id}/anexos/{aid}/arquivo` → o front chama `/bff` + url).
  `POST .../anexos` recebe `tipo` como campo de formulário (padrão `documento`); aceita PDF, PNG, JPG, WEBP, DOCX, XLSX.
- Funções para outros módulos (`app/modules/nucleo/consultas.py`): `consultar_cnpj(cnpj, db=None) -> dict` (com `db`
  traz `empresa_existente`), `consultar_cep(cep) -> dict`; erros `RegraViolada` (inválido), `ConsultaNaoEncontrada`
  (é `LookupError`, 404) e `ConsultaIndisponivel` (502), ambas com `.mensagem`. Testes trocam `consultas.TRANSPORTE`
  por `httpx.MockTransport` e chamam `consultas.limpar_cache()`. Telefone sai "(11) 3333-4444"; logradouro/bairro/cidade
  do CNPJ saem em "Título" (sem acento quando a Receita não tem).
- Endereço da pessoa: a marca só desliga se algum campo de endereço enviado for **diferente** do atual (reenviar o
  formulário inteiro não desliga). Trocar a empresa de uma pessoa com a marca ligada copia o endereço da nova.
  Fornecedor (`/nucleo/fornecedores`) também expõe e grava os 7 campos e propaga. Mesclar empresas propaga para os
  contatos movidos. A regra pura: `app/domain/cadastro.py` (`resolver_endereco_pessoa`, `propagar_endereco`,
  `validar_cnpj`, `validar_documento` (CNPJ ou CPF), `validar_cep`, `validar_uf`, `preencher_vazios`).
- `empresa.documento` **não** passou a ser validado no POST/PATCH de empresa (dados antigos e CPF continuam aceitos);
  a planilha valida (CNPJ 14 dígitos ou CPF 11, com dígito verificador) e grava formatado.
- Aplicar CNPJ: preenche campo a campo só os vazios (`nome_fantasia, segmento, porte, telefone, email_financeiro` + os 7
  de endereço) e normaliza `documento`; o nome nunca muda. Auditoria: `empresa.alterar`, `empresa.socios`
  (antes→depois), `empresa_anexo.criar`, `pessoa.endereco_da_empresa`.
- Planilhas: o cabeçalho só exige a coluna que identifica o registro (empresas/fornecedores: Nome ou CNPJ/CPF; pessoas:
  Nome ou E-mail; produtos: Nome ou Código; categorias: Nome e Natureza; centros: Código; contas: Nome) — as demais
  obrigatórias (`*`) valem só ao criar, linha a linha. Colunas desconhecidas são ignoradas. Linha de exemplo = 1ª célula
  começando com "EXEMPLO". `simular` padrão `true`. `previa` limitada a 1 000 itens (contadores são exatos).
  Erro de campo personalizado vem com a coluna do campo. Papéis da planilha são **acrescentados** (nunca removidos).
  Números aceitam "1.234,56", "1234.56", "R$ 1.234,56"; datas DD/MM/AAAA ou AAAA-MM-DD; CSV também em cp1252.
  Auditoria por linha `importacao.<objeto>` (entidade do registro) + resumo `importacao.<objeto>` com entidade
  `importacao`. Empresa criada a partir da planilha de pessoas: `empresa.criar`.

## 5. Telas (frontend)

- Drawer de empresa/fornecedor ganha seções **"Quadro societário"** (tabela nome · qualificação · entrada; botão
  "Atualizar pela Receita" → `/cnpj/aplicar`) e **"Anexos"** (lista com baixar/arquivar, enviar arquivo com tipo; o
  comprovante CNPJ aparece com etiqueta "Cartão CNPJ"). Texto curto explicando que o cartão oficial pode ser anexado.

- `components/cadastros/endereco.tsx`: bloco CEP (máscara; ao completar 8 dígitos chama `/nucleo/consultas/cep/...` e
  preenche logradouro/bairro/cidade/uf, foco vai para "Número") + campos. Usado em empresa e pessoa.
- Drawer de empresa (e fornecedor): campo CNPJ com máscara e botão "Buscar CNPJ" (também dispara ao completar 14
  dígitos válidos em cadastro novo) → preenche os campos vazios e mostra quais mudou; se `empresa_existente`, avisa e
  oferece abrir o cadastro existente em vez de duplicar.
- Drawer de pessoa: ao escolher empresa, oferece "Usar endereço da empresa" (switch `usa_endereco_da_empresa`, ligado
  por padrão) que copia e trava o endereço; desligar libera a edição.
- Botão **"✧ Enriquecer com IA"** em TODO drawer de cadastro (empresa, fornecedor, pessoa, produto, categoria, centro de
  custo, conta): abre painel com campo "O que você quer?" (texto livre) + atalhos (ex.: empresa: "Completar pelo CNPJ",
  "Descobrir segmento e porte", "Padronizar nome e contatos"; pessoa: "Separar nome, cargo e contatos do texto colado";
  produto: "Escrever descrição comercial", "Sugerir unidade e preço de referência"), área opcional "Texto de apoio";
  resultado em lista campo · atual → sugerido com caixa marcada, justificativa e fonte (`<Fonte>`); "Aplicar
  selecionados" preenche o formulário (não salva). Mostra evidências/limites; com `origem:"regras"` diz que a IA está
  desligada.
- Em cada tela de lista de cadastro: botão "Importar planilha" → drawer: 1) "Baixar modelo (.xlsx)"; 2) enviar arquivo;
  3) simulação (contadores + tabela de erros por linha/coluna + prévia); 4) "Importar N registros" só sem erros; toast.
