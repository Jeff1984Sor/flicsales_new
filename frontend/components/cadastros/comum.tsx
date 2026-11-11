"use client";

/**
 * Peças comuns dos cadastros do Núcleo (reutilizáveis por qualquer módulo).
 *
 * Seletores simples (select nativo, carregam a lista sozinhos; `valor`/`onChange` com id numérico ou null):
 *  - `<SeletorResponsavel valor onChange />`                      usuários (GET /config/usuarios/opcoes)
 *  - `<SeletorCategoria valor onChange natureza? />`              categorias ativas (natureza "receita" | "despesa")
 *  - `<SeletorCentroCusto valor onChange />`                      centros de custo ativos
 *  - `<SeletorConta valor onChange />`                            contas financeiras ativas
 *  - `<SeletorProduto valor onChange />`                          produtos e serviços ativos
 *  - `<SeletorPessoa valor onChange empresaId? />`                contatos (filtra pela empresa, se informada)
 *  Todos aceitam `id?` (para o <Field>), `disabled?` e `vazio?` (texto da opção vazia, padrão "Selecionar").
 *
 * Utilitários de formulário:
 *  - `paraEnvio(form)`               "" → null (campo vazio vai como null, nunca "")
 *  - `alterados(inicial, atual)`     só o que mudou (o backend grava só o enviado)
 *  - `CHIPS_SITUACAO`                chips Ativos · Inativos · Todos para a BarraFiltros
 *  - `useInvalidarCadastros()`       invalida as listas do Núcleo após salvar
 *  - `<AcoesLista>`                  linha de ações de uma lista embutida (sem PageHeader): Importar à esquerda,
 *                                    ação primária por último
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { NativeSelect } from "@/components/flic/form";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Pagina } from "@/lib/types";
import type {
  Categoria,
  CentroCusto,
  ContaFinanceira,
  Natureza,
  Pessoa,
  Produto,
  Situacao,
  UsuarioOpcao,
} from "@/lib/tipos-nucleo";

export const CHIPS_SITUACAO: { valor: Situacao; rotulo: string }[] = [
  { valor: "ativos", rotulo: "Ativos" },
  { valor: "inativos", rotulo: "Inativos" },
  { valor: "todos", rotulo: "Todos" },
];

/** "" e textos só com espaço viram null. */
export function paraEnvio<T extends object>(form: T): { [K in keyof T]: T[K] | null } {
  const out = {} as { [K in keyof T]: T[K] | null };
  for (const k of Object.keys(form) as (keyof T)[]) {
    const v = form[k];
    out[k] = typeof v === "string" && v.trim() === "" ? null : v;
  }
  return out;
}

/** Só as chaves cujo valor mudou (comparação por JSON, serve para listas e objetos). */
export function alterados<T extends object>(inicial: Partial<T>, atual: T): Partial<T> {
  const out: Partial<T> = {};
  for (const k of Object.keys(atual) as (keyof T)[]) {
    if (JSON.stringify(inicial[k] ?? null) !== JSON.stringify(atual[k] ?? null)) out[k] = atual[k];
  }
  return out;
}

/** Texto do formulário a partir de um valor da API (null → ""). */
export const txt = (v: string | number | null | undefined) => (v == null ? "" : String(v));

export function useInvalidarCadastros() {
  const qc = useQueryClient();
  return (...chaves: string[]) => {
    for (const c of chaves.length ? chaves : ["nucleo"]) qc.invalidateQueries({ queryKey: c === "nucleo" ? ["nucleo"] : ["nucleo", c] });
  };
}

interface SeletorBase {
  valor: number | null;
  onChange: (id: number | null) => void;
  id?: string;
  disabled?: boolean;
  vazio?: string;
}

function SelectDeOpcoes({
  valor,
  onChange,
  id,
  disabled,
  vazio = "Selecionar",
  opcoes,
  carregando,
}: SeletorBase & { opcoes: { id: number; rotulo: string }[]; carregando?: boolean }) {
  // mantém visível a opção atual mesmo se ela estiver inativa (fora da lista)
  const lista = valor != null && !opcoes.some((o) => o.id === valor) ? [...opcoes, { id: valor, rotulo: carregando ? "Carregando…" : `#${valor}` }] : opcoes;
  return (
    <NativeSelect id={id} disabled={disabled} value={valor == null ? "" : String(valor)} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">{vazio}</option>
      {lista.map((o) => (
        <option key={o.id} value={o.id}>
          {o.rotulo}
        </option>
      ))}
    </NativeSelect>
  );
}

export function useUsuariosOpcoes() {
  return useQuery({ queryKey: ["usuarios-opcoes"], queryFn: () => api.get<UsuarioOpcao[]>("/config/usuarios/opcoes"), staleTime: 60_000 });
}

export function SeletorResponsavel(p: SeletorBase) {
  const { data, isPending } = useUsuariosOpcoes();
  return <SelectDeOpcoes {...p} carregando={isPending} opcoes={(data ?? []).map((u) => ({ id: u.id, rotulo: u.nome }))} />;
}

export function SeletorCategoria({ natureza, ...p }: SeletorBase & { natureza?: Natureza }) {
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "categorias", "opcoes", natureza ?? ""],
    queryFn: () => api.get<Categoria[]>("/nucleo/categorias", { natureza }),
    staleTime: 30_000,
  });
  return (
    <SelectDeOpcoes
      {...p}
      carregando={isPending}
      opcoes={(data ?? []).map((c) => ({ id: c.id, rotulo: c.superior_nome ? `${c.superior_nome} › ${c.nome}` : c.nome }))}
    />
  );
}

export function SeletorCentroCusto(p: SeletorBase) {
  const { data, isPending } = useQuery({ queryKey: ["nucleo", "centros-custo", "opcoes"], queryFn: () => api.get<CentroCusto[]>("/nucleo/centros-custo"), staleTime: 30_000 });
  return <SelectDeOpcoes {...p} carregando={isPending} opcoes={(data ?? []).map((c) => ({ id: c.id, rotulo: `${c.codigo} · ${c.nome}` }))} />;
}

export function SeletorConta(p: SeletorBase) {
  const { data, isPending } = useQuery({ queryKey: ["nucleo", "contas", "opcoes"], queryFn: () => api.get<ContaFinanceira[]>("/nucleo/contas"), staleTime: 30_000 });
  return <SelectDeOpcoes {...p} carregando={isPending} opcoes={(data ?? []).map((c) => ({ id: c.id, rotulo: c.nome }))} />;
}

export function SeletorProduto(p: SeletorBase) {
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "produtos", "opcoes"],
    queryFn: () => api.get<Pagina<Produto>>("/nucleo/produtos", { por_pagina: 200 }),
    staleTime: 30_000,
  });
  return <SelectDeOpcoes {...p} carregando={isPending} opcoes={(data?.itens ?? []).map((x) => ({ id: x.id, rotulo: x.nome }))} />;
}

export function SeletorPessoa({ empresaId, ...p }: SeletorBase & { empresaId?: number | null }) {
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "pessoas", "opcoes", empresaId ?? 0],
    queryFn: () => api.get<Pagina<Pessoa>>("/nucleo/pessoas", { empresa_id: empresaId ?? undefined, por_pagina: 200 }),
    staleTime: 30_000,
  });
  return (
    <SelectDeOpcoes
      {...p}
      carregando={isPending}
      opcoes={(data?.itens ?? []).map((x) => ({ id: x.id, rotulo: x.empresa_nome && !empresaId ? `${x.nome} · ${x.empresa_nome}` : x.nome }))}
    />
  );
}

/** Ações de uma lista embutida em outra tela: mesma ordem do cabeçalho (Importar → ação primária). */
export function AcoesLista({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 flex flex-wrap items-center justify-end gap-2.5">{children}</div>;
}

/** Rodapé padrão dos drawers de formulário: "Salvar …" (submit do form `formId`) + "Cancelar". */
export function RodapeFormulario({
  formId,
  rotulo,
  salvando,
  onCancelar,
  extra,
}: {
  formId: string;
  rotulo: string;
  salvando?: boolean;
  onCancelar: () => void;
  extra?: React.ReactNode;
}) {
  return (
    <>
      <Button type="submit" form={formId} disabled={salvando}>
        {salvando ? "Salvando…" : rotulo}
      </Button>
      <Button type="button" variant="outline" onClick={onCancelar}>
        Cancelar
      </Button>
      {extra && <div className="ml-auto flex gap-2">{extra}</div>}
    </>
  );
}
