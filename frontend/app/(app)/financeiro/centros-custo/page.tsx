"use client";

import { Suspense } from "react";

import { TelaCentrosCusto, useIdDaUrl } from "@/components/cadastros";

function Tela() {
  const id = useIdDaUrl();
  return <TelaCentrosCusto key={id ?? 0} idInicial={id} />;
}

export default function CentrosCustoPage() {
  return (
    <Suspense>
      <Tela />
    </Suspense>
  );
}
