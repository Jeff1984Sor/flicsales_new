"use client";

/**
 * Marca do FlicSales OS.
 *  - <FlicLogo claro? tamanho?>  logo `flic`+`sales` (sales em azul) + "/ OS" sobrescrito, como no topo do protótipo
 *  - <MarcaLogo claro?>          logo + lema "Um contexto. Próxima ação." (telas públicas)
 *  - <ClientLogo>                monograma quadrado (carregamento) ou logo da organização (Configurações › Identidade)
 *  - <Assinatura>                "FlicSales OS" + versão no ar (rodapé das telas públicas)
 *  - <Mono>                      número em JetBrains Mono
 */
import { useQuery } from "@tanstack/react-query";

import { API_URL } from "@/lib/api";
import { useBrand } from "@/lib/brand";
import { VERSAO } from "@/lib/env";
import { cn } from "@/lib/utils";

export function FlicLogo({ className, claro }: { className?: string; claro?: boolean }) {
  return (
    <span className={cn("inline-flex items-baseline text-[25px] font-[750] tracking-[-1px] select-none", claro ? "text-white" : "text-ink", className)}>
      flic<span className="text-electric">sales</span>
      <sup className="ml-[5px] text-[9px] font-semibold tracking-normal text-sidebar-foreground">/ OS</sup>
    </span>
  );
}

export function MarcaLogo({ className, claro }: { className?: string; claro?: boolean }) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <FlicLogo claro={claro} />
      <p className={cn("text-xs", claro ? "text-sidebar-foreground" : "text-muted")}>Um contexto. Próxima ação.</p>
    </div>
  );
}

/** Logo da organização (white-label) com fallback de monograma "fs". */
export function ClientLogo({ className, compacto }: { className?: string; compacto?: boolean }) {
  const { logoSrc, nome_exibicao } = useBrand();
  if (logoSrc && !compacto) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={logoSrc} alt={nome_exibicao} className={cn("h-8 w-auto object-contain", className)} />;
  }
  return (
    <div className={cn("grid size-9 shrink-0 place-items-center overflow-hidden rounded-[10px] bg-sidebar text-sm font-bold text-white ring-1 ring-electric/40", className)}>
      {logoSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={logoSrc} alt={nome_exibicao} className="size-full bg-surface object-contain p-1" />
      ) : (
        <span>
          f<span className="text-electric">s</span>
        </span>
      )}
    </div>
  );
}

/** Versão que está no ar (lida de /api/health); o valor do build é só o fallback. */
function useVersao() {
  const { data } = useQuery({
    queryKey: ["versao-no-ar"],
    queryFn: async () => {
      const r = await fetch(`${API_URL}/health`, { credentials: "same-origin" });
      return ((await r.json()) as { versao?: string }).versao;
    },
    staleTime: 30 * 60_000,
    retry: false,
    meta: { silencioso: true },
  });
  return data && data !== "dev" ? data : VERSAO;
}

export function Assinatura({ className, versao = true }: { className?: string; versao?: boolean }) {
  const numero = useVersao();
  return (
    <p className={cn("flex items-center gap-1.5 text-xs", className)}>
      <span className="inline-block size-1.5 rounded-full bg-accent" />
      <span className="font-semibold tracking-tight">FlicSales OS</span> · orquestração comercial e financeira
      {versao && <span className="rounded bg-current/10 px-1.5 py-px font-mono text-[10px] opacity-80">{numero}</span>}
    </p>
  );
}

export function Mono({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("num text-[0.92em]", className)}>{children}</span>;
}
