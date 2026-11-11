"use client";

import { Bot } from "lucide-react";

import { PageHeader } from "@/components/flic/page-header";
import { ConfiguracaoIA } from "@/components/orquestracao/configuracao-ia";

export default function ConfiguracoesIAPage() {
  return (
    <>
      <PageHeader titulo="Configurações de IA" descricao="Provedor, modelo e chave cifrada. Sem IA, o produto segue útil." icone={Bot} />
      <ConfiguracaoIA />
    </>
  );
}
