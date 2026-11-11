"use client";

/**
 * TelaGovernanca — Núcleo › Administração › "Governança de ajustes" (`/nucleo/governanca`, permissão
 * `nucleo.administracao`). Abas: Segmentos · Portes · Motivos de perda (listas de opção) · Produtos e serviços (a mesma
 * tela de produtos dos cadastros) · Modelos de e-mail (os modelos de comunicação, com classificação).
 * Lê `?aba=segmentos|portes|motivos|produtos|modelos&id=` (o `id` abre um produto): envolva a página em <Suspense>.
 */
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { TelaProdutos, useIdDaUrl } from "@/components/cadastros";
import { TelaModelos } from "@/components/comercial/tela-modelos";
import { PageHeader } from "@/components/flic/page-header";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

import { TelaOpcoesLista } from "./tela-opcoes-lista";

type Aba = "segmentos" | "portes" | "motivos" | "produtos" | "modelos";
const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "segmentos", rotulo: "Segmentos" },
  { id: "portes", rotulo: "Portes" },
  { id: "motivos", rotulo: "Motivos de perda" },
  { id: "produtos", rotulo: "Produtos e serviços" },
  { id: "modelos", rotulo: "Modelos de e-mail" },
];

export function TelaGovernanca() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { podeVer } = useAuth();
  const id = useIdDaUrl();
  const aba = ABAS.find((a) => a.id === params.get("aba"))?.id ?? "segmentos";

  const trocar = (nova: Aba) => router.replace(`${pathname}?aba=${nova}`, { scroll: false });

  return (
    <>
      <Link href="/nucleo/administracao" className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-primary">
        <ArrowLeft className="size-4" />
        Administração
      </Link>
      <PageHeader titulo="Governança de ajustes" descricao="As listas e os modelos que toda a plataforma usa, num lugar só." />
      <div role="tablist" aria-label="Ajustes" className="mb-5 flex flex-wrap gap-2">
        {ABAS.map((a) => (
          <button
            key={a.id}
            role="tab"
            type="button"
            aria-selected={aba === a.id}
            onClick={() => trocar(a.id)}
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
        {aba === "segmentos" && <TelaOpcoesLista key="segmento" tipo="segmento" />}
        {aba === "portes" && <TelaOpcoesLista key="porte" tipo="porte" />}
        {aba === "motivos" && <TelaOpcoesLista key="motivo_perda" tipo="motivo_perda" />}
        {aba === "produtos" &&
          (podeVer("nucleo.cadastros") ? (
            <TelaProdutos key={id ?? 0} embutida idInicial={id} />
          ) : (
            <p className="text-sm text-muted">Seu perfil não tem acesso aos cadastros de produtos e serviços.</p>
          ))}
        {aba === "modelos" &&
          (podeVer("comercial.recursos") ? (
            <TelaModelos embutida classificacaoPadrao="geral" />
          ) : (
            <p className="text-sm text-muted">Seu perfil não tem acesso aos modelos de comunicação.</p>
          ))}
      </div>
    </>
  );
}
