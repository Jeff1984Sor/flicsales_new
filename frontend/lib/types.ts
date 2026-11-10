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

/** Corpo de POST /orquestracao/ia/perguntar (contrato proposto pelo frontend; o agente de IA confirma). */
export interface PerguntaIA {
  pergunta: string;
  escopo: "registro" | "modulo" | "global";
  contexto: { modulo: string; tela: string; rota: string; registro?: RegistroContexto | null };
}

/** Resposta estruturada: evidência, fonte e limite sempre presentes. Ações nascem propostas. */
export interface RespostaIA {
  titulo?: string | null;
  resumo: string;
  proxima_acao?: string | null;
  evidencias?: string[];
  fontes?: string[];
  limites?: string[];
  acoes_sugeridas?: { tipo: string; rotulo: string; dados?: Record<string, unknown> }[];
  ferramentas?: string[];
  /** false quando a IA está desligada e a resposta veio das regras determinísticas */
  ia_ativa?: boolean;
}
