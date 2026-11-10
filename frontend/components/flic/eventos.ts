"use client";

/**
 * Eventos globais do shell (desacoplam telas do shell, sem contexto React):
 *
 *  - `abrirAssistente(escopo?, registro?)`  abre o drawer "Assistente de orquestração".
 *  - `abrirPaleta(termo?)`                   abre a paleta de comandos (busca global), já com o termo digitado.
 *  - `useAtalhoNovo(fn)`                     a tela decide o que Alt+N cria (oportunidade, título…). O shell dispara
 *                                            o evento `flic:novo`; só a tela montada reage.
 *
 * Atalhos (shell.tsx): Alt+N → `flic:novo` (se nenhuma tela registrou, o padrão do módulo: nova oportunidade no
 * Comercial, novo título a receber no Financeiro/Núcleo) · `/` → foca a busca do topo · Esc → fecha o drawer aberto.
 */
import { useEffect, useRef } from "react";

import type { EscopoIA, RegistroContexto } from "@/lib/types";

export const EVENTO_NOVO = "flic:novo";
export const EVENTO_IA = "flic:ia";
export const EVENTO_PALETA = "flic:paleta";

export interface DetalheIA {
  escopo: EscopoIA;
  registro?: RegistroContexto | null;
}

export function abrirAssistente(escopo: EscopoIA = "Este módulo", registro?: RegistroContexto | null) {
  window.dispatchEvent(new CustomEvent<DetalheIA>(EVENTO_IA, { detail: { escopo, registro } }));
}

export function abrirPaleta(termo = "") {
  window.dispatchEvent(new CustomEvent<string>(EVENTO_PALETA, { detail: termo }));
}

/** Quantas telas montadas registraram `useAtalhoNovo` (0 = o shell aplica o padrão do módulo). */
let telasComAtalho = 0;

/** Dispara Alt+N para a tela montada. Devolve false se nenhuma tela registrou o atalho. */
export function dispararNovo(): boolean {
  if (telasComAtalho === 0) return false;
  window.dispatchEvent(new Event(EVENTO_NOVO));
  return true;
}

/** Registra o que Alt+N faz nesta tela (ex.: abrir o drawer "Nova oportunidade"). */
export function useAtalhoNovo(fn: () => void) {
  const ref = useRef(fn);
  useEffect(() => {
    ref.current = fn;
  });
  useEffect(() => {
    const h = () => ref.current();
    telasComAtalho += 1;
    window.addEventListener(EVENTO_NOVO, h);
    return () => {
      telasComAtalho -= 1;
      window.removeEventListener(EVENTO_NOVO, h);
    };
  }, []);
}

/** O alvo do teclado é um campo de digitação? (atalhos de uma tecla não disparam dentro de campos) */
export function digitando(alvo: EventTarget | null) {
  if (!(alvo instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName) || alvo.isContentEditable;
}
