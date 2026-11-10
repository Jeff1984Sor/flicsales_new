/**
 * Cadastros do Núcleo — componentes reutilizáveis por TODOS os módulos (importe daqui: `@/components/cadastros`).
 * As props de cada um estão documentadas no topo do respectivo arquivo.
 *
 * Seleção e criação contextual
 *  - SeletorEmpresa          "selecionar ou criar" empresa (o nome basta; nunca duplica)
 *  - SeletorResponsavel, SeletorCategoria, SeletorCentroCusto, SeletorConta, SeletorProduto, SeletorPessoa
 *  - CamposPersonalizados    renderiza/edita os campos custom de empresa | pessoa | oportunidade
 *    (+ useCamposDoObjeto, formatarValorCampo)
 *
 * Drawers de cadastro (abrem por cima de qualquer tela)
 *  - DrawerEmpresa, DrawerPessoa, DrawerProduto, DrawerFornecedor, DrawerCategoria, DrawerCentroCusto, DrawerConta
 *  - DrawerDependencias      dependências de um campo personalizado (e arquivamento revisado)
 *  - ChipsPapeis             seletor de papéis da empresa
 *
 * Telas inteiras (usadas pelas páginas do Comercial, Financeiro e Núcleo)
 *  - TelaEmpresas, TelaPessoas, TelaProdutos, TelaFornecedores, TelaCategorias, TelaCentrosCusto, TelaContas,
 *    TelaCampos, TelaCadastrosMestres, TelaArquitetura, QualidadeDados
 *
 * Enriquecimento e migração
 *  - BlocoEndereco (+ enderecoDe, ENDERECO_VAZIO)   endereço estruturado com busca de CEP
 *  - CampoCnpj (+ preencherVazios)                   "Buscar CNPJ" que preenche só campos vazios
 *  - EnriquecerIA                                    "✧ Enriquecer com IA" para qualquer drawer de cadastro
 *  - BotaoImportarPlanilha, DrawerImportarPlanilha   migração por planilha (.xlsx/.csv)
 *  - QuadroSocietario, AnexosEmpresa, aplicarCnpj    seções do drawer de empresa/fornecedor
 *
 * Utilitários: paraEnvio, alterados, txt, CHIPS_SITUACAO, useInvalidarCadastros, useUsuariosOpcoes, useIdDaUrl,
 * RodapeFormulario.
 */
export { CamposPersonalizados, formatarValorCampo, useCamposDoObjeto } from "./campos-personalizados";
export {
  CHIPS_SITUACAO,
  RodapeFormulario,
  SeletorCategoria,
  SeletorCentroCusto,
  SeletorConta,
  SeletorPessoa,
  SeletorProduto,
  SeletorResponsavel,
  alterados,
  paraEnvio,
  txt,
  useInvalidarCadastros,
  useUsuariosOpcoes,
} from "./comum";
export { CampoCnpj, preencherVazios } from "./campo-cnpj";
export { dadosParaIA, mascaraCep, mascaraDocumento, mesclarSugestoes, rotaAusente } from "./consultas";
export { ChipsPapeis, DrawerEmpresa } from "./drawer-empresa";
export { AnexosEmpresa, QuadroSocietario, aplicarCnpj } from "./empresa-extras";
export { BlocoEndereco, ENDERECO_VAZIO, enderecoDe, type ValorEndereco } from "./endereco";
export { EnriquecerIA } from "./enriquecer-ia";
export { BotaoImportarPlanilha, DrawerImportarPlanilha, permissaoImportar } from "./importar-planilha";
export { DrawerPessoa } from "./drawer-pessoa";
export { QualidadeDados } from "./qualidade-dados";
export { SeletorEmpresa, type EmpresaEscolhida } from "./seletor-empresa";
export { TelaArquitetura } from "./tela-arquitetura";
export { TelaCadastrosMestres, useIdDaUrl } from "./tela-cadastros-mestres";
export { DrawerDependencias, TelaCampos } from "./tela-campos";
export { TelaEmpresas } from "./tela-empresas";
export { TelaPessoas } from "./tela-pessoas";
export { DrawerProduto, TelaProdutos } from "./tela-produtos";
export {
  DrawerCategoria,
  DrawerCentroCusto,
  DrawerConta,
  DrawerFornecedor,
  TelaCategorias,
  TelaCentrosCusto,
  TelaContas,
  TelaFornecedores,
} from "./telas-financeiras";
