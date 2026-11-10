"use client";

/** Financeiro › Caixa (protótipo `cash`, última versão): saldo por conta, projeção e limites; Transferir entre contas. */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { CHAVE } from "@/components/financeiro/comum";
import { FormTransferencia } from "@/components/financeiro/form-transferencia";
import { VisaoCaixa } from "@/components/financeiro/visao-caixa";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Caixa } from "@/lib/tipos-financeiro";

export default function FinanceiroCaixaPage() {
  const { pode } = useAuth();
  const [transferir, setTransferir] = useState(false);
  const podeTransferir = pode("financeiro.caixa.editar");
  useAtalhoNovo(() => podeTransferir && setTransferir(true));
  const { data, isPending } = useQuery({ queryKey: [CHAVE, "caixa"], queryFn: () => api.get<Caixa>("/financeiro/caixa") });
  return (
    <>
      <PageHeader
        titulo="Caixa"
        descricao="Saldos informados, baixas e projeção calculados a partir dos registros."
        acao={podeTransferir ? <Button onClick={() => setTransferir(true)}>Transferir entre contas</Button> : undefined}
      />
      <VisaoCaixa caixa={data} carregando={isPending} />
      <FormTransferencia aberto={transferir} onFechar={() => setTransferir(false)} />
    </>
  );
}
