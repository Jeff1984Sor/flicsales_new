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
export { ChipsPapeis, DrawerEmpresa } from "./drawer-empresa";
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
