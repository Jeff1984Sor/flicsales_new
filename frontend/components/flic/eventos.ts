"use client";

/**
 * Eventos globais do shell (desacoplam telas do shell, sem contexto React):
 *
 *  - `abrirAssistente(escopo?, registro?)`  abre o drawer "Assistente de orquestração".
 *  - `abrirPaleta(termo?)`                   abre a paleta de comandos (busca global), já com o termo digitado.
 *  - `useAtalhoNovo(fn)`                     a tela decide o que Alt+N cria (oportunidade, título…). O shell dispara
 *                                            o evento `flic:novo`; só a tela montada reage.
 *
 * Atalhos (shell.tsx): Alt+N → `flic:novo` · `/` → foca a busca do topo · Esc → fecha o drawer aberto.
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

export function dispararNovo() {
  window.dispatchEvent(new Event(EVENTO_NOVO));
}

/** Registra o que Alt+N faz nesta tela (ex.: abrir o drawer "Nova oportunidade"). */
export function useAtalhoNovo(fn: () => void) {
  const ref = useRef(fn);
  useEffect(() => {
    ref.current = fn;
  });
  useEffect(() => {
    const h = () => ref.current();
    window.addEventListener(EVENTO_NOVO, h);
    return () => window.removeEventListener(EVENTO_NOVO, h);
  }, []);
}

/** O alvo do teclado é um campo de digitação? (atalhos de uma tecla não disparam dentro de campos) */
export function digitando(alvo: EventTarget | null) {
  if (!(alvo instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName) || alvo.isContentEditable;
}
