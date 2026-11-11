"use client";

/**
 * PageHeader — cabeçalho de tela do protótipo (`heading()`): título 29px + subtítulo + "✧ Perguntar à IA" + ação primária.
 *
 * Props:
 *  - `titulo: ReactNode`              h1 ("Oportunidades")
 *  - `descricao?: ReactNode`          subtítulo cinza ("Um funil simples. Contexto completo em cada negociação.")
 *  - `acao?: ReactNode`               slot da ação primária (ex.: <Button onClick={novo}>+ Oportunidade</Button>)
 *  - `acoes?: ReactNode`              botões secundários extras (antes do "Perguntar à IA")
 *  - `semIA?: boolean`                esconde o "✧ Perguntar à IA" (telas de configuração)
 *                                     O botão só aparece nas telas de Comercial e Financeiro (some no Núcleo,
 *                                     Configurações, Minha conta e Assistente); o "✧ IA unificada" do topo vale em todas.
 *  - `escopoIA?: EscopoIA`            escopo ao abrir o assistente (padrão "Este módulo")
 *  - `icone?`                         ícone opcional à esquerda do título (telas do core)
 *  - `migalhas?`                      ignorado (o breadcrumb é do shell); mantido por compatibilidade com telas portadas
 */
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import type { EscopoIA } from "@/lib/types";
import { cn } from "@/lib/utils";

import { abrirAssistente } from "./eventos";

export function PageHeader({
  titulo,
  descricao,
  acao,
  acoes,
  semIA,
  escopoIA = "Este módulo",
  icone: Icone,
  className,
}: {
  titulo: React.ReactNode;
  descricao?: React.ReactNode;
  acao?: React.ReactNode;
  acoes?: React.ReactNode;
  semIA?: boolean;
  escopoIA?: EscopoIA;
  icone?: React.ComponentType<{ className?: string }>;
  migalhas?: { label: string; href?: string }[];
  className?: string;
}) {
  const pathname = usePathname();
  const comIA = !semIA && /^\/(comercial|financeiro)(\/|$)/.test(pathname);
  return (
    <div className={cn("mb-[25px] flex flex-col items-start justify-between gap-5 md:flex-row md:items-center", className)}>
      <div className="flex min-w-0 items-center gap-3">
        {Icone && (
          <div className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-tint text-primary">
            <Icone className="size-5" />
          </div>
        )}
        <div className="min-w-0">
          <h1 className="mb-[9px] text-[29px] leading-tight font-bold tracking-[-0.9px]">{titulo}</h1>
          {descricao && <p className="leading-relaxed text-muted">{descricao}</p>}
        </div>
      </div>
      {(comIA || acao || acoes) && (
        <div className="flex flex-wrap items-center gap-2.5">
          {acoes}
          {comIA && (
            <Button variant="outline" onClick={() => abrirAssistente(escopoIA)}>
              ✧ Perguntar à IA
            </Button>
          )}
          {acao}
        </div>
      )}
    </div>
  );
}
