"use client";

/** VisaoCaixa — KPIs do caixa (com fórmula visível) + tabela de contas (protótipo `cash`, reaproveitado no Dashboards). */
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { data } from "@/lib/format";
import type { Caixa, ContaSaldo } from "@/lib/tipos-financeiro";

import { Limite } from "./comum";

const COLUNAS: Coluna<ContaSaldo>[] = [
  {
    id: "conta",
    titulo: "Conta",
    celula: (c) => (
      <>
        <strong>{c.nome}</strong>
        {c.instituicao && <p className="text-muted">{c.instituicao}</p>}
      </>
    ),
  },
  { id: "inicial", titulo: "Saldo inicial", alinhar: "direita", celula: (c) => <Dinheiro valor={c.saldo_inicial} /> },
  { id: "base", titulo: "Data-base", celula: (c) => <span className="num">{data(c.data_base)}</span> },
  { id: "atual", titulo: "Saldo atual", alinhar: "direita", celula: (c) => <Dinheiro valor={c.saldo_atual} className="font-semibold" /> },
];

export function VisaoCaixa({ caixa, carregando }: { caixa: Caixa | undefined; carregando?: boolean }) {
  const k = (r: "saldo_gerencial" | "entradas_abertas" | "saidas_abertas" | "saldo_apos_titulos", rotulo: string) => (
    <KpiCard
      rotulo={rotulo}
      valor={<Dinheiro valor={caixa?.[r].valor} />}
      detalhe={caixa?.[r].detalhe}
      formula={caixa?.[r].formula}
      carregando={carregando}
    />
  );
  return (
    <>
      <Metricas>
        {k("saldo_gerencial", "Saldo gerencial")}
        {k("entradas_abertas", "Entradas abertas")}
        {k("saidas_abertas", "Saídas abertas")}
        {k("saldo_apos_titulos", "Saldo após títulos")}
      </Metricas>
      <DataTable
        colunas={COLUNAS}
        linhas={caixa?.contas}
        chave={(c) => c.id}
        carregando={carregando}
        vazio={{ titulo: "Nenhuma conta financeira.", descricao: "Cadastre contas em Contas financeiras para acompanhar o saldo." }}
      />
      {caixa?.limites.map((l) => (
        <Limite key={l}>{l}</Limite>
      ))}
    </>
  );
}
