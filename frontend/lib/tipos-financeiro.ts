// Tipos da API do Financeiro (espelham backend/app/modules/financeiro/schemas.py). Dinheiro chega como string decimal.

export type Direcao = "receber" | "pagar";
export type StatusTitulo = "rascunho" | "aberto" | "parcial" | "liquidado" | "cancelado";
export type EstadoTitulo = StatusTitulo | "vencido";
export type FiltroEstado = "todos" | EstadoTitulo;
export type Forma = "pix" | "boleto" | "transferencia" | "cartao" | "dinheiro" | "outra";
export type Aprovacao = "pendente" | "aprovado";
export type Frequencia = "mensal" | "trimestral" | "anual";
export type SituacaoRecorrencia = "ativa" | "pausada" | "cancelada";
export type SituacaoCobranca = "em_acompanhamento" | "promessa_pagamento" | "em_contestacao" | "resolvida";
export type Canal = "email" | "ligacao" | "whatsapp";

export interface Titulo {
  id: number;
  direcao: Direcao;
  empresa_id: number;
  empresa_nome: string;
  descricao: string;
  documento: string | null;
  emissao: string | null;
  competencia: string | null;
  vencimento: string;
  valor_original: string;
  saldo: string;
  categoria_id: number | null;
  categoria_nome: string | null;
  centro_custo_id: number | null;
  centro_custo_nome: string | null;
  conta_prevista_id: number | null;
  conta_prevista_nome: string | null;
  forma: Forma | null;
  responsavel_id: number;
  responsavel_nome: string | null;
  observacoes: string | null;
  status: StatusTitulo;
  estado: EstadoTitulo;
  dias_atraso: number;
  aprovacao: Aprovacao | null;
  aprovado_por_nome: string | null;
  aprovado_em: string | null;
  motivo_cancelamento: string | null;
  cancelado_em: string | null;
  confirmado_em: string | null;
  origem_oportunidade_id: number | null;
  origem_recorrencia_id: number | null;
  parcela: number | null;
  parcelas_total: number | null;
  tem_baixa_ativa: boolean;
  em_contestacao: boolean;
  criado_em: string | null;
}

export interface Origem {
  tipo: "oportunidade" | "recorrencia" | "manual";
  id: number | null;
  rotulo: string;
}

export interface Baixa {
  id: number;
  titulo_id: number;
  direcao: Direcao;
  empresa_nome: string;
  titulo_descricao: string;
  valor: string;
  data: string;
  conta_id: number;
  conta_nome: string;
  forma: Forma;
  referencia_comprovante: string | null;
  observacao: string | null;
  registrada_por_nome: string | null;
  estornada: boolean;
  estorno_motivo: string | null;
  estornada_em: string | null;
  estornada_por_nome: string | null;
  criado_em: string | null;
}

export interface Cobranca {
  id: number;
  assunto: string;
  titulo_id: number;
  titulo_descricao: string;
  empresa_nome: string;
  titulo_saldo: string;
  titulo_estado: EstadoTitulo;
  responsavel_id: number;
  responsavel_nome: string | null;
  canal: Canal;
  situacao: SituacaoCobranca;
  data_prometida: string | null;
  valor_prometido: string | null;
  proximo_contato: string | null;
  historico: string;
  criado_em: string | null;
}

export interface TituloDetalhe extends Titulo {
  origem: Origem;
  baixas: Baixa[];
  cobrancas: Cobranca[];
}

export interface TituloIn {
  direcao: Direcao;
  empresa_id: number;
  descricao: string;
  documento: string | null;
  emissao: string | null;
  competencia: string | null;
  vencimento: string;
  valor_original: string;
  categoria_id: number | null;
  centro_custo_id: number | null;
  conta_prevista_id: number | null;
  forma: Forma | null;
  responsavel_id: number;
  observacoes: string | null;
  aprovacao?: Aprovacao | null;
}

export interface BaixaIn {
  valor: string;
  data: string;
  conta_id: number;
  forma: Forma;
  referencia_comprovante: string | null;
  observacao: string | null;
}

export interface Opcao {
  id: number;
  nome: string;
}

export interface OpcoesFinanceiro {
  empresas: (Opcao & { cliente: boolean; fornecedor: boolean })[];
  categorias: (Opcao & { natureza: "receita" | "despesa" })[];
  centros_custo: Opcao[];
  contas: (Opcao & { data_base: string })[];
}

export interface UsuarioOpcao {
  id: number;
  nome: string;
  login: string | null;
}

export type ContagensEstado = Record<FiltroEstado, number>;

export interface Transferencia {
  id: number;
  conta_origem_id: number;
  conta_origem_nome: string;
  conta_destino_id: number;
  conta_destino_nome: string;
  valor: string;
  data: string;
  descricao: string | null;
  criado_em: string | null;
}

export interface TransferenciaIn {
  conta_origem_id: number;
  conta_destino_id: number;
  valor: string;
  data: string;
  descricao: string | null;
}

export interface Recorrencia {
  id: number;
  descricao: string;
  direcao: Direcao;
  empresa_id: number;
  empresa_nome: string;
  valor_ciclo: string;
  frequencia: Frequencia;
  inicio: string;
  fim: string;
  dia_vencimento: number;
  categoria_id: number | null;
  categoria_nome: string | null;
  centro_custo_id: number | null;
  centro_custo_nome: string | null;
  responsavel_id: number | null;
  situacao: SituacaoRecorrencia;
  competencias_geradas: string[];
  proxima_competencia: string | null;
  criado_em: string | null;
}

export interface RecorrenciaIn {
  descricao: string;
  direcao: Direcao;
  empresa_id: number;
  valor_ciclo: string;
  frequencia: Frequencia;
  inicio: string;
  fim: string;
  dia_vencimento: number;
  categoria_id: number | null;
  centro_custo_id: number | null;
  responsavel_id: number | null;
  situacao: SituacaoRecorrencia;
}

export interface CobrancaIn {
  assunto: string;
  titulo_id: number;
  responsavel_id: number;
  canal: Canal;
  situacao: SituacaoCobranca;
  data_prometida: string | null;
  valor_prometido: string | null;
  proximo_contato: string | null;
  historico: string;
}

export interface Indicador {
  valor: string;
  detalhe: string;
  formula: string;
}

export interface ContaSaldo {
  id: number;
  nome: string;
  instituicao: string | null;
  saldo_inicial: string;
  data_base: string;
  saldo_atual: string;
  ativo: boolean;
}

export interface Caixa {
  saldo_gerencial: Indicador;
  entradas_abertas: Indicador;
  saidas_abertas: Indicador;
  saldo_apos_titulos: Indicador;
  contas: ContaSaldo[];
  limites: string[];
}

export interface FaixaAging {
  faixa: "a_vencer" | "1_30" | "31_60" | "61_90" | "90_mais";
  rotulo: string;
  valor: string;
  quantidade: number;
}

export interface Dashboards {
  caixa: Caixa;
  aging_receber: FaixaAging[];
  aging_pagar: FaixaAging[];
  hoje: string;
  limites: string[];
}

export interface EvidenciaLeitura {
  texto: string;
  fonte: string;
  registro?: { tipo: string; id: number };
}

/** Leitura do momento determinística (app.domain.leitura): mesmo formato da IA. */
export interface Leitura {
  titulo: string;
  analise: string;
  proxima_acao: string;
  evidencias: EvidenciaLeitura[];
  limites: string[];
  acoes_sugeridas: { tipo: string; rotulo: string; registro?: { tipo: string; id: number } }[];
  origem: string;
}

export interface FilaCobranca {
  titulo_id: number;
  empresa_nome: string;
  descricao: string;
  saldo: string;
  vencimento: string;
  dias_atraso: number;
  em_contestacao: boolean;
}

export interface HojeFinanceiro {
  hoje: string;
  /** null = perfil sem financeiro.caixa.ver (esconde o KPI). */
  saldo_gerencial: Indicador | null;
  recebiveis_vencidos: Indicador;
  recebiveis_vencidos_qtd: number;
  /** null = perfil não vê contas a pagar. */
  aprovacoes_pendentes: number | null;
  /** null = perfil sem financeiro.recorrencias.ver. */
  recorrencias_ativas: number | null;
  fila_cobranca: FilaCobranca[];
  leitura: Leitura;
  ia_ligada: boolean;
  limites: string[];
}
