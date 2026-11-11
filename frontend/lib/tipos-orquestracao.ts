/**
 * Tipos da Orquestração (IA unificada, automações, integrações). Contratos de /api/orquestracao.
 * A resposta da IA/regras (formato único) é `RespostaIA` em lib/types.ts.
 */

export type AreaAutomacao = "comercial" | "financeiro";
export type EstadoAutomacao = "rascunho" | "ativa" | "pausada";
export type ModuloIA = "comercial" | "financeiro" | "nucleo";

export interface EstadoIA {
  ligada: boolean;
  provedor: string | null;
  modelo: string | null;
  configurar_em: string;
}

export interface Automacao {
  id: number;
  area: AreaAutomacao;
  nome: string;
  gatilho: string;
  gatilho_rotulo: string;
  funil_id: number | null;
  etapa_destino_id: number | null;
  campo: string | null;
  operador: string | null;
  valor_esperado: string | null;
  prazo_dias: number | null;
  acao: string;
  acao_rotulo: string;
  tipo_atividade: string | null;
  responsavel_regra: string | null;
  destinatario: string | null;
  conteudo: string;
  revisar_condicoes: boolean;
  estado: EstadoAutomacao;
  ativada_em: string | null;
  criado_em: string;
  atualizado_em: string;
}

/** Corpo de POST /orquestracao/automacoes (PATCH aceita os mesmos campos, menos `area`). */
export interface AutomacaoIn {
  area: AreaAutomacao;
  nome: string;
  gatilho: string;
  funil_id: number | null;
  etapa_destino_id: number | null;
  campo: string | null;
  operador: string | null;
  valor_esperado: string | null;
  prazo_dias: number | null;
  acao: string;
  tipo_atividade: string | null;
  responsavel_regra: string | null;
  destinatario: string | null;
  conteudo: string;
  revisar_condicoes: boolean;
}

export interface OpcaoCatalogo {
  id: string;
  rotulo: string;
}

export interface CatalogoAutomacoes {
  gatilhos: Record<AreaAutomacao, OpcaoCatalogo[]>;
  gatilhos_de_evento: string[];
  acoes: (OpcaoCatalogo & { envio: boolean })[];
  operadores: OpcaoCatalogo[];
  tipos_atividade: OpcaoCatalogo[];
  campos_padrao: Record<AreaAutomacao, { slug: string; nome: string }[]>;
  destinatarios: OpcaoCatalogo[];
  variaveis: string[];
  funis: { id: number; nome: string; etapas: { id: number; nome: string }[] }[];
  campos: { slug: string; nome: string; objeto: string; tipo: string; opcoes: string[] }[];
  canais_conectados: string[];
}

export interface ModeloAutomacao {
  chave: string;
  area: AreaAutomacao;
  nome: string;
  gatilho: string;
  gatilho_rotulo: string;
  acao: string;
  acao_rotulo: string;
  tipo_atividade: string | null;
  tipo_atividade_rotulo: string;
  descricao: string;
  prazo_dias: number | null;
  campo: string | null;
  operador: string | null;
  valor_esperado: string | null;
  etapa_destino_nome: string | null;
  etapa_destino_id: number | null;
  conteudo: string;
  destinatario: string | null;
  responsavel_regra: string;
}

export interface ExecucaoAutomacao {
  id: number;
  automacao_id: number;
  automacao_nome: string;
  area: AreaAutomacao;
  quando: string;
  registro: string | null;
  resultado: "executada" | "notificado" | "pendente_conector" | "falhou" | "simulada" | "em_execucao" | null;
  simulacao: boolean;
  erro: string | null;
  tentativas: number;
  detalhe: string | null;
  registro_criado: string | null;
}

export interface TesteAutomacao {
  elegiveis: number;
  ja_executadas: number;
  amostra: string[];
  acao: string;
  resumo: string;
  observacao: string;
}

export type TipoIntegracao = "google_calendar" | "outlook" | "email" | "whatsapp";
export type SituacaoIntegracao = "desconectado" | "conectado" | "erro" | "aguardando_conector";

export interface Integracao {
  tipo: TipoIntegracao;
  nome: string;
  grupo: string;
  descricao: string;
  estado: "desconectado" | "conectado" | "erro";
  situacao: SituacaoIntegracao;
  situacao_rotulo: string;
  conta: string | null;
  escopos: string[];
  escopos_disponiveis: string[];
  responsavel_id: number | null;
  segredo_definido: boolean;
  segredo_final: string | null;
  segredo_rotulo: string | null;
  requisitos: string[];
  fluxos_dependentes: string[];
  conectado_em: string | null;
  testado_em: string | null;
  ultimo_erro: string | null;
}

export interface IntegracaoIn {
  conta?: string | null;
  escopos?: string[];
  responsavel_id?: number | null;
  /** somente escrita: vazio = manter o segredo salvo */
  segredo?: string | null;
}

/** Integrações › WhatsApp pela Evolution API (GET /orquestracao/integracoes/whatsapp/evolution). */
export type EstadoEvolution = "conectado" | "desconectado" | "erro";

export interface ConfigEvolution {
  configurado: boolean;
  provedor: string | null;
  url: string | null;
  instancia: string | null;
  /** últimos caracteres da API key (somente escrita) */
  chave_final: string | null;
  estado: EstadoEvolution | null;
  numero?: string | null;
  testado_em: string | null;
  ultimo_erro: string | null;
}

/** PUT …/whatsapp/evolution — apikey vazia/ausente = manter a salva. */
export interface ConfigEvolutionIn {
  url: string;
  apikey?: string;
  instancia?: string | null;
}

export interface InstanciaEvolution {
  nome: string;
  /** conectado | conectando | desconectado */
  estado: string | null;
  numero: string | null;
}

export interface TesteEvolution {
  ok: boolean;
  estado: EstadoEvolution;
  mensagem: string;
}

export interface QrCodeEvolution {
  /** "data:image/png;base64,…" (ou só o base64) */
  base64?: string | null;
  codigo_pareamento?: string | null;
  estado?: "conectando" | "conectado" | null;
  mensagem?: string | null;
}

export interface ResultadoIntegracao {
  mensagem: string;
  integracao: Integracao;
}

export interface AnaliseComunicacao {
  comunicacao_id: number;
  origem: "ia" | "regras";
  analisada_em: string | null;
  analise: {
    necessidades: string[];
    objecoes: string[];
    compromissos: { quem: string; o_que: string; quando: string | null }[];
    citacoes: string[];
    limites: string[];
    fonte?: string;
  };
}

export interface AcaoExecutada {
  tipo: string;
  registro: { tipo: string; id: number; assunto?: string; prazo?: string };
  mensagem: string;
}

export interface UsuarioOpcao {
  id: number;
  nome: string;
  login: string | null;
}

/** GET /orquestracao/consumo — Plano e consumo (uso do mês da organização). */
export interface ConsumoOrganizacao {
  competencia: string; // "AAAA-MM"
  usuarios_ativos: number;
  perguntas_ia_mes: number;
  perguntas_ia_com_provedor_mes: number;
  automacoes_ativas: number;
  execucoes_mes: number;
}
