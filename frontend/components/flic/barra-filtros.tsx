"use client";

/**
 * BarraFiltros — barra acima da tabela: busca + chips de estado + "Exportar CSV" (no cliente).
 *
 * Props:
 *  - `busca?: { valor: string; onChange: (v: string) => void; placeholder?: string }`
 *  - `chips?: { opcoes: { valor: string; rotulo: string; contagem?: number }[]; valor: string; onChange: (v: string) => void }`
 *        ex.: Todos · Aberto · Rascunho · Parcial · Liquidado · Cancelado · Vencido
 *  - `exportar?: { nome: string; colunas: ColunaCsv<T>[]; linhas: T[] }`
 *        CSV com `;`, BOM UTF-8 e neutralização de = + - @ (lib/csv.ts). Exporta as linhas recebidas (as filtradas).
 *  - `children?`   filtros extras (selects) entre a busca e o botão de exportar
 *
 * Ex.:
 *   <BarraFiltros
 *     busca={{ valor: q, onChange: setQ, placeholder: "Buscar empresa ou descrição" }}
 *     chips={{ opcoes: ESTADOS, valor: estado, onChange: setEstado }}
 *     exportar={{ nome: "a-receber", colunas: CSV, linhas: itens }}
 *   />
 */
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { baixarCsv, type ColunaCsv } from "@/lib/csv";
import { numero } from "@/lib/format";
import { cn } from "@/lib/utils";

import { SearchInput } from "./data-table";
import { notificar } from "./toast";

export interface OpcaoChip {
  valor: string;
  rotulo: string;
  contagem?: number;
}

export function BarraFiltros<T>({
  busca,
  chips,
  exportar,
  className,
  children,
}: {
  busca?: { valor: string; onChange: (v: string) => void; placeholder?: string };
  chips?: { opcoes: OpcaoChip[]; valor: string; onChange: (v: string) => void };
  exportar?: { nome: string; colunas: ColunaCsv<T>[]; linhas: T[] };
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn("mb-[18px] flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-center gap-2.5">
        {busca && <SearchInput value={busca.valor} onChange={busca.onChange} placeholder={busca.placeholder ?? "Buscar…"} />}
        {children}
        {exportar && (
          <Button
            variant="outline"
            className="sm:ml-auto"
            onClick={() => {
              if (exportar.linhas.length === 0) {
                notificar("Nada para exportar com estes filtros.");
                return;
              }
              baixarCsv(exportar.nome, exportar.colunas, exportar.linhas);
            }}
          >
            <Download className="size-4" />
            Exportar CSV
          </Button>
        )}
      </div>
      {chips && (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtrar por estado">
          {chips.opcoes.map((o) => {
            const on = o.valor === chips.valor;
            return (
              <button
                key={o.valor}
                type="button"
                aria-pressed={on}
                onClick={() => chips.onChange(o.valor)}
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded-[7px] border px-3 text-xs transition",
                  on ? "border-primary bg-tint font-semibold text-primary" : "border-line bg-surface text-ink hover:border-primary",
                )}
              >
                {o.rotulo}
                {o.contagem !== undefined && <span className="num text-[11px] text-muted">{numero(o.contagem)}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
