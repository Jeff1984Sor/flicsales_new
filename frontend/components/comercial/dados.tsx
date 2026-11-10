"use client";

/**
 * Peças comuns às telas do Comercial: opções de formulário (empresas, pessoas, produtos, funis, campos), usuários
 * para escolher responsável, invalidação das consultas e utilitários de formulário.
 *
 *  - `useOpcoes()`           GET /comercial/oportunidades/opcoes (cache de 1 min)
 *  - `useUsuarios()`         GET /config/usuarios/opcoes
 *  - `useInvalidarComercial()` → função que invalida tudo do Comercial (depois de qualquer mutação)
 *  - `nulo(v)`               "" → null (campo vazio numérico/data vai como null, não "")
 *  - `lerForm(form)`         FormData → Record<string, string>
 *  - `CampoEmpresa`          input com datalist das empresas (selecionar OU criar pelo nome)
 *        Troque pelo `SeletorEmpresa` do Núcleo quando existir (mesmo contrato: devolve id ou nome).
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useId } from "react";

import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { OpcoesComerciais, UsuarioOpcao } from "@/lib/tipos-comercial";

export const CHAVE = "comercial";

export function useOpcoes() {
  return useQuery({
    queryKey: [CHAVE, "opcoes"],
    queryFn: () => api.get<OpcoesComerciais>("/comercial/oportunidades/opcoes"),
    staleTime: 60_000,
  });
}

export function useUsuarios() {
  return useQuery({
    queryKey: ["usuarios", "opcoes"],
    queryFn: () => api.get<UsuarioOpcao[]>("/config/usuarios/opcoes"),
    staleTime: 5 * 60_000,
  });
}

/** Depois de qualquer mutação do Comercial: tudo que é `["comercial", ...]` é recarregado. */
export function useInvalidarComercial() {
  const qc = useQueryClient();
  return useCallback(() => qc.invalidateQueries({ queryKey: [CHAVE] }), [qc]);
}

export const nulo = (v: FormDataEntryValue | string | null | undefined): string | null => {
  const s = typeof v === "string" ? v.trim() : "";
  return s === "" ? null : s;
};

export const numeroOuNulo = (v: FormDataEntryValue | string | null | undefined): number | null => {
  const s = nulo(v);
  return s === null ? null : Number(s);
};

export function lerForm(form: HTMLFormElement): Record<string, string> {
  const out: Record<string, string> = {};
  new FormData(form).forEach((v, k) => {
    if (typeof v === "string") out[k] = v;
  });
  return out;
}

/** Valor da empresa digitada: id se bate com uma empresa existente (nome igual, sem caixa), senão o nome (cria). */
export function empresaDoTexto(texto: string, empresas: { id: number; nome: string }[]) {
  const t = texto.trim();
  if (!t) return { empresa_id: null, empresa_nome: null };
  const achada = empresas.find((e) => e.nome.toLocaleLowerCase("pt-BR") === t.toLocaleLowerCase("pt-BR"));
  return achada ? { empresa_id: achada.id, empresa_nome: null } : { empresa_id: null, empresa_nome: t };
}

/** Input + datalist: escolha uma empresa da base compartilhada ou digite um nome novo (nasce como prospect). */
export function CampoEmpresa({
  name = "empresa",
  defaultValue,
  required,
  empresas,
}: {
  name?: string;
  defaultValue?: string | null;
  required?: boolean;
  empresas: { id: number; nome: string }[] | undefined;
}) {
  const lista = useId();
  return (
    <>
      <Input name={name} list={lista} defaultValue={defaultValue ?? ""} required={required} placeholder="Selecionar ou criar" autoComplete="off" />
      <datalist id={lista}>
        {(empresas ?? []).map((e) => (
          <option key={e.id} value={e.nome} />
        ))}
      </datalist>
    </>
  );
}

/** Hora "HH:MM:SS" da API → "HH:MM". */
export const hora = (v: string | null | undefined) => (v ? v.slice(0, 5) : "");

/** Percentual decimal da API ("33.3") → "33,3%". */
export const pct = (v: string | number | null | undefined) =>
  v == null ? "—" : `${Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
