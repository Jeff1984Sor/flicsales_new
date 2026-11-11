"use client";

/**
 * Campos padrões (fixos do sistema) configuráveis em "Campos de dados": visível no cadastro e obrigatório.
 *
 *  `const cp = useCamposPadroes("empresa")`
 *   - `cp.visivel("segmento")`        false esconde o campo do formulário (padrão true se a config não chegou)
 *   - `cp.obrigatorio("segmento")`    true marca "*" e exige no envio (padrão false)
 *   - `cp.faltando(valores, rotulos)` rótulo do 1º campo obrigatório e visível vazio (ou null) — use no submit
 *  Sem a rota publicada (404) ou sem permissão, tudo fica visível e opcional; o backend valida de qualquer forma.
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { CampoPadrao, ObjetoCampo } from "@/lib/tipos-nucleo";

const vazio = (v: unknown) => v == null || (typeof v === "string" && v.trim() === "") || (Array.isArray(v) && v.length === 0);

export function useCamposPadroesLista(objeto: ObjetoCampo) {
  return useQuery({
    queryKey: ["nucleo", "campos", "padroes", objeto],
    queryFn: () => api.get<CampoPadrao[]>("/nucleo/campos/padroes", { objeto }),
    staleTime: 60_000,
    retry: false,
    meta: { silencioso: true },
  });
}

export function useCamposPadroes(objeto: ObjetoCampo) {
  const { data } = useCamposPadroesLista(objeto);
  const mapa = new Map((data ?? []).map((c) => [c.campo, c]));
  const visivel = (campo: string) => mapa.get(campo)?.visivel ?? true;
  const obrigatorio = (campo: string) => {
    const c = mapa.get(campo);
    return !!c && c.visivel && c.obrigatorio;
  };
  const faltando = (valores: Record<string, unknown>, rotulos: Record<string, string> = {}) => {
    for (const c of data ?? []) {
      if (c.visivel && c.obrigatorio && c.campo in valores && vazio(valores[c.campo])) return rotulos[c.campo] ?? c.nome;
    }
    return null;
  };
  return { visivel, obrigatorio, faltando };
}
