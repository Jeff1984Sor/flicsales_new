"use client";

/**
 * Insight — "LEITURA DO MOMENTO" (protótipo `.insight`): o destaque priorizado do topo das telas Hoje.
 * Props:
 *  - `titulo: ReactNode`            frase forte ("Uma conversa pode destravar sua semana.")
 *  - `texto?: ReactNode`            explicação curta
 *  - `eyebrow?: string`             padrão "LEITURA DO MOMENTO"
 *  - `acao?: { rotulo: string; onClick: () => void }`   botão à direita (ex.: "Entender e agir")
 *  - `iaDesligada?: boolean`        mostra "IA desligada, leitura por regras" (a leitura vem do domínio, não da IA)
 *  - `children?`                    conteúdo extra (ex.: <Fonte/>)
 */
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Insight({
  titulo,
  texto,
  eyebrow = "LEITURA DO MOMENTO",
  acao,
  iaDesligada,
  className,
  children,
}: {
  titulo: React.ReactNode;
  texto?: React.ReactNode;
  eyebrow?: string;
  acao?: { rotulo: string; onClick: () => void };
  iaDesligada?: boolean;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <section className={cn("mb-[25px] flex flex-wrap items-center gap-5 rounded-[10px] border border-electric/20 bg-electric/5 p-[22px] md:flex-nowrap", className)}>
      <div className="text-[28px] leading-none text-primary" aria-hidden>
        ✧
      </div>
      <div className="min-w-0 flex-1">
        <div className="eyebrow">
          {eyebrow}
          {iaDesligada && <span className="ml-2 font-medium tracking-normal text-muted normal-case">· IA desligada, leitura por regras</span>}
        </div>
        <p className="mt-1.5 text-base font-bold">{titulo}</p>
        {texto && <p className="mt-1 leading-relaxed text-muted">{texto}</p>}
        {children}
      </div>
      {acao && (
        <Button variant="outline" onClick={acao.onClick} className="whitespace-nowrap md:ml-auto">
          {acao.rotulo}
        </Button>
      )}
    </section>
  );
}
