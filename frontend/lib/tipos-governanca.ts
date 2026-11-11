/**
 * Tipos da Governança de ajustes (Núcleo › Administração › `/nucleo/governanca`).
 *
 * Listas de opção da plataforma (tabela `opcao_lista`):
 *  - `GET   /api/nucleo/listas/{tipo}`                     ativas, na ordem (livre para logados — alimenta selects)
 *  - `GET   /api/nucleo/listas/{tipo}?incluir_inativos=true` todas (tela de governança)
 *  - `POST  /api/nucleo/listas/{tipo}`                     { nome }
 *  - `PATCH /api/nucleo/listas/{tipo}/{id}`                { nome?, ativo? } (inativar; nada se exclui)
 *  - `POST  /api/nucleo/listas/{tipo}/reordenar`           { ids: number[] } na ordem nova
 */
export type TipoLista = "segmento" | "porte" | "motivo_perda";

export interface OpcaoLista {
  id: number;
  tipo: TipoLista;
  nome: string;
  ordem: number;
  ativo: boolean;
  criado_em?: string | null;
}

export const ROTULO_LISTA: Record<TipoLista, { plural: string; singular: string; novo: string; descricao: string }> = {
  segmento: {
    plural: "Segmentos",
    singular: "Segmento",
    novo: "+ Segmento",
    descricao: "Opções de segmento no cadastro de empresas e fornecedores.",
  },
  porte: {
    plural: "Portes",
    singular: "Porte",
    novo: "+ Porte",
    descricao: "Opções de porte no cadastro de empresas e fornecedores.",
  },
  motivo_perda: {
    plural: "Motivos de perda",
    singular: "Motivo de perda",
    novo: "+ Motivo de perda",
    descricao: "Opções ao registrar uma oportunidade perdida. “Outro” continua aceitando texto livre.",
  },
};
