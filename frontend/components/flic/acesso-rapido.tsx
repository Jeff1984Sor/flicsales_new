"use client";

/**
 * AcessoRapido — barra `.quickbar` do protótipo ("Acesso rápido": +Oportunidade, +Atividade…).
 * Props:
 *  - `itens: { rotulo: string; onClick?: () => void; href?: string; icone?: LucideIcon }[]`
 *  - `titulo?: string`   padrão "Acesso rápido"
 */
import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ItemAcessoRapido {
  rotulo: string;
  onClick?: () => void;
  href?: string;
  icone?: LucideIcon;
}

export function AcessoRapido({ itens, titulo = "Acesso rápido", className }: { itens: ItemAcessoRapido[]; titulo?: string; className?: string }) {
  return (
    <nav aria-label={titulo} className={cn("mb-[22px] flex flex-wrap items-center gap-2 rounded-[9px] border border-line bg-surface p-3.5", className)}>
      <span className="eyebrow mr-1">{titulo}</span>
      {itens.map((i) => {
        const conteudo = (
          <>
            {i.icone && <i.icone className="size-3.5" />}
            {i.rotulo}
          </>
        );
        return i.href ? (
          <Button key={i.rotulo} variant="outline" size="sm" className="h-8 px-2.5 text-[11px]" render={<Link href={i.href} />}>
            {conteudo}
          </Button>
        ) : (
          <Button key={i.rotulo} variant="outline" size="sm" className="h-8 px-2.5 text-[11px]" onClick={i.onClick}>
            {conteudo}
          </Button>
        );
      })}
    </nav>
  );
}
