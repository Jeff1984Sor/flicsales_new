"use client";

import { Suspense } from "react";

import { TelaFornecedores, useIdDaUrl } from "@/components/cadastros";

function Tela() {
  const id = useIdDaUrl();
  return <TelaFornecedores key={id ?? 0} idInicial={id} />;
}

export default function FornecedoresPage() {
  return (
    <Suspense>
      <Tela />
    </Suspense>
  );
}
