"use client";

import { Suspense } from "react";

import { TelaGovernanca } from "@/components/governanca/tela-governanca";

export default function GovernancaPage() {
  return (
    <Suspense>
      <TelaGovernanca />
    </Suspense>
  );
}
