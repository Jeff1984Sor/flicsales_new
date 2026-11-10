"use client";

import { Suspense } from "react";

import { AutomacoesTela } from "@/components/orquestracao/automacoes";

export default function NucleoAutomacoesPage() {
  return (
    <Suspense>
      <AutomacoesTela />
    </Suspense>
  );
}
