"use client";

import { Suspense } from "react";

import { TelaProdutos, useIdDaUrl } from "@/components/cadastros";

function Tela() {
  const id = useIdDaUrl();
  return <TelaProdutos key={id ?? 0} idInicial={id} />;
}

export default function ComercialProdutosPage() {
  return (
    <Suspense>
      <Tela />
    </Suspense>
  );
}
