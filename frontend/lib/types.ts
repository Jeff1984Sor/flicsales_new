// Tipos da API do core (espelham backend/app/core/schemas.py). Cada área acrescenta os seus em lib/tipos-<area>.ts.

export interface Pagina<T> {
  itens: T[];
  total: number;
  pagina: number;
  por_pagina: number;
}

/** Segredo cadastrado na tela: o valor NUNCA volta do servidor, só "definido" + últimos caracteres. */
export interface Segredo {
  definido: boolean;
  final: string | null;
}

export interface Mensagem {
  mensagem: string;
}

export interface UsuarioMe {
  id: number;
  nome: string;
  email: string;
  login: string | null;
  telefone: string | null;
  foto_url: string | null;
  preferencias: Record<string, unknown> & { menu_recolhido?: string[] };
  perfil_acesso_id: number | null;
  perfil_acesso_nome: string | null;
  administrador: boolean;
  /** Perfil com escopo "só meus registros" (ex.: Comercial vê só as próprias oportunidades). */
  somente_meus_registros?: boolean;
  /** Permissões "recurso.acao" (ex.: "comercial.oportunidades.ver"). */
  permissoes: string[];
  /** Organização da sessão (modo um banco por organização). Ausente no modo de um banco só. */
  organizacao?: { slug: string; nome: string; status: string } | null;
}

export interface IdentidadePublica {
  nome_exibicao: string;
  logo_url: string | null;
  cor_destaque: string | null;
}

export interface IdentidadeOut extends IdentidadePublica {
  assinatura_email: string | null;
}

export interface UsuarioOut {
  id: number;
  nome: string;
  email: string;
  login: string | null;
  telefone: string | null;
  foto_url: string | null;
  ativo: boolean;
  acesso_sistema: boolean;
  convite_pendente: boolean;
  ultimo_acesso: string | null;
  online: boolean;
  perfil_acesso_id: number | null;
  perfil_acesso_nome: string | null;
  perfil_acesso_cor: string | null;
}

export interface PerfilAcessoOut {
  id: number;
  nome: string;
  descricao: string | null;
  cor: string | null;
  administrador: boolean;
  sistema: boolean;
  somente_meus_registros?: boolean;
  permissoes: string[];
  qtd_usuarios: number;
}

export interface PerfilAcessoIn {
  nome: string;
  descricao: string | null;
  cor: string | null;
  administrador: boolean;
  somente_meus_registros: boolean;
  permissoes: string[];
}

export interface CatalogoPermissoes {
  grupos: { grupo: string; recursos: { id: string; nome: string; acoes: string[] }[] }[];
  acoes: Record<string, string>;
}

export interface ConfigEmailOut {
  remetente_nome: string;
  remetente_email: string;
  smtp_host: string | null;
  smtp_porta: number;
  smtp_usuario: string | null;
  smtp_senha_definida: boolean;
  copia_padrao: string[];
}

/** GET /auth/me/email — SMTP próprio (opcional) do usuário logado. A senha nunca volta. */
export interface ConfigEmailUsuarioOut {
  configurado: boolean;
  ativo: boolean;
  remetente_nome: string | null;
  remetente_email: string | null;
  smtp_host: string | null;
  smtp_porta: number | null;
  smtp_usuario: string | null;
  /** "••••abcd" quando há senha salva */
  senha_final: string | null;
}

/** PUT /auth/me/email — senha ausente/vazia mantém a salva. */
export interface ConfigEmailUsuarioIn {
  remetente_nome: string;
  remetente_email: string;
  smtp_host: string;
  smtp_porta: number;
  smtp_usuario: string | null;
  smtp_senha?: string;
  ativo: boolean;
}

export interface TesteConexao {
  ok: boolean;
  mensagem: string;
}

/** GET /auth/me/envio — habilita o botão Enviar e mostra "Enviar como …". */
export interface StatusEnvio {
  pode_enviar: boolean;
  via: "usuario" | "organizacao" | "outbox" | null;
  remetente: string | null;
  /** WhatsApp pela Evolution API da organização (ausente em backend antigo = sem WhatsApp). */
  whatsapp?: StatusWhatsApp | null;
}

export interface StatusWhatsApp {
  pode_enviar: boolean;
  numero?: string | null;
}

/** Corpo comum dos envios de e-mail pelas telas (comunicações, propostas, cobranças). */
export interface EnvioEmailIn {
  para: string[];
  cc?: string[];
  assunto: string;
  corpo: string;
  modelo_id?: number | null;
}

export interface EnvioEmailOut {
  ok: true;
  enviado_para: string[];
  registro: string;
}

/** Corpo comum dos envios por WhatsApp (comunicações, propostas, cobranças). Telefones em dígitos com DDI. */
export interface EnvioWhatsAppIn {
  para: string[];
  texto: string;
  modelo_id?: number | null;
}

export interface EnvioWhatsAppOut {
  ok: boolean;
  enviado_para: string[];
  registro: string;
}

export interface ConfigIAOut {
  ativo: boolean;
  provedor: "openai" | "gemini";
  modelo: string | null;
  chave_definida: boolean;
  chave_final: string | null;
  provedores: Record<string, string>;
}

export interface AuditoriaOut {
  id: number;
  usuario_nome: string | null;
  acao: string;
  entidade: string;
  entidade_id: string | null;
  descricao: string | null;
  antes_json: Record<string, unknown> | null;
  depois_json: Record<string, unknown> | null;
  ip: string | null;
  criado_em: string;
}

// ---------------------------------------------------------------- IA unificada (orquestração)

/** Escopo da conversa com a IA, como aparece na tela. */
export type EscopoIA = "Este registro" | "Este módulo" | "Toda a FlicSales";

/** Registro em foco (para o escopo "Este registro"). */
export interface RegistroContexto {
  /** tipo do registro: "oportunidade", "titulo", "empresa"… */
  tipo: string;
  id: number | string;
  /** rótulo legível ("Aurora Consultoria · Projeto de consultoria") */
  rotulo?: string;
}

/** Corpo de POST /orquestracao/ia/perguntar (contrato da Orquestração). */
export interface PerguntaIA {
  pergunta: string;
  escopo: "registro" | "modulo" | "tudo";
  modulo?: "comercial" | "financeiro" | "nucleo" | null;
  tela?: string | null;
  registro?: { tipo: string; id: number } | null;
  /** continua uma conversa já aberta */
  conversa_id?: number | null;
}

/** Evidência: de onde veio (fonte) + o dado que sustenta (trecho). */
export interface EvidenciaIA {
  fonte: string;
  trecho: string;
  registro?: { tipo: string; id: number };
}

/** Ação sugerida: nasce PROPOSTA. `criar_atividade` vira registro após o clique (POST /orquestracao/acoes/executar);
 *  `abrir_registro` é atalho de navegação. */
export interface AcaoSugeridaIA {
  tipo: "criar_atividade" | "abrir_registro" | (string & {});
  rotulo: string;
  payload: Record<string, unknown>;
}

/** Formato ÚNICO de resposta (IA e regras): evidência, fonte e limite sempre presentes. */
export interface RespostaIA {
  titulo: string;
  analise: string;
  proxima_acao: string;
  evidencias: EvidenciaIA[];
  limites: string[];
  acoes_sugeridas: AcaoSugeridaIA[];
  /** "regras" = IA desligada ou indisponível: leitura determinística */
  origem: "ia" | "regras";
  /** assistentes/fontes consultados (cada um dentro das permissões do perfil) */
  ferramentas: string[];
  ia_ligada?: boolean;
  conversa_id?: number | null;
  mensagem_id?: number | null;
}
