"use client";

import { Suspense } from "react";

import { TelaCadastrosMestres } from "@/components/cadastros";

export default function CadastrosMestresPage() {
  return (
    <Suspense>
      <TelaCadastrosMestres />
    </Suspense>
  );
}
