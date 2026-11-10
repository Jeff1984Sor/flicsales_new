"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { MODULOS, gruposVisiveis } from "@/components/flic/nav";
import { useAuth } from "@/lib/auth";

/** "/" → Comercial › Hoje (ou a primeira tela que o perfil enxerga). */
export default function Inicio() {
  const router = useRouter();
  const { podeVer } = useAuth();
  useEffect(() => {
    const primeira = MODULOS.map((m) => gruposVisiveis(m, podeVer)[0]?.itens[0]?.href).find(Boolean);
    router.replace(primeira ?? "/comercial");
  }, [router, podeVer]);
  return null;
}
