/**
 * Etiqueta — `.tag` do protótipo (10px, raio 5).
 * Props:
 *  - `tom?: "neutra" | "green" | "amber" | "azul"`  neutra (padrão) · green = turquesa/ok/IA · amber = vencido/atenção · azul = informação
 *  - `children`                                    texto (sempre presente: cor nunca é o único sinal)
 * Ex.: <Etiqueta tom="green">Alto interesse</Etiqueta>  <Etiqueta tom="amber">Vencido</Etiqueta>
 */
import { cn } from "@/lib/utils";

export type TomEtiqueta = "neutra" | "green" | "amber" | "azul";

const TONS: Record<TomEtiqueta, string> = {
  neutra: "bg-line/40 text-muted",
  green: "bg-accent/10 text-primary",
  amber: "bg-amber/15 text-amber-ink",
  azul: "bg-tint text-primary",
};

export function Etiqueta({ tom = "neutra", className, children }: { tom?: TomEtiqueta; className?: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-[5px] px-2 py-[5px] text-[10px] leading-none font-medium whitespace-nowrap", TONS[tom], className)}>
      {children}
    </span>
  );
}
