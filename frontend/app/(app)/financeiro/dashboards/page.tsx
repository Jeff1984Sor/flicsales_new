"use client";

/** Financeiro › Dashboards (protótipo `dashboard` no modo Financeiro): Caixa + Aging em faixas (a vencer, 1–30 … 90+). */
import { useQuery } from "@tanstack/react-query";

import { CHAVE, Limite } from "@/components/financeiro/comum";
import { VisaoCaixa } from "@/components/financeiro/visao-caixa";
import { Dinheiro } from "@/components/flic/dinheiro";
import { PageHeader } from "@/components/flic/page-header";
import { GradePaineis, Painel } from "@/components/flic/painel";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { data, numero } from "@/lib/format";
import type { Dashboards, FaixaAging } from "@/lib/tipos-financeiro";
import { cn } from "@/lib/utils";

function Aging({ faixas, carregando }: { faixas: FaixaAging[] | undefined; carregando: boolean }) {
  if (carregando || !faixas) return <Skeleton className="h-48 w-full" />;
  const max = Math.max(...faixas.map((f) => Number(f.valor)), 1);
  const total = faixas.reduce((s, f) => s + Number(f.valor), 0);
  return (
    <>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] tracking-[0.6px] text-muted uppercase">
            <th className="border-b border-line py-2.5 text-left font-medium">Faixa</th>
            <th className="w-[40%] border-b border-line py-2.5" aria-hidden />
            <th className="border-b border-line py-2.5 text-right font-medium">Títulos</th>
            <th className="border-b border-line py-2.5 text-right font-medium">Saldo aberto</th>
          </tr>
        </thead>
        <tbody>
          {faixas.map((f) => (
            <tr key={f.faixa}>
              <td className="border-b border-line py-3 pr-3">{f.rotulo}</td>
              <td className="border-b border-line py-3">
                <div className="h-2 rounded-full bg-subtle">
                  <div
                    className={cn("h-2 rounded-full", f.faixa === "a_vencer" ? "bg-electric" : "bg-amber")}
                    style={{ width: `${(Number(f.valor) / max) * 100}%` }}
                  />
                </div>
              </td>
              <td className="num border-b border-line py-3 text-right">{numero(f.quantidade)}</td>
              <td className="border-b border-line py-3 text-right">
                <Dinheiro valor={f.valor} />
              </td>
            </tr>
          ))}
          <tr>
            <td className="pt-3 font-semibold" colSpan={3}>
              Total em aberto
            </td>
            <td className="pt-3 text-right font-semibold">
              <Dinheiro valor={total} />
            </td>
          </tr>
        </tbody>
      </table>
    </>
  );
}

export default function FinanceiroDashboardsPage() {
  const { data: d, isPending } = useQuery({ queryKey: [CHAVE, "dashboards"], queryFn: () => api.get<Dashboards>("/financeiro/dashboards") });
  return (
    <>
      <PageHeader titulo="Dashboards" descricao="Caixa, projeção e inadimplência por faixa de atraso, calculados em código." />
      <VisaoCaixa caixa={d?.caixa} carregando={isPending} />
      <GradePaineis className="mt-5 min-[1100px]:grid-cols-2">
        <Painel titulo="Aging de recebíveis">
          <Aging faixas={d?.aging_receber} carregando={isPending} />
        </Painel>
        <Painel titulo="Aging de contas a pagar">
          <Aging faixas={d?.aging_pagar} carregando={isPending} />
        </Painel>
      </GradePaineis>
      {d && (
        <Limite>
          Posição em {data(d.hoje)}. {d.limites[0]} Não inclui previsão comercial.
        </Limite>
      )}
    </>
  );
}
