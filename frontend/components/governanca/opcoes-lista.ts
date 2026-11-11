"use client";

/**
 * useOpcoesLista(tipo) — opções ATIVAS de uma lista da Governança de ajustes (segmento · porte · motivo_perda), na ordem.
 * Alimenta selects (empresa, fornecedor, perder oportunidade). Silenciosa: enquanto a rota não existir (404), devolve
 * `[]` e `indisponivel = true` — quem usa cai no campo de texto livre.
 *
 * Ex.: const { opcoes, indisponivel } = useOpcoesLista("motivo_perda");
 */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { OpcaoLista, TipoLista } from "@/lib/tipos-governanca";

export const chaveLista = (tipo: TipoLista) => ["nucleo", "listas", tipo] as const;

export function useOpcoesLista(tipo: TipoLista) {
  const q = useQuery({
    queryKey: [...chaveLista(tipo), "ativas"],
    queryFn: () => api.get<OpcaoLista[]>(`/nucleo/listas/${tipo}`),
    staleTime: 60_000,
    retry: false,
    meta: { silencioso: true },
  });
  const opcoes = (q.data ?? []).filter((o) => o.ativo !== false).sort((a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome));
  return { opcoes, carregando: q.isPending, indisponivel: q.isError };
}
