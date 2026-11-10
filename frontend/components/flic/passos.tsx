/**
 * Passos — `.steps` do protótipo (ex.: Oportunidade → Condição comercial → Recebível em rascunho → Recebimento).
 * Props:
 *  - `passos: string[]`   rótulos, em ordem
 *  - `atual?: number`     índice do passo atual (destacado); os anteriores ficam marcados como feitos
 */
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export function Passos({ passos, atual, className }: { passos: string[]; atual?: number; className?: string }) {
  return (
    <ol className={cn("my-5 flex flex-wrap gap-2", className)}>
      {passos.map((p, i) => {
        const feito = atual != null && i < atual;
        const corrente = atual === i;
        return (
          <li
            key={p}
            aria-current={corrente ? "step" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-[5px] bg-tint p-2.5 text-[11px] text-primary",
              corrente && "bg-primary text-primary-foreground",
              feito && "opacity-80",
            )}
          >
            {feito && <Check className="size-3" />}
            {p}
          </li>
        );
      })}
    </ol>
  );
}
