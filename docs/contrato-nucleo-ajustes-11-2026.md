# Contrato — Ajustes do Núcleo (documento "Módulo Núcleo_11.2026.docx", Jefferson, 10/11/2026)

Backend e frontend trabalham em paralelo a partir deste contrato. Mudou → atualize aqui.

## A. Todas as telas de cadastro (front)
1. Tirar o rótulo "FLICSALES / CONTEXTO" do topo dos drawers. Implementação: o padrão de `eyebrow` do `Drawer`
   (`components/flic/drawer.tsx`) passa a ser vazio (não renderiza nada); quem passa `eyebrow`/`rotulo` explícito mantém.

## B. Empresas
1. Enriquecimento pelo CNPJ ao digitar (já existe: confirmar que, em empresa nova, ao completar CNPJ válido traz os dados
   do cartão CNPJ — nome, fantasia, segmento, porte, contatos, endereço — e, ao salvar, grava sócios, Dados da Receita e o
   comprovante PDF). Corrigir o que não estiver funcionando.
2. Campo **Origem** fica, com rótulo "Origem" e dica "Canal de entrada do relacionamento", e vira **lista suspensa**:
   Indicação · Site / formulário · Prospecção ativa · Evento · Redes sociais · Parceiro · Importação · Outro.
   Backend aceita qualquer texto (dados antigos ficam); a tela mostra o valor antigo como opção se não estiver na lista.

## C. Pessoas
1. **Tirar o "✧ Enriquecer com IA"** do drawer de pessoa (fica nos demais cadastros).
2. Novo grupo **"ORIGEM"** no drawer de pessoa, com:
   - **Base legal** (seleção única, lista suspensa) — `pessoa.base_legal` String(30) null, valores:
     `consentimento` "Consentimento" · `legitimo_interesse` "Legítimo interesse" ·
     `contrato` "Execução de contrato / Pré-contrato" · `aguardando` "Sem base legal definida / Aguardando validação".
   - **Permissão de comunicação** (múltipla escolha, checkbox) — `pessoa.permissoes_comunicacao` JSON lista de str,
     default [], valores: `whatsapp_telefone` "Aceita contato via WhatsApp / Telefone" ·
     `email_marketing` "Aceita receber E-mail Marketing / Newsletters" ·
     `comercial_pontual` "Apenas contato comercial pontual" · `opt_out` "Opt-out / Não deseja receber comunicações".
   - Regra (domínio puro + teste): `opt_out` é exclusivo — junto com qualquer outro → RegraViolada
     "Opt-out não combina com outras permissões de comunicação." Valor fora da lista → 400.
   - Migração nova `0005_nucleo_ajustes`. Schemas de entrada/saída de pessoa, planilha de pessoas (colunas "Base legal"
     e "Permissão de comunicação" separada por `;`), exportar CSV e auditoria cobrem os dois campos.
   - (Envios automáticos a pessoa com `opt_out` devem ser bloqueados onde já houver envio — registrar como pendência
     em docs/PROGRESSO.md se não houver ponto óbvio.)

## D. Campos personalizados
1. Tipos oferecidos na criação: **Texto · Data · Número · Moeda · Seleção única · Seleção múltipla · Hiperlink**.
   Backend: tipos `texto|data|numero|moeda|lista|multipla|link` (`lista` = seleção única, já existe; `multipla` e `link`
   novos; `sim_nao` continua aceito para campos antigos, mas não é oferecido na tela). `multipla` exige ≥ 1 opção e o
   valor é lista de opções válidas; `link` valida URL http(s). Atualizar validação de valores, filtros, CSV, planilha e a
   lista branca da IA (`app/domain/enriquecimento.py`: multipla → lista de opções; link → site/url).
2. **Exigir no funil**: lista dos funis criados; **Escolher na etapa**: etapas daquele funil (só aparece depois de
   escolher o funil). Só para objeto Oportunidade. Backend: `GET` de funis/etapas já existe no comercial — a tela usa;
   o campo continua gravando `exigido_na_etapa_id` (validar que a etapa existe). Mostrar o funil na listagem de campos.

## E. Administração
1. Tirar o card **Auditoria** da tela Administração.
2. Card **"Usuários e perfis"** → a tela de Configurações passa a ter só as abas **Usuários · Perfis de acesso · E-mail**.
3. Novo card **"Identidade"** na Administração (abre `/configuracoes/identidade`, que sai das abas).
4. **Inteligência Artificial** fica só no card "Configuração da IA" (sai das abas de Configurações; rota
   `/configuracoes/ia` continua existindo).
5. **Assinatura de e-mail por usuário, com imagem**:
   - Backend: `usuario.assinatura_email` Text null e `usuario.assinatura_imagem` String(300) null (caminho no storage);
     migração `0005_nucleo_ajustes` (é tabela do core: autorizado). `PATCH /api/auth/me` (ou a rota de "minha conta"
     existente) aceita `assinatura_email`; `POST /api/auth/me/assinatura-imagem` (multipart png/jpg até 1 MB) e
     `DELETE` do mesmo; `GET` da imagem para logados (e embutida no e-mail como imagem inline/CID ou URL assinada,
     o que o `app/core/email.py` suportar melhor).
   - E-mails enviados **por um usuário** (comunicações, cobranças, propostas) usam a assinatura dele; sem assinatura
     própria, cai na assinatura padrão da Identidade. E-mails do sistema (senha, convite) usam a da Identidade.
   - Front: em "Minha conta" seção "Assinatura de e-mail" (texto + enviar/remover imagem + prévia). Em Identidade, o
     campo existente vira "Assinatura padrão (quando o usuário não tem a sua)".

## F. Histórico de ações
1. Renomear para **"Auditoria"** no menu, título da página, breadcrumb e paleta (`nav.ts`, página `/nucleo/historico`).

## Backend entregue (10/11/2026) — campos e rotas finais
Migração `0005_nucleo_ajustes` (revisa `0004_dados_receita`).

- **B.1**: fluxo coberto por teste (`tests/nucleo/test_nucleo_ajustes.py`): `GET /nucleo/consultas/cnpj/{cnpj}` →
  `POST /nucleo/empresas` (com o que veio) → `POST /nucleo/empresas/{id}/cnpj/aplicar` grava sócios, Dados da Receita
  e o comprovante PDF (anexo `cartao_cnpj`). Nada a corrigir no backend.
- **B.2**: `empresa.origem` continua texto livre (até 100 caracteres).
- **C**: `PessoaCriar/Atualizar/Saida` ganham `base_legal: str | null` e `permissoes_comunicacao: str[]` (saída sempre
  lista, ordem do catálogo, sem repetição). Fora da lista ou opt-out combinado → **400** com a mensagem do contrato.
  `GET /nucleo/pessoas?base_legal=<valor>|sem` filtra. Planilha de pessoas: colunas "Base legal" (rótulo ou valor) e
  "Permissão de comunicação" (rótulos ou valores separados por `;`; célula preenchida substitui a lista). Auditoria
  `pessoa.criar/alterar` traz os dois campos no antes→depois. Exportar CSV é do front (campos já vêm na listagem).
  Regra pura: `app.domain.cadastro.validar_base_legal`, `validar_permissoes_comunicacao`, `aceita_envio_automatico`.
- **D**: `tipo` aceita `multipla` e `link` (`TipoCampo`). `multipla`: valor é lista (também aceita texto "A; B"),
  ordenada como as opções; opção não pode conter `;`. `link`: sem protocolo vira `https://`; outro protocolo → 400.
  `CampoSaida` ganha `funil_id`, `funil_nome` (funil da etapa exigida) e `tipo_rotulo`. `GET /nucleo/campos/etapas`
  devolve também `funil_id` (a tela filtra as etapas pelo funil escolhido). `exigido_na_etapa_id`: etapa precisa existir
  e o funil estar ativo (só conferido quando o valor muda). Planilha: `multipla` separada por `;`. IA: `multipla` →
  lista de opções; `link` → tipo `site`.
- **E.5**: `usuario.assinatura_email` (Text) e `usuario.assinatura_imagem` (String 300, caminho em
  `storage/assinaturas/`). `UsuarioMe` ganha `assinatura_email` e `assinatura_imagem_url`
  (`"/auth/me/assinatura-imagem?v=<versão>"` ou null). `PATCH /api/auth/me {"assinatura_email": "..."}` (vazio = sem
  assinatura própria; até 4000 caracteres). `POST /api/auth/me/assinatura-imagem` (multipart `arquivo`, PNG/JPG até 1 MB)
  e `DELETE` do mesmo devolvem `UsuarioMe`; `GET /api/auth/me/assinatura-imagem` devolve a imagem (404 sem imagem).
  Envio: `app.core.email.enviar(..., remetente=usuario)` usa a do usuário (imagem inline CID `assinatura`) ou, sem ela,
  a da Identidade; `assinar=True` (e-mails do sistema: senha, convite) usa a da Identidade.
