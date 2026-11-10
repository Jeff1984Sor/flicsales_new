"use client";

/**
 * DataTable — tabela padrão do protótipo (cabeçalho 10px em caixa alta, linhas com hover azul-claro, clique abre drawer).
 *
 * <DataTable<T>> props:
 *  - `colunas: Coluna<T>[]`                 { id, titulo, celula(linha) → ReactNode, alinhar?: "esquerda"|"direita"|"centro", className? }
 *  - `linhas: T[] | undefined`
 *  - `chave: (linha: T) => string | number`
 *  - `onLinha?: (linha: T) => void`         clique na linha (normalmente abre o <Drawer>)
 *  - `carregando?: boolean`                 esqueleto
 *  - `vazio?: { icone, titulo, descricao?, acao? }`   estado vazio ilustrado (padrão: "Nada por aqui ainda.")
 *  - `paginacao?: { pagina, porPagina, total, onChange }`   paginação no servidor (resposta `Pagina<T>` de lib/types.ts)
 *  - `semCartao?: boolean`                  sem a moldura branca (quando já está dentro de um <Painel>)
 *
 * Ex.:
 *   const colunas: Coluna<Titulo>[] = [
 *     { id: "empresa", titulo: "Empresa / descrição", celula: (t) => <><strong>{t.empresa_nome}</strong><p className="text-muted">{t.descricao}</p></> },
 *     { id: "valor", titulo: "Valor original", alinhar: "direita", celula: (t) => <Dinheiro valor={t.valor_original} /> },
 *   ];
 *   <DataTable colunas={colunas} linhas={data?.itens} chave={(t) => t.id} onLinha={setSel} carregando={isPending} />
 *
 * Também exporta peças menores herdadas do core: TableCard, Toolbar, SearchInput, Segmented, Pagination, TableSkeleton.
 */
import { ChevronLeft, ChevronRight, Inbox, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { numero } from "@/lib/format";
import { cn } from "@/lib/utils";

import { EmptyState } from "./empty-state";

export interface Coluna<T> {
  id: string;
  titulo: string;
  celula: (linha: T) => React.ReactNode;
  alinhar?: "esquerda" | "direita" | "centro";
  className?: string;
}

export interface Paginacao {
  pagina: number;
  porPagina: number;
  total: number;
  onChange: (pagina: number) => void;
}

const ALINHAR = { esquerda: "text-left", direita: "text-right", centro: "text-center" } as const;

export function DataTable<T>({
  colunas,
  linhas,
  chave,
  onLinha,
  carregando,
  vazio,
  paginacao,
  semCartao,
  className,
}: {
  colunas: Coluna<T>[];
  linhas: T[] | undefined;
  chave: (linha: T) => string | number;
  onLinha?: (linha: T) => void;
  carregando?: boolean;
  vazio?: { icone?: React.ComponentType<{ className?: string }>; titulo: string; descricao?: React.ReactNode; acao?: React.ReactNode };
  paginacao?: Paginacao;
  semCartao?: boolean;
  className?: string;
}) {
  const lista = linhas ?? [];
  const corpo = carregando ? (
    <TableSkeleton colunas={Math.min(colunas.length, 6)} />
  ) : lista.length === 0 ? (
    <EmptyState icone={vazio?.icone ?? Inbox} titulo={vazio?.titulo ?? "Nada por aqui ainda."} descricao={vazio?.descricao} acao={vazio?.acao} />
  ) : (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            {colunas.map((c) => (
              <th
                key={c.id}
                scope="col"
                className={cn("border-b border-line px-2.5 py-3.5 text-[10px] font-medium tracking-[0.6px] whitespace-nowrap text-muted uppercase", ALINHAR[c.alinhar ?? "esquerda"], c.className)}
              >
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lista.map((l) => (
            <tr
              key={chave(l)}
              onClick={onLinha ? () => onLinha(l) : undefined}
              onKeyDown={
                onLinha
                  ? (e) => {
                      if (e.key === "Enter" && e.target === e.currentTarget) onLinha(l);
                    }
                  : undefined
              }
              tabIndex={onLinha ? 0 : undefined}
              className={cn("transition-colors hover:bg-subtle", onLinha && "cursor-pointer")}
            >
              {colunas.map((c) => (
                <td key={c.id} className={cn("border-b border-line px-2.5 py-[17px] align-middle", ALINHAR[c.alinhar ?? "esquerda"], c.className)}>
                  {c.celula(l)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  const conteudo = (
    <>
      {corpo}
      {paginacao && paginacao.total > paginacao.porPagina && (
        <Pagination pagina={paginacao.pagina} porPagina={paginacao.porPagina} total={paginacao.total} onChange={paginacao.onChange} />
      )}
    </>
  );
  if (semCartao) return <div className={className}>{conteudo}</div>;
  return <div className={cn("card-surface mb-5 overflow-hidden px-2 md:px-4", className)}>{conteudo}</div>;
}

/** Superfície padrão das tabelas. */
export function TableCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("card-surface overflow-hidden", className)}>{children}</div>;
}

export function Toolbar({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("flex flex-col gap-2 border-b border-line p-3 sm:flex-row sm:items-center sm:justify-between", className)}>{children}</div>;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Buscar…",
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cn("relative w-full sm:w-80", className)}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" />
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="h-9 rounded-[7px] bg-surface pr-8 pl-9"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          className="absolute top-1/2 right-2 grid size-5 -translate-y-1/2 place-items-center rounded text-muted hover:bg-subtle"
          aria-label="Limpar busca"
        >
          <X className="size-3.5" />
        </button>
      )}
    </div>
  );
}

/** Abas de filtro rápido em formato "segmented control". */
export function Segmented<T extends string>({
  value,
  onChange,
  opcoes,
}: {
  value: T;
  onChange: (v: T) => void;
  opcoes: { value: T; label: string; contagem?: number; tom?: "success" | "warning" | "danger" }[];
}) {
  return (
    <div className="inline-flex flex-wrap items-center gap-0.5 rounded-[7px] bg-subtle p-0.5">
      {opcoes.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={cn(
            "inline-flex h-8 items-center gap-1.5 rounded-[6px] px-3 text-sm font-medium text-muted transition-all",
            value === o.value && "bg-surface text-ink shadow-sm ring-1 ring-line",
          )}
        >
          {o.tom && (
            <span className={cn("size-1.5 rounded-full", o.tom === "success" && "bg-success", o.tom === "warning" && "bg-amber", o.tom === "danger" && "bg-danger")} />
          )}
          {o.label}
          {o.contagem !== undefined && <span className="num rounded bg-line/30 px-1.5 text-[11px]">{numero(o.contagem)}</span>}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ pagina, porPagina, total, onChange }: { pagina: number; porPagina: number; total: number; onChange: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  const de = total === 0 ? 0 : (pagina - 1) * porPagina + 1;
  const ate = Math.min(total, pagina * porPagina);
  return (
    <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-3 text-sm text-muted">
      <span>
        <span className="num text-ink">{numero(de)}</span>–<span className="num text-ink">{numero(ate)}</span> de <span className="num text-ink">{numero(total)}</span>
      </span>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="icon-sm" disabled={pagina <= 1} onClick={() => onChange(pagina - 1)} aria-label="Página anterior">
          <ChevronLeft />
        </Button>
        <span className="num px-2">
          {pagina}/{paginas}
        </span>
        <Button variant="outline" size="icon-sm" disabled={pagina >= paginas} onClick={() => onChange(pagina + 1)} aria-label="Próxima página">
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
}

export function TableSkeleton({ linhas = 6, colunas = 5 }: { linhas?: number; colunas?: number }) {
  return (
    <div className="divide-y divide-line">
      {Array.from({ length: linhas }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3.5">
          {Array.from({ length: colunas }).map((__, j) => (
            <Skeleton key={j} className={cn("h-4", j === 0 ? "w-32" : "flex-1")} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Classes padrão para <tr> clicável fora do DataTable. */
export const linhaClicavel = "cursor-pointer transition-colors hover:bg-subtle";
