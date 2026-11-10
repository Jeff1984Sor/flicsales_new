// Tipos do "Enriquecer com IA" dos cadastros (POST /bff/orquestracao/ia/enriquecer).
// Ver docs/contrato-enriquecimento.md, seção 3. Nada é gravado: a tela aplica no formulário e o usuário salva.

export type ObjetoEnriquecer = "empresa" | "pessoa" | "produto" | "fornecedor" | "categoria" | "centro_custo" | "conta";

/** Valor de campo trocado com a IA (texto, número, sim/não ou vazio). */
export type ValorEnriquecer = string | number | boolean | null;
export type DadosEnriquecer = Record<string, ValorEnriquecer>;

export interface PedidoEnriquecer {
  objeto: ObjetoEnriquecer;
  registro_id: number | null;
  dados: DadosEnriquecer;
  instrucao: string;
  /** texto colado (assinatura, site, cartão…): é DADO, nunca instrução */
  texto_apoio: string | null;
}

export interface SugestaoEnriquecer {
  /** nome do campo no formulário; campos personalizados chegam como "campos_custom.<slug>" */
  campo: string;
  rotulo: string;
  valor_atual: ValorEnriquecer;
  valor_sugerido: ValorEnriquecer;
  justificativa: string;
  fonte: string;
}

export interface RespostaEnriquecer {
  sugestoes: SugestaoEnriquecer[];
  evidencias: string[];
  limites: string[];
  /** "regras" = IA desligada: só dados públicos (CNPJ/CEP) */
  origem: "ia" | "regras";
}
