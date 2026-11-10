"use client";

import { Suspense } from "react";

import { TelaContas, useIdDaUrl } from "@/components/cadastros";

function Tela() {
  const id = useIdDaUrl();
  return <TelaContas key={id ?? 0} idInicial={id} />;
}

export default function ContasPage() {
  return (
    <Suspense>
      <Tela />
    </Suspense>
  );
}
