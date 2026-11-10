"use client";

import { Suspense } from "react";

import { TelaEmpresas, useIdDaUrl } from "@/components/cadastros";

function Tela() {
  const id = useIdDaUrl();
  return <TelaEmpresas key={id ?? 0} idInicial={id} />;
}

export default function ComercialEmpresasPage() {
  return (
    <Suspense>
      <Tela />
    </Suspense>
  );
}
