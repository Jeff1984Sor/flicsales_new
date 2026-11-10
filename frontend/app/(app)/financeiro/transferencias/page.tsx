"use client";

/** Financeiro › Transferências (protótipo `transferList`): movimentos internos entre contas + nova transferência. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { useState } from "react";

import { CHAVE, Limite } from "@/components/financeiro/comum";
import { FormTransferencia } from "@/components/financeiro/form-transferencia";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data } from "@/lib/format";
import type { Transferencia } from "@/lib/tipos-financeiro";
import type { Pagina } from "@/lib/types";

const COLUNAS: Coluna<Transferencia>[] = [
  { id: "data", titulo: "Data", celula: (t) => <span className="num">{data(t.data)}</span> },
  { id: "origem", titulo: "Origem", celula: (t) => t.conta_origem_nome },
  { id: "destino", titulo: "Destino", celula: (t) => t.conta_destino_nome },
  { id: "desc", titulo: "Descrição", celula: (t) => <span className="text-muted">{t.descricao ?? "—"}</span> },
  { id: "valor", titulo: "Valor", alinhar: "direita", celula: (t) => <Dinheiro valor={t.valor} /> },
];

const POR_PAGINA = 50;

export default function FinanceiroTransferenciasPage() {
  const { pode } = useAuth();
  const [nova, setNova] = useState(false);
  const [pagina, setPagina] = useState(1);
  const podeCriar = pode("financeiro.caixa.editar");
  useAtalhoNovo(() => podeCriar && setNova(true));
  const lista = useQuery({
    queryKey: [CHAVE, "transferencias", pagina],
    queryFn: () => api.get<Pagina<Transferencia>>("/financeiro/transferencias", { pagina, por_pagina: POR_PAGINA }),
    placeholderData: keepPreviousData,
  });
  return (
    <>
      <PageHeader
        titulo="Transferências"
        descricao="Movimentações internas entre contas financeiras."
        acao={podeCriar ? <Button onClick={() => setNova(true)}>+ Transferência</Button> : undefined}
      />
      <BarraFiltros
        exportar={{
          nome: "transferencias",
          linhas: lista.data?.itens ?? [],
          colunas: [
            { titulo: "Data", valor: (t) => data(t.data) },
            { titulo: "Origem", valor: (t) => t.conta_origem_nome },
            { titulo: "Destino", valor: (t) => t.conta_destino_nome },
            { titulo: "Valor", valor: (t) => t.valor.replace(".", ",") },
            { titulo: "Descrição", valor: (t) => t.descricao },
          ],
        }}
      />
      <DataTable
        colunas={COLUNAS}
        linhas={lista.data?.itens}
        chave={(t) => t.id}
        carregando={lista.isPending}
        vazio={{ icone: ArrowLeftRight, titulo: "Nenhuma transferência registrada.", descricao: "Transferências entre contas não são receita nem despesa." }}
        paginacao={lista.data ? { pagina, porPagina: POR_PAGINA, total: lista.data.total, onChange: setPagina } : undefined}
      />
      <Limite>Registro entre contas, sem envio de dinheiro. Não altera receita ou despesa.</Limite>
      <FormTransferencia aberto={nova} onFechar={() => setNova(false)} />
    </>
  );
}
