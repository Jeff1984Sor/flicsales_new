"use client";

import { Suspense } from "react";

import { TelaCategorias, useIdDaUrl } from "@/components/cadastros";

function Tela() {
  const id = useIdDaUrl();
  return <TelaCategorias key={id ?? 0} idInicial={id} />;
}

export default function CategoriasPage() {
  return (
    <Suspense>
      <Tela />
    </Suspense>
  );
}
