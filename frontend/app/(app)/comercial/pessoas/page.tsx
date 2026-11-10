"use client";

import { Suspense } from "react";

import { TelaPessoas, useIdDaUrl } from "@/components/cadastros";

function Tela() {
  const id = useIdDaUrl();
  return <TelaPessoas key={id ?? 0} idInicial={id} />;
}

export default function ComercialPessoasPage() {
  return (
    <Suspense>
      <Tela />
    </Suspense>
  );
}
