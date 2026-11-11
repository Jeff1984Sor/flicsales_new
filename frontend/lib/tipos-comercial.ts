// Tipos da API do Comercial (/api/comercial) — espelham backend/app/modules/comercial/schemas.py.
// Dinheiro chega como string decimal ("24000.00"); datas-de-dia como "AAAA-MM-DD"; horas como "HH:MM:SS".

export type Decimal = string;

export interface Etapa {
  id: number;
  funil_id: number;
  nome: string;
  ordem: number;
  probabilidade: number;
  limite_dias: number | null;
  criterios: string | null;
}

export interface Funil {
  id: number;
  nome: string;
  ativo: boolean;
  etapas: Etapa[];
}

export type Resultado = "aberta" | "ganha" | "perdida";

export interface Oportunidade {
  id: number;
  titulo: string;
  funil_id: number;
  funil_nome: string | null;
  etapa_id: number | null;
  etapa_nome: string | null;
  etapa_probabilidade: number | null;
  resultado: Resultado;
  empresa_id: number | null;
  empresa_nome: string | null;
  contato_id: number | null;
  contato_nome: string | null;
  responsavel_id: number;
  responsavel_nome: string | null;
  valor_unico: Decimal;
  valor_recorrente_mensal: Decimal;
  previsao_fechamento: string | null;
  proxima_acao: string | null;
  proxima_acao_prazo: string | null;
  origem: string | null;
  necessidade: string | null;
  decisor: string | null;
  orcamento_concorrencia: string | null;
  criterio_sucesso: string | null;
  motivo_perda: string | null;
  concorrente: string | null;
  data_retomada: string | null;
  ganha_em: string | null;
  perdida_em: string | null;
  entrou_etapa_em: string | null;
  dias_na_etapa: number;
  alem_do_limite: boolean;
  interesse: string | null;
  campos_custom: Record<string, unknown>;
  criado_em: string;
}

export interface Recebivel {
  id: number;
  descricao: string;
  valor_original: Decimal;
  saldo: Decimal;
  vencimento: string;
  status: string;
  parcela: number | null;
  parcelas_total: number | null;
}

export interface OportunidadeDetalhe extends Oportunidade {
  contexto: { texto: string; fonte: string | null; limite: string };
  /** Vazio para quem não tem financeiro.titulos.ver (aí só vem a quantidade em recebiveis_preparados). */
  recebiveis: Recebivel[];
  recebiveis_preparados: number;
  atividades_pendentes: number;
  comunicacoes: number;
  propostas: number;
}

export interface Evento {
  id: number;
  quando: string;
  tipo: "criada" | "etapa" | "ganha" | "perdida" | "reaberta" | "proxima_acao" | "proposta" | "reuniao" | "nota";
  texto: string;
  usuario_id: number | null;
  usuario_nome: string | null;
}

export interface GanhoOut {
  oportunidade: Oportunidade;
  recebiveis: Recebivel[];
  mensagem: string;
}

/** Corpo de criar/editar oportunidade. `empresa_nome` cria a empresa (prospect) se ainda não existir. */
export interface OportunidadeEntrada {
  titulo?: string;
  funil_id?: number;
  etapa_id?: number | null;
  empresa_id?: number | null;
  empresa_nome?: string | null;
  responsavel_id?: number | null;
  contato_id?: number | null;
  valor_unico?: string | null;
  valor_recorrente_mensal?: string | null;
  previsao_fechamento?: string | null;
  proxima_acao?: string | null;
  proxima_acao_prazo?: string | null;
  origem?: string | null;
  necessidade?: string | null;
  decisor?: string | null;
  orcamento_concorrencia?: string | null;
  criterio_sucesso?: string | null;
  interesse?: string | null;
}

export interface Opcao {
  id: number;
  nome: string;
}

export interface CampoOpcao {
  id: number;
  nome: string;
  slug: string;
  tipo: string;
  objeto: string;
  opcoes: string[];
}

export interface OpcoesComerciais {
  empresas: Opcao[];
  pessoas: (Opcao & { empresa_id: number | null })[];
  produtos: (Opcao & { preco_referencia: Decimal | null; recorrente: boolean })[];
  oportunidades: (Opcao & { empresa_id: number | null; resultado: Resultado })[];
  funis: Funil[];
  campos: CampoOpcao[];
  condicoes_ganho: string[];
  interesse: string[];
}

export interface UsuarioOpcao {
  id: number;
  nome: string;
  login: string | null;
}

// ---------------------------------------------------------------------------------------------- atividades
export type TipoAtividade = "tarefa" | "email" | "ligacao" | "whatsapp" | "reuniao";

export const TIPOS_ATIVIDADE: { valor: TipoAtividade; rotulo: string }[] = [
  { valor: "tarefa", rotulo: "Tarefa" },
  { valor: "email", rotulo: "E-mail" },
  { valor: "ligacao", rotulo: "Ligação" },
  { valor: "whatsapp", rotulo: "WhatsApp" },
  { valor: "reuniao", rotulo: "Reunião" },
];

export const rotuloTipoAtividade = (t: string) => TIPOS_ATIVIDADE.find((x) => x.valor === t)?.rotulo ?? t;

export interface Atividade {
  id: number;
  assunto: string;
  tipo: TipoAtividade;
  responsavel_id: number;
  responsavel_nome: string | null;
  empresa_id: number | null;
  empresa_nome: string | null;
  oportunidade_id: number | null;
  oportunidade_titulo: string | null;
  prazo: string;
  hora_inicio: string | null;
  hora_fim: string | null;
  fuso: string;
  participantes: string | null;
  canal: string | null;
  objetivo: string | null;
  resultado: string | null;
  status: "pendente" | "concluida";
  concluida_em: string | null;
  origem: "manual" | "ia" | "automacao";
  atrasada: boolean;
}

export interface AtividadeEntrada {
  assunto: string;
  tipo: TipoAtividade;
  responsavel_id?: number | null;
  empresa_id?: number | null;
  oportunidade_id?: number | null;
  prazo: string;
  hora_inicio?: string | null;
  hora_fim?: string | null;
  fuso?: string | null;
  participantes?: string | null;
  canal?: string | null;
  objetivo?: string | null;
  resultado?: string | null;
  origem?: "manual" | "ia" | "automacao";
}

// ---------------------------------------------------------------------------------------------- comunicações
export type CanalComunicacao = "reuniao" | "email" | "whatsapp" | "notas";

export const CANAIS_COMUNICACAO: { valor: CanalComunicacao; rotulo: string }[] = [
  { valor: "notas", rotulo: "Notas de reunião" },
  { valor: "reuniao", rotulo: "Reunião" },
  { valor: "email", rotulo: "E-mail" },
  { valor: "whatsapp", rotulo: "WhatsApp" },
];

export const rotuloCanal = (c: string) =>
  ({ reuniao: "Reunião", email: "E-mail", whatsapp: "WhatsApp", notas: "Notas" })[c] ?? c;

export interface AnaliseComunicacao {
  necessidades: string[];
  objecoes: string[];
  compromissos: string[];
  citacoes: { trecho: string; fonte: string | null }[];
  limites: string[];
  origem?: string;
  resumo?: string;
  tarefa_sugerida?: { assunto?: string; prazo?: string; tipo?: TipoAtividade } | string;
}

export interface Comunicacao {
  id: number;
  canal: CanalComunicacao;
  titulo: string | null;
  conteudo: string;
  data: string | null;
  empresa_id: number | null;
  empresa_nome: string | null;
  oportunidade_id: number | null;
  oportunidade_titulo: string | null;
  analise: AnaliseComunicacao | null;
  analisada_em: string | null;
  criado_em: string;
}

// ---------------------------------------------------------------------------------------------- propostas
export type StatusProposta = "rascunho" | "em_aprovacao" | "aprovada_internamente" | "enviada" | "aceita" | "recusada";

export const STATUS_PROPOSTA: { valor: StatusProposta; rotulo: string }[] = [
  { valor: "rascunho", rotulo: "Rascunho" },
  { valor: "em_aprovacao", rotulo: "Em aprovação" },
  { valor: "aprovada_internamente", rotulo: "Aprovada internamente" },
  { valor: "enviada", rotulo: "Enviada" },
  { valor: "aceita", rotulo: "Aceita" },
  { valor: "recusada", rotulo: "Recusada" },
];

export const CONDICOES_PROPOSTA = ["À vista", "2 parcelas", "3 parcelas", "Recorrente mensal"];

export interface Proposta {
  id: number;
  titulo: string;
  oportunidade_id: number;
  oportunidade_titulo: string | null;
  empresa_id: number;
  empresa_nome: string | null;
  versao: number;
  escopo: string;
  produto_id: number | null;
  produto_nome: string | null;
  quantidade: Decimal;
  preco_unitario: Decimal;
  desconto_pct: Decimal;
  mensalidade_adicional: Decimal;
  validade: string;
  condicao: string;
  responsavel_id: number;
  responsavel_nome: string | null;
  status: StatusProposta;
  justificativa_desconto: string | null;
  total: Decimal;
  criado_em: string;
  /** modelo de proposta usado (ausente em backend antigo) */
  modelo_proposta_id?: number | null;
  /** só na proposta automática: ex. "IA desligada: escopo montado pelo cadastro do produto." */
  aviso?: string | null;
}

/** POST /comercial/oportunidades/{id}/proposta-automatica */
export interface PropostaAutomaticaIn {
  modelo_proposta_id: number | null;
  produto_id: number | null;
  usar_ia: boolean;
}

/** Gestão comercial › Modelos de proposta (GET /comercial/modelos-proposta). */
export interface ModeloProposta {
  id: number;
  nome: string;
  padrao: boolean;
  introducao: string | null;
  termos: string | null;
  rodape: string | null;
  validade_dias: number;
  condicao_padrao: string | null;
  ativo: boolean;
  variaveis: string[];
}

export interface ModeloPropostaIn {
  nome?: string;
  padrao?: boolean;
  introducao?: string | null;
  termos?: string | null;
  rodape?: string | null;
  validade_dias?: number;
  condicao_padrao?: string | null;
  ativo?: boolean;
}

/** Variáveis aceitas nos textos do modelo de proposta (clicáveis no formulário). */
export const VARIAVEIS_PROPOSTA: { chave: string; rotulo: string }[] = [
  { chave: "empresa.nome", rotulo: "Empresa" },
  { chave: "empresa.cnpj", rotulo: "CNPJ" },
  { chave: "contato.nome", rotulo: "Contato" },
  { chave: "oportunidade.titulo", rotulo: "Oportunidade" },
  { chave: "proposta.titulo", rotulo: "Título da proposta" },
  { chave: "proposta.total", rotulo: "Total" },
  { chave: "proposta.validade", rotulo: "Validade" },
  { chave: "proposta.condicao", rotulo: "Condição" },
  { chave: "responsavel.nome", rotulo: "Responsável" },
  { chave: "hoje", rotulo: "Data de hoje" },
];

// ---------------------------------------------------------------------------------------------- metas e forecast
export type IndicadorMeta = "receita_unica_ganha" | "mrr_novo" | "vendas_ganhas" | "atividades_concluidas";

export const INDICADORES_META: { valor: IndicadorMeta; rotulo: string; moeda: boolean }[] = [
  { valor: "receita_unica_ganha", rotulo: "Receita única ganha", moeda: true },
  { valor: "mrr_novo", rotulo: "MRR novo", moeda: true },
  { valor: "vendas_ganhas", rotulo: "Vendas ganhas", moeda: false },
  { valor: "atividades_concluidas", rotulo: "Atividades concluídas", moeda: false },
];

export interface Meta {
  id: number;
  nome: string;
  responsavel_tipo: "pessoa" | "equipe";
  responsavel_id: number | null;
  responsavel_nome: string | null;
  equipe: string | null;
  inicio: string;
  fim: string;
  indicador: IndicadorMeta;
  alvo: Decimal;
  funil_id: number | null;
  funil_nome: string | null;
  realizado: Decimal;
  percentual: Decimal | null;
  formula: string;
}

export interface Forecast {
  pipeline_aberto: Decimal;
  ponderado: Decimal;
  mrr_potencial: Decimal;
  sem_previsao: number;
  abertas: number;
  por_etapa: { etapa: string; probabilidade: number; quantidade: number; valor: Decimal; ponderado: Decimal }[];
  formulas: Record<"pipeline_aberto" | "ponderado" | "mrr_potencial" | "sem_previsao", string>;
  limite: string;
}

// ---------------------------------------------------------------------------------------------- desempenho
export interface IndicadorCalculado {
  valor: Decimal | null;
  detalhe: string;
  formula: string;
}

export interface VendedorDesempenho {
  usuario_id: number;
  nome: string;
  ganhas: number;
  perdidas: number;
  encerradas: number;
  conversao: Decimal | null;
  receita: Decimal;
  sem_proxima_acao: number;
}

export interface Desempenho {
  inicio: string;
  fim: string;
  encerradas: number;
  conversao: IndicadorCalculado;
  receita_ganha: IndicadorCalculado;
  ticket_medio: IndicadorCalculado;
  ciclo_mediano: IndicadorCalculado;
  vendedores: VendedorDesempenho[];
  limites: string[];
}

export interface Evidencias {
  usuario_id: number;
  nome: string;
  inicio: string;
  fim: string;
  ganhas: Oportunidade[];
  perdidas: Oportunidade[];
  sem_proxima_acao: Oportunidade[];
  alem_do_limite: Oportunidade[];
  atividades_atrasadas: Atividade[];
  gargalo: string;
  acao_sugerida: string;
  limites: string[];
}

// ---------------------------------------------------------------------------------------------- dashboards
export interface PreviaIndicador {
  valor: Decimal;
  quantidade: number;
  descricao: string;
  formula: string;
}

export interface IndicadorConfig {
  id: number;
  nome: string;
  objeto: string;
  metrica: "soma_valor_unico" | "quantidade";
  filtro_campo_id: number | null;
  filtro_campo_nome: string | null;
  filtro_valor: string | null;
  ativo: boolean;
  resultado: PreviaIndicador | null;
}

export interface Dashboard {
  pipeline_alto_interesse: Decimal;
  oportunidades: number;
  recebiveis: number;
  proximas_acoes: number;
  funil_id: number | null;
  pipeline_por_etapa: { etapa: string; quantidade: number; valor: Decimal }[];
  indicadores: IndicadorConfig[];
}

// ---------------------------------------------------------------------------------------------- playbooks e modelos
export interface Playbook {
  id: number;
  nome: string;
  funil_id: number | null;
  funil_nome: string | null;
  etapa_id: number | null;
  etapa_nome: string | null;
  objetivo: string;
  perguntas_discovery: string | null;
  criterios_avanco: string;
  objecoes: string | null;
  proxima_acao_padrao: string | null;
  responsavel_id: number | null;
  responsavel_nome: string | null;
  ativo: boolean;
}

export type CanalModelo = "email" | "whatsapp" | "ligacao" | "reuniao";
export type FinalidadeModelo = "prospeccao" | "follow_up" | "proposta" | "cobranca" | "renovacao";

export const CANAIS_MODELO: { valor: CanalModelo; rotulo: string }[] = [
  { valor: "email", rotulo: "E-mail" },
  { valor: "whatsapp", rotulo: "WhatsApp" },
  { valor: "ligacao", rotulo: "Ligação" },
  { valor: "reuniao", rotulo: "Reunião" },
];

export const FINALIDADES_MODELO: { valor: FinalidadeModelo; rotulo: string }[] = [
  { valor: "prospeccao", rotulo: "Prospecção" },
  { valor: "follow_up", rotulo: "Follow-up" },
  { valor: "proposta", rotulo: "Proposta" },
  { valor: "cobranca", rotulo: "Cobrança" },
  { valor: "renovacao", rotulo: "Renovação" },
];

/** Classificação do modelo: Comercial lista comercial+geral; Financeiro (cobranças) lista financeiro+geral. */
export type ClassificacaoModelo = "comercial" | "financeiro" | "geral";

export const CLASSIFICACOES_MODELO: { valor: ClassificacaoModelo; rotulo: string }[] = [
  { valor: "comercial", rotulo: "Comercial" },
  { valor: "financeiro", rotulo: "Financeiro" },
  { valor: "geral", rotulo: "Geral" },
];

export interface ModeloComunicacao {
  id: number;
  nome: string;
  canal: CanalModelo;
  finalidade: FinalidadeModelo;
  /** ausente enquanto o backend não publicar a coluna: trate como "comercial" */
  classificacao?: ClassificacaoModelo;
  assunto: string | null;
  conteudo: string;
  status: "rascunho" | "revisado";
  ativo: boolean;
  variaveis: string[];
}

export interface PreviaModelo {
  assunto: string | null;
  conteudo: string;
  faltando: string[];
  aviso: string;
}

// ---------------------------------------------------------------------------------------------- hoje
export interface LeituraMomento {
  titulo: string;
  analise: string;
  proxima_acao: string | null;
  evidencias: { texto?: string; trecho?: string; fonte: string; registro?: { tipo: string; id: number } }[];
  limites: string[];
  acoes_sugeridas: { tipo: string; rotulo: string; registro?: { tipo: string; id: number }; payload?: Record<string, unknown> }[];
  origem: string;
}

export interface SaudeEtapa {
  etapa_id: number;
  etapa: string;
  quantidade: number;
  valor: Decimal;
  probabilidade: number;
}

export interface Hoje {
  nome: string;
  hoje: string;
  pipeline_aberto: Decimal;
  oportunidades_ativas: number;
  em_negociacao: Decimal;
  em_negociacao_qtd: number;
  em_negociacao_etapa: string | null;
  tarefas_do_dia: number;
  recebiveis_vinculados: number;
  atencao: Atividade[];
  agenda: Atividade[];
  agenda_conectada: boolean;
  saude_funil: SaudeEtapa[];
  funil_nome: string | null;
  leitura: LeituraMomento;
  ia_ligada: boolean;
}
