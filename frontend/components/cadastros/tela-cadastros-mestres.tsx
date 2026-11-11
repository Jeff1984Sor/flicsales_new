"use client";

/**
 * TelaCadastrosMestres — Núcleo › "Cadastros mestres" (protótipo `masters`): abas Empresas · Pessoas sobre o mesmo
 * cadastro único, e o painel Qualidade dos dados (duplicidades e mesclagem). Produtos e serviços moram na
 * Governança de ajustes: `?aba=produtos` leva para lá.
 * Lê `?aba=empresas|pessoas&id=` (links da busca global): envolva a página em <Suspense>.
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/flic/page-header";
import { cn } from "@/lib/utils";

import { QualidadeDados } from "./qualidade-dados";
import { TelaEmpresas } from "./tela-empresas";
import { TelaPessoas } from "./tela-pessoas";

type Aba = "empresas" | "pessoas";
const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "empresas", rotulo: "Empresas" },
  { id: "pessoas", rotulo: "Pessoas" },
];

/** id numérico do `?id=` da URL (ou null). */
export function useIdDaUrl() {
  const p = useSearchParams();
  const n = Number(p.get("id"));
  return Number.isInteger(n) && n > 0 ? n : null;
}

export function TelaCadastrosMestres() {
  const params = useSearchParams();
  const router = useRouter();
  // links antigos de produto (busca global, favoritos) vão para a Governança de ajustes
  const produtos = params.get("aba") === "produtos";
  useEffect(() => {
    if (!produtos) return;
    const id = params.get("id");
    router.replace(`/nucleo/governanca?aba=produtos${id ? `&id=${encodeURIComponent(id)}` : ""}`);
  }, [produtos, params, router]);
  if (produtos) return null;
  // a busca global pode trocar ?aba=&id= com a tela já aberta: remonta para abrir o registro pedido
  return <Conteudo key={params.toString()} />;
}

function Conteudo() {
  const params = useSearchParams();
  const id = useIdDaUrl();
  const inicial = (ABAS.find((a) => a.id === params.get("aba"))?.id ?? "empresas") as Aba;
  const [aba, setAba] = useState<Aba>(inicial);

  // cada aba traz as próprias ações (Importar planilha → + Empresa / + Pessoa)
  return (
    <>
      <PageHeader titulo="Cadastros mestres" descricao="Uma base única para Comercial e Financeiro." />
      <div role="tablist" aria-label="Tipo de cadastro" className="mb-5 flex flex-wrap gap-2">
        {ABAS.map((a) => (
          <button
            key={a.id}
            role="tab"
            type="button"
            aria-selected={aba === a.id}
            onClick={() => setAba(a.id)}
            className={cn(
              "rounded-[7px] border px-4 py-2 text-sm transition",
              aba === a.id ? "border-primary bg-primary font-semibold text-primary-foreground" : "border-line bg-surface hover:border-primary",
            )}
          >
            {a.rotulo}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {aba === "empresas" && <TelaEmpresas embutida idInicial={inicial === "empresas" ? id : null} />}
        {aba === "pessoas" && <TelaPessoas embutida idInicial={inicial === "pessoas" ? id : null} />}
      </div>
      <div className="mt-6">
        <QualidadeDados />
      </div>
    </>
  );
}
