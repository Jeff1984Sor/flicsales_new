"use client";

import { Suspense } from "react";

import { TelaTitulos } from "@/components/financeiro/tela-titulos";

export default function FinanceiroPagarPage() {
  return (
    <Suspense>
      <TelaTitulos direcao="pagar" />
    </Suspense>
  );
}
