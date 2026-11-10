"use client";

/**
 * Abrir o assistente JÁ com uma pergunta (o drawer pergunta sozinho). Complementa `abrirAssistente` de
 * components/flic/eventos.ts, usando o mesmo evento.
 *   perguntarAoAssistente("Toda a FlicSales", "Quais negociações podem afetar os recebimentos?")
 *   perguntarAoAssistente("Este registro", "Por que esta negociação está parada?", { tipo: "oportunidade", id: 12 })
 */
import { EVENTO_IA, type DetalheIA } from "@/components/flic/eventos";
import type { EscopoIA, RegistroContexto } from "@/lib/types";

export interface DetalheIAComPergunta extends DetalheIA {
  pergunta?: string;
}

export function perguntarAoAssistente(escopo: EscopoIA, pergunta: string, registro?: RegistroContexto | null) {
  window.dispatchEvent(new CustomEvent<DetalheIAComPergunta>(EVENTO_IA, { detail: { escopo, registro, pergunta } }));
}

/** Rota da tela onde o registro citado por uma evidência/ação é aberto. */
export function rotaDoRegistro(tipo: string | undefined): string | null {
  switch (tipo) {
    case "oportunidade":
      return "/comercial/oportunidades";
    case "atividade":
      return "/comercial/atividades";
    case "comunicacao":
      return "/comercial/comunicacoes";
    case "titulo":
      return "/financeiro/receber";
    case "empresa":
      return "/nucleo/cadastros";
    default:
      return null;
  }
}
