// Tipos da API do Núcleo (/bff/nucleo/*). Espelham backend/app/modules/nucleo/schemas.py.
// Dinheiro chega como string decimal ("1234.50"); datas-de-dia como "AAAA-MM-DD".

export type Papel = "prospect" | "cliente" | "fornecedor" | "parceiro";
export type Situacao = "ativos" | "inativos" | "todos";
export type CanalPreferido = "email" | "ligacao" | "whatsapp";
export type TipoProduto = "servico" | "produto";
export type Natureza = "receita" | "despesa";
/** `lista` = seleção única; `sim_nao` só existe em campos antigos (não é oferecido na criação). */
export type TipoCampo = "texto" | "numero" | "moeda" | "data" | "sim_nao" | "lista" | "multipla" | "link";
export type ObjetoCampo = "empresa" | "pessoa" | "oportunidade";

/** Valor de um campo personalizado como a API guarda: texto, número, moeda ("1234.50"), data ("AAAA-MM-DD"), sim/não,
 * seleção múltipla (lista de opções) e hiperlink (URL http/https). */
export type ValorCampo = string | number | boolean | string[] | null;
export type ValoresCampos = Record<string, ValorCampo>;

export const PAPEIS: { valor: Papel; rotulo: string }[] = [
  { valor: "prospect", rotulo: "Prospect" },
  { valor: "cliente", rotulo: "Cliente" },
  { valor: "fornecedor", rotulo: "Fornecedor" },
  { valor: "parceiro", rotulo: "Parceiro" },
];
export const ROTULO_PAPEL: Record<string, string> = Object.fromEntries(PAPEIS.map((p) => [p.valor, p.rotulo]));
export const ROTULO_CANAL: Record<CanalPreferido, string> = { email: "E-mail", ligacao: "Ligação", whatsapp: "WhatsApp" };
export const ROTULO_TIPO_PRODUTO: Record<TipoProduto, string> = { servico: "Serviço", produto: "Produto" };
export const ROTULO_NATUREZA: Record<Natureza, string> = { receita: "Receita", despesa: "Despesa" };
export const ROTULO_TIPO_CAMPO: Record<TipoCampo, string> = {
  texto: "Texto",
  numero: "Número",
  moeda: "Moeda",
  data: "Data",
  sim_nao: "Sim/não",
  lista: "Seleção única",
  multipla: "Seleção múltipla",
  link: "Hiperlink",
};
/** Tipos oferecidos na criação de campo, na ordem da tela. */
export const TIPOS_CAMPO_CRIACAO: TipoCampo[] = ["texto", "data", "numero", "moeda", "lista", "multipla", "link"];

/** Origem da empresa: lista sugerida (o backend aceita qualquer texto; valor antigo aparece como opção). */
export const ORIGENS_EMPRESA = [
  "Indicação",
  "Site / formulário",
  "Prospecção ativa",
  "Evento",
  "Redes sociais",
  "Parceiro",
  "Importação",
  "Outro",
] as const;

export type BaseLegal = "consentimento" | "legitimo_interesse" | "contrato" | "aguardando";
export const BASES_LEGAIS: { valor: BaseLegal; rotulo: string }[] = [
  { valor: "consentimento", rotulo: "Consentimento" },
  { valor: "legitimo_interesse", rotulo: "Legítimo interesse" },
  { valor: "contrato", rotulo: "Execução de contrato / Pré-contrato" },
  { valor: "aguardando", rotulo: "Sem base legal definida / Aguardando validação" },
];
export const ROTULO_BASE_LEGAL: Record<string, string> = Object.fromEntries(BASES_LEGAIS.map((b) => [b.valor, b.rotulo]));

export type PermissaoComunicacao = "whatsapp_telefone" | "email_marketing" | "comercial_pontual" | "opt_out";
export const PERMISSOES_COMUNICACAO: { valor: PermissaoComunicacao; rotulo: string; curto: string }[] = [
  { valor: "whatsapp_telefone", rotulo: "Aceita contato via WhatsApp / Telefone", curto: "WhatsApp / Telefone" },
  { valor: "email_marketing", rotulo: "Aceita receber E-mail Marketing / Newsletters", curto: "E-mail marketing" },
  { valor: "comercial_pontual", rotulo: "Apenas contato comercial pontual", curto: "Comercial pontual" },
  { valor: "opt_out", rotulo: "Opt-out / Não deseja receber comunicações", curto: "Opt-out" },
];
export const ROTULO_PERMISSAO: Record<string, string> = Object.fromEntries(PERMISSOES_COMUNICACAO.map((p) => [p.valor, p.curto]));
export const ROTULO_OBJETO: Record<ObjetoCampo, string> = { empresa: "Empresa", pessoa: "Pessoa", oportunidade: "Oportunidade" };

/** Endereço estruturado de empresa e pessoa (CEP no formato 00000-000, UF com 2 letras). */
export interface Endereco {
  cep?: string | null;
  logradouro?: string | null;
  numero?: string | null;
  complemento?: string | null;
  bairro?: string | null;
  cidade?: string | null;
  uf?: string | null;
}
export const CAMPOS_ENDERECO = ["cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf"] as const;
export type CampoEndereco = (typeof CAMPOS_ENDERECO)[number];

export interface ContatoResumo {
  id: number;
  nome: string;
  cargo: string | null;
  email: string | null;
  telefone: string | null;
}

export interface Empresa extends Endereco {
  id: number;
  nome: string;
  documento: string | null;
  nome_fantasia: string | null;
  segmento: string | null;
  porte: string | null;
  site: string | null;
  email_financeiro: string | null;
  telefone: string | null;
  endereco: string | null;
  responsavel_id: number | null;
  responsavel_nome: string | null;
  papeis: Papel[];
  origem: string | null;
  observacoes: string | null;
  campos_custom: ValoresCampos;
  categoria_padrao_id: number | null;
  categoria_padrao_nome: string | null;
  condicao_habitual: string | null;
  ativo: boolean;
  criado_em: string;
  /** relacionamentos no escopo do perfil: oportunidades e títulos a receber não cancelados.
   * null = o perfil não vê aquele módulo (mostre "—"). */
  oportunidades: number | null;
  titulos_receber: number | null;
  saldo_receber: string | null;
  /** Dados da Receita (gravados em "Atualizar pela Receita"); ausentes até a primeira consulta. */
  situacao_cadastral?: string | null;
  /** data-de-dia "AAAA-MM-DD" */
  data_abertura?: string | null;
  natureza_juridica?: string | null;
  cnae_principal?: string | null;
  cnaes_secundarios?: string[] | null;
  /** string decimal "10000.00" */
  capital_social?: string | null;
  /** instante da última consulta */
  receita_consultada_em?: string | null;
}

export interface EmpresaDetalhe extends Empresa {
  contatos: ContatoResumo[];
}

export interface EmpresaEntrada extends Endereco {
  nome?: string;
  documento?: string | null;
  nome_fantasia?: string | null;
  segmento?: string | null;
  porte?: string | null;
  site?: string | null;
  email_financeiro?: string | null;
  telefone?: string | null;
  endereco?: string | null;
  responsavel_id?: number | null;
  papeis?: Papel[];
  origem?: string | null;
  observacoes?: string | null;
  campos_custom?: ValoresCampos;
  categoria_padrao_id?: number | null;
  condicao_habitual?: string | null;
  ativo?: boolean;
}

export interface Pessoa extends Endereco {
  /** o endereço segue o da empresa vinculada (padrão ligado) */
  usa_endereco_da_empresa?: boolean;
  id: number;
  nome: string;
  empresa_id: number | null;
  empresa_nome: string | null;
  cargo: string | null;
  email: string | null;
  telefone: string | null;
  responsavel_id: number | null;
  responsavel_nome: string | null;
  canal_preferido: CanalPreferido | null;
  observacoes: string | null;
  campos_custom: ValoresCampos;
  ativo: boolean;
  /** LGPD: base legal do tratamento (ausente até o backend publicar o campo) */
  base_legal?: BaseLegal | null;
  /** LGPD: permissões de comunicação; `opt_out` é exclusivo */
  permissoes_comunicacao?: PermissaoComunicacao[];
}

export interface Produto {
  id: number;
  nome: string;
  tipo: TipoProduto;
  codigo: string | null;
  unidade: string | null;
  preco_referencia: string | null;
  recorrente: boolean;
  descricao: string | null;
  ativo: boolean;
}

export interface Fornecedor extends Endereco {
  id: number;
  nome: string;
  documento: string | null;
  contato: string | null;
  email: string | null;
  telefone: string | null;
  categoria_padrao_id: number | null;
  categoria_padrao_nome: string | null;
  condicao_habitual: string | null;
  observacoes: string | null;
  papeis: Papel[];
  ativo: boolean;
  titulos_pagar: number;
}

export interface Categoria {
  id: number;
  nome: string;
  natureza: Natureza;
  superior_id: number | null;
  superior_nome: string | null;
  ativo: boolean;
}

export interface CentroCusto {
  id: number;
  nome: string;
  codigo: string;
  responsavel_id: number | null;
  responsavel_nome: string | null;
  ativo: boolean;
}

export interface ContaFinanceira {
  id: number;
  nome: string;
  instituicao: string | null;
  saldo_inicial: string;
  data_base: string;
  ativo: boolean;
  /** há baixa (não estornada) ou transferência: saldo inicial e data-base ficam travados */
  tem_movimento: boolean;
}

export interface CampoCustom {
  id: number;
  nome: string;
  slug: string;
  tipo: TipoCampo;
  objeto: ObjetoCampo;
  opcoes: string[];
  obrigatorio: boolean;
  exigido_na_etapa_id: number | null;
  etapa_nome: string | null;
  /** funil da etapa exigida (ausente em backend antigo) */
  funil_id?: number | null;
  funil_nome?: string | null;
  ordem: number;
  arquivado: boolean;
  registros_preenchidos: number;
  dependencias_ativas: number;
}

export interface Dependencia {
  tipo: "dashboard" | "automacao" | "etapa" | "registros";
  id: number | null;
  nome: string;
  detalhe: string;
  ativa: boolean;
}

export interface DependenciasCampo {
  campo: CampoCustom;
  dependencias: Dependencia[];
  pode_arquivar: boolean;
  mensagem: string;
}

export interface EtapaOpcao {
  id: number;
  nome: string;
  funil_nome: string;
  funil_id?: number;
}

/** Funil com as etapas, para "Exigir no funil" / "Escolher na etapa" (GET /comercial/funis, só o que a tela usa). */
export interface FunilOpcao {
  id: number;
  nome: string;
  etapas: { id: number; nome: string }[];
}

export interface EmpresaCurta {
  id: number;
  nome: string;
  documento: string | null;
  ativo: boolean;
  oportunidades: number;
  titulos: number;
}

export interface Duplicidade {
  a: EmpresaCurta;
  b: EmpresaCurta;
  motivo: string;
  semelhanca: number;
}

export interface MesclaResultado {
  empresa: Empresa;
  movidos: Record<string, number>;
  mensagem: string;
}

export interface ItemBusca {
  id: number;
  titulo: string;
  subtitulo: string | null;
  href: string;
}

export interface GrupoBusca {
  tipo: "empresas" | "pessoas" | "oportunidades" | "titulos";
  rotulo: string;
  itens: ItemBusca[];
}

export interface BuscaGlobal {
  termo: string;
  grupos: GrupoBusca[];
}

export interface UsuarioOpcao {
  id: number;
  nome: string;
  login: string | null;
}

// ---------------------------------------------------------------- consultas públicas (CNPJ / CEP)
export interface ConsultaCep {
  cep: string;
  logradouro: string | null;
  bairro: string | null;
  cidade: string | null;
  uf: string | null;
  fonte: string;
}

export interface ConsultaCnpj extends Endereco {
  documento: string;
  nome: string | null;
  nome_fantasia: string | null;
  segmento: string | null;
  porte: string | null;
  situacao: string | null;
  /** AAAA-MM-DD */
  abertura: string | null;
  telefone: string | null;
  email_financeiro: string | null;
  fonte: string;
  empresa_existente: { id: number; nome: string } | null;
  socios?: SocioConsulta[];
  cnae_principal?: string | null;
  cnaes_secundarios?: string[];
  natureza_juridica?: string | null;
  /** decimal em string ("10000.00") */
  capital_social?: string | null;
}

// ---------------------------------------------------------------- quadro societário e anexos da empresa
export interface SocioConsulta {
  nome: string;
  qualificacao: string | null;
  /** CPF vem mascarado da Receita: mostrar como veio */
  documento: string | null;
  /** AAAA-MM-DD */
  data_entrada: string | null;
  faixa_etaria: string | null;
}

export interface Socio extends SocioConsulta {
  id: number;
}

export type TipoAnexo = "cartao_cnpj" | "contrato" | "documento" | "outro";
export const ROTULO_TIPO_ANEXO: Record<TipoAnexo, string> = {
  cartao_cnpj: "Cartão CNPJ",
  contrato: "Contrato",
  documento: "Documento",
  outro: "Outro",
};

export interface AnexoEmpresa {
  id: number;
  nome: string;
  tipo: TipoAnexo;
  mime: string | null;
  tamanho: number;
  enviado_por_nome: string | null;
  /** instante ISO */
  criado_em: string;
  url: string | null;
}

// ---------------------------------------------------------------- planilhas de migração
export type ObjetoPlanilha = "empresas" | "fornecedores" | "pessoas" | "produtos" | "categorias" | "centros-custo" | "contas";

export interface ErroImportacao {
  linha: number;
  coluna: string | null;
  mensagem: string;
}

export interface PreviaImportacao {
  linha: number;
  acao: "criar" | "atualizar" | "ignorar";
  nome: string | null;
}

export interface ResultadoImportacao {
  total: number;
  criar: number;
  atualizar: number;
  ignorar: number;
  erros: ErroImportacao[];
  previa: PreviaImportacao[];
}

// ---------------------------------------------------------------- assinatura de e-mail do usuário (Minha conta)
/** Campos de assinatura que `GET/PATCH /auth/me` devolvem (ausentes até o backend publicá-los). */
export interface AssinaturaUsuario {
  assinatura_email?: string | null;
  /** caminho no storage (só indica que há imagem) */
  assinatura_imagem?: string | null;
  /** URL autenticada da imagem (como `foto_url`), quando o backend a devolver */
  assinatura_imagem_url?: string | null;
}
