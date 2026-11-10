/**
 * KpiCard e Metricas — cartões de métrica do protótipo (`.metric` dentro de `.metrics`, grade de 4).
 *
 * <KpiCard> props:
 *  - `rotulo: string`            texto cinza do topo ("Pipeline aberto")
 *  - `valor: ReactNode`          número grande 29px, mono (use <Dinheiro/> ou número)
 *  - `detalhe?: ReactNode`       linha azul embaixo ("4 oportunidades ativas", "Vendas ≠ recebimentos")
 *  - `formula?: string`          fórmula visível (tooltip nativo + aria), regra "indicador com fórmula"
 *  - `carregando?: boolean`      esqueleto no lugar do valor
 *  - `tom?: "padrao" | "atencao"` atencao pinta o detalhe de âmbar (vencidos)
 *
 * <Metricas colunas?={4|2|3}> envolve os cartões (2 colunas abaixo de 1100px, como no protótipo).
 *
 * Ex.:
 *   <Metricas>
 *     <KpiCard rotulo="Pipeline aberto" valor={<Dinheiro valor={63600} />} detalhe="4 oportunidades ativas" />
 *   </Metricas>
 */
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function KpiCard({
  rotulo,
  valor,
  detalhe,
  formula,
  carregando,
  tom = "padrao",
  className,
}: {
  rotulo: string;
  valor: React.ReactNode;
  detalhe?: React.ReactNode;
  formula?: string;
  carregando?: boolean;
  tom?: "padrao" | "atencao";
  className?: string;
}) {
  return (
    <div className={cn("card-surface p-[15px] md:p-5", className)} title={formula}>
      <span className="text-muted">{rotulo}</span>
      {carregando ? (
        <Skeleton className="mt-[13px] mb-2.5 h-8 w-32" />
      ) : (
        <strong className="num mt-[13px] mb-2.5 block truncate text-[23px] leading-tight font-bold tracking-[-1px] md:text-[29px]">{valor}</strong>
      )}
      {detalhe && <small className={cn("block text-xs", tom === "atencao" ? "text-amber-ink" : "text-primary")}>{detalhe}</small>}
      {formula && <span className="sr-only">Fórmula: {formula}</span>}
    </div>
  );
}

export function Metricas({ colunas = 4, className, children }: { colunas?: 2 | 3 | 4; className?: string; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "mt-5 mb-[25px] grid grid-cols-2 gap-2.5 md:gap-4",
        colunas === 4 && "min-[1100px]:grid-cols-4",
        colunas === 3 && "min-[1100px]:grid-cols-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
