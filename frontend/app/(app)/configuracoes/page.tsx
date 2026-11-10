"use client";

import { Settings } from "lucide-react";

import { SemAcesso } from "@/components/flic/sem-acesso";
import { TELAS_EXTRAS } from "@/components/flic/nav";
import { useAuth } from "@/lib/auth";

/** O layout redireciona para a primeira aba liberada; sem nenhuma, avisa. */
export default function ConfiguracoesPage() {
  const { podeVer } = useAuth();
  const algum = TELAS_EXTRAS.some((i) => i.grupo === "Configurações" && (!i.recurso || podeVer(i.recurso)));
  return algum ? <Settings className="mx-auto mt-10 size-6 animate-pulse text-muted-foreground" /> : <SemAcesso />;
}
