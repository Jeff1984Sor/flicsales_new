"use client";

import { TelaModelos } from "@/components/comercial/tela-modelos";

/** Comercial lista os modelos comerciais e os gerais (os financeiros ficam nas cobranças). */
export default function ModelosPage() {
  return <TelaModelos classificacoes={["comercial", "geral"]} classificacaoPadrao="comercial" />;
}
