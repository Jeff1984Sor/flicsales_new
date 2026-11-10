"use client";

/**
 * SeletorEmpresa — "selecionar ou criar" empresa (cadastro único do Núcleo). Digite para buscar; se não existir,
 * "+ Criar “Nome”" cria na hora (o nome basta) e já seleciona. Nome duplicado nunca é criado: a busca é sem acento
 * e a API recusa nome repetido.
 *
 * Props:
 *  - `valor: number | null`                                   id da empresa selecionada
 *  - `onChange: (id: number | null, empresa: EmpresaEscolhida | null) => void`
 *  - `permitirCriar?: boolean`                                padrão true (exige `nucleo.cadastros.editar`)
 *  - `papeisAoCriar?: Papel[]`                                papéis da empresa criada aqui (padrão ["prospect"];
 *                                                              no Financeiro use ["cliente"] ou ["fornecedor"])
 *  - `papel?: Papel`                                          só sugere empresas com este papel (ex.: "fornecedor")
 *  - `placeholder?: string`  `id?: string`  `disabled?: boolean`  `autoFocus?: boolean`
 *
 * Ex.: <Field label="Empresa"><SeletorEmpresa valor={empresaId} onChange={(id) => setEmpresaId(id)} /></Field>
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Loader2, Plus, X } from "lucide-react";
import { useDeferredValue, useId, useRef, useState } from "react";

import { notificar } from "@/components/flic/toast";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Pagina } from "@/lib/types";
import { ROTULO_PAPEL, type Empresa, type Papel } from "@/lib/tipos-nucleo";
import { cn } from "@/lib/utils";

export interface EmpresaEscolhida {
  id: number;
  nome: string;
  papeis: Papel[];
  criada?: boolean;
}

const chave = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

export function SeletorEmpresa({
  valor,
  onChange,
  permitirCriar = true,
  papeisAoCriar = ["prospect"],
  papel,
  placeholder = "Buscar ou criar empresa",
  id,
  disabled,
  autoFocus,
}: {
  valor: number | null;
  onChange: (id: number | null, empresa: EmpresaEscolhida | null) => void;
  permitirCriar?: boolean;
  papeisAoCriar?: Papel[];
  papel?: Papel;
  placeholder?: string;
  id?: string;
  disabled?: boolean;
  autoFocus?: boolean;
}) {
  const { pode } = useAuth();
  const qc = useQueryClient();
  const listaId = useId();
  const [texto, setTexto] = useState("");
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0);
  const termo = useDeferredValue(texto.trim());
  const caixa = useRef<HTMLDivElement>(null);
  const podeCriar = permitirCriar && pode("nucleo.cadastros.editar");

  const selecionada = useQuery({
    queryKey: ["nucleo", "empresas", "item", valor],
    queryFn: () => api.get<Empresa>(`/nucleo/empresas/${valor}`),
    enabled: valor != null,
    staleTime: 60_000,
    meta: { silencioso: true },
  });
  const busca = useQuery({
    queryKey: ["nucleo", "empresas", "seletor", termo, papel ?? ""],
    queryFn: () => api.get<Pagina<Empresa>>("/nucleo/empresas", { q: termo, papel, por_pagina: 8 }),
    enabled: aberto,
    staleTime: 10_000,
  });

  const criar = useMutation({
    mutationFn: (nome: string) => api.post<Empresa>("/nucleo/empresas", { nome, papeis: papeisAoCriar }),
    onSuccess: (e) => {
      qc.invalidateQueries({ queryKey: ["nucleo", "empresas"] });
      notificar.sucesso("Empresa disponível em todos os módulos");
      escolher({ id: e.id, nome: e.nome, papeis: e.papeis, criada: true });
    },
  });

  const itens = busca.data?.itens ?? [];
  const exata = itens.some((e) => chave(e.nome) === chave(termo));
  const mostrarCriar = podeCriar && termo.length > 0 && !exata && !busca.isFetching;
  const total = itens.length + (mostrarCriar ? 1 : 0);

  function escolher(e: EmpresaEscolhida | null) {
    onChange(e?.id ?? null, e);
    setTexto("");
    setAberto(false);
    setAtivo(0);
  }

  function confirmar(i: number) {
    if (i < itens.length) {
      const e = itens[i];
      escolher({ id: e.id, nome: e.nome, papeis: e.papeis });
    } else if (mostrarCriar && !criar.isPending) {
      criar.mutate(texto.trim());
    }
  }

  const nomeSelecionado = valor == null ? "" : (selecionada.data?.nome ?? "Carregando…");

  return (
    <div
      ref={caixa}
      className="relative"
      onBlur={(e) => {
        if (!caixa.current?.contains(e.relatedTarget as Node | null)) setAberto(false);
      }}
    >
      <div className="relative">
        <Building2 className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" aria-hidden />
        <Input
          id={id}
          role="combobox"
          aria-expanded={aberto}
          aria-controls={listaId}
          aria-autocomplete="list"
          autoComplete="off"
          autoFocus={autoFocus}
          disabled={disabled}
          className="h-9 pr-8 pl-8"
          placeholder={valor != null && !aberto ? undefined : placeholder}
          value={aberto ? texto : nomeSelecionado}
          onFocus={() => {
            setAberto(true);
            setTexto("");
          }}
          onChange={(e) => {
            setTexto(e.target.value);
            setAberto(true);
            setAtivo(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setAtivo((a) => Math.min(a + 1, Math.max(total - 1, 0)));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setAtivo((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && aberto) {
              e.preventDefault();
              if (total > 0) confirmar(ativo);
            } else if (e.key === "Escape" && aberto) {
              e.preventDefault(); // não fecha o drawer: só a lista
              setAberto(false);
            }
          }}
        />
        {criar.isPending ? (
          <Loader2 className="absolute top-1/2 right-2.5 size-4 -translate-y-1/2 animate-spin text-muted" />
        ) : (
          valor != null &&
          !disabled && (
            <button
              type="button"
              aria-label="Limpar empresa"
              onClick={() => escolher(null)}
              className="absolute top-1/2 right-2 grid size-5 -translate-y-1/2 place-items-center rounded text-muted hover:text-ink"
            >
              <X className="size-3.5" />
            </button>
          )
        )}
      </div>
      {aberto && (
        <ul
          id={listaId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-[9px] border border-line bg-surface p-1 shadow-lg shadow-ink/10"
        >
          {busca.isPending && <li className="px-3 py-2 text-xs text-muted">Buscando…</li>}
          {!busca.isPending && itens.length === 0 && !mostrarCriar && (
            <li className="px-3 py-2 text-xs text-muted">{termo ? "Nenhuma empresa com este nome." : "Digite o nome da empresa."}</li>
          )}
          {itens.map((e, i) => (
            <li key={e.id} role="option" aria-selected={i === ativo}>
              <button
                type="button"
                tabIndex={-1}
                onMouseEnter={() => setAtivo(i)}
                onClick={() => confirmar(i)}
                className={cn("flex w-full flex-col items-start rounded-[7px] px-3 py-2 text-left text-sm", i === ativo && "bg-subtle")}
              >
                <span className="font-medium">{e.nome}</span>
                <span className="text-[11px] text-muted">
                  {[e.papeis.map((p) => ROTULO_PAPEL[p]).join(" / "), e.segmento, e.documento].filter(Boolean).join(" · ") || "Cadastro compartilhado"}
                </span>
              </button>
            </li>
          ))}
          {mostrarCriar && (
            <li role="option" aria-selected={ativo === itens.length}>
              <button
                type="button"
                tabIndex={-1}
                onMouseEnter={() => setAtivo(itens.length)}
                onClick={() => confirmar(itens.length)}
                className={cn("flex w-full items-center gap-2 rounded-[7px] px-3 py-2 text-left text-sm text-primary", ativo === itens.length && "bg-subtle")}
              >
                <Plus className="size-4" />
                Criar “{texto.trim()}”
                <span className="ml-auto text-[11px] text-muted">o nome basta</span>
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
