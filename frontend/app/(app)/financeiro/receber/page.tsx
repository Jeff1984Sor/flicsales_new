"use client";

import { Suspense } from "react";

import { TelaTitulos } from "@/components/financeiro/tela-titulos";

export default function FinanceiroReceberPage() {
  return (
    <Suspense>
      <TelaTitulos direcao="receber" />
    </Suspense>
  );
}
