// Tipos da API do Núcleo (/bff/nucleo/*). Espelham backend/app/modules/nucleo/schemas.py.
// Dinheiro chega como string decimal ("1234.50"); datas-de-dia como "AAAA-MM-DD".

export type Papel = "prospect" | "cliente" | "fornecedor" | "parceiro";
export type Situacao = "ativos" | "inativos" | "todos";
export type CanalPreferido = "email" | "ligacao" | "whatsapp";
export type TipoProduto = "servico" | "produto";
export type Natureza = "receita" | "despesa";
export type TipoCampo = "texto" | "numero" | "moeda" | "data" | "sim_nao" | "lista";
export type ObjetoCampo = "empresa" | "pessoa" | "oportunidade";

/** Valor de um campo personalizado como a API guarda: texto, número, moeda ("1234.50"), data ("AAAA-MM-DD"), sim/não. */
export type ValorCampo = string | number | boolean | null;
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
  lista: "Lista",
};
export const ROTULO_OBJETO: Record<ObjetoCampo, string> = { empresa: "Empresa", pessoa: "Pessoa", oportunidade: "Oportunidade" };

export interface ContatoResumo {
  id: number;
  nome: string;
  cargo: string | null;
  email: string | null;
  telefone: string | null;
}

export interface Empresa {
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
  /** relacionamentos: oportunidades (todas) e títulos a receber não cancelados */
  oportunidades: number;
  titulos_receber: number;
  saldo_receber: string;
}

export interface EmpresaDetalhe extends Empresa {
  contatos: ContatoResumo[];
}

export interface EmpresaEntrada {
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

export interface Pessoa {
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

export interface Fornecedor {
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
