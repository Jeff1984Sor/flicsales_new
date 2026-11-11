"use client";

/**
 * Módulo Assistente › "Assistente" (protótipo `assistant()`): chat universal da IA unificada, escopo "Toda a FlicSales".
 * Atalhos abrem o drawer JÁ perguntando: Analisar a operação · Relacionar vendas e caixa · Priorizar minha semana.
 * Mostra se a IA está ligada (senão: leitura por regras + link para Configurações de IA) e a leitura do momento,
 * com escolha da área (Comercial · Financeiro · Núcleo).
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Fonte } from "@/components/flic/fonte";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { Etiqueta } from "@/components/flic/etiqueta";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { EstadoIA } from "@/lib/tipos-orquestracao";
import type { RespostaIA } from "@/lib/types";

import { perguntarAoAssistente } from "./eventos-ia";
import { AvisoIADesligada, CorpoRespostaIA } from "./resposta-ia";

const ATALHOS = [
  {
    rotulo: "Analisar a operação",
    escopo: "Toda a FlicSales",
    pergunta: "Analise a operação (Núcleo, Comercial e Financeiro): o que merece atenção agora e por quê?",
  },
  {
    rotulo: "Relacionar vendas e caixa",
    escopo: "Toda a FlicSales",
    pergunta: "Quais negociações podem afetar os recebimentos e o caixa? Separe potencial comercial de recebível e de saldo.",
  },
  { rotulo: "Priorizar minha semana", escopo: "Toda a FlicSales", pergunta: "Priorize minha semana: quais são as próximas ações mais importantes e por quê?" },
] as const;

type AreaLeitura = "comercial" | "financeiro" | "nucleo";
const AREAS: { id: AreaLeitura; rotulo: string }[] = [
  { id: "comercial", rotulo: "Comercial" },
  { id: "financeiro", rotulo: "Financeiro" },
  { id: "nucleo", rotulo: "Núcleo" },
];

export function AssistenteTela() {
  const [modulo, setModulo] = useState<AreaLeitura>("comercial");
  const estado = useQuery({
    queryKey: ["orquestracao", "ia", "estado"],
    queryFn: () => api.get<EstadoIA>("/orquestracao/ia/estado"),
    meta: { silencioso: true },
  });
  const leitura = useQuery({
    queryKey: ["orquestracao", "leitura", modulo],
    queryFn: () => api.get<RespostaIA>("/orquestracao/leitura", { modulo }),
    meta: { silencioso: true },
  });

  return (
    <>
      <PageHeader
        titulo="Uma conversa. Todos os contextos."
        descricao="Pergunte sobre Núcleo, Comercial e Financeiro. Os assistentes especializados trabalham juntos dentro das suas permissões."
      />
      <div className="card-surface mx-auto my-[35px] max-w-[850px] p-[25px] text-center md:p-[45px]">
        <div className="text-[44px] leading-none text-accent" aria-hidden>
          ✧
        </div>
        <h1 className="mt-[18px] text-[29px] font-bold tracking-[-0.9px]">O que você precisa decidir?</h1>
        <p className="mt-1.5 text-muted">Conecte evidências, entenda impactos e prepare a próxima ação.</p>
        <div className="mt-[25px] flex flex-wrap justify-center gap-2.5">
          {ATALHOS.map((a) => (
            <Button key={a.rotulo} variant="outline" onClick={() => perguntarAoAssistente(a.escopo, a.pergunta)}>
              {a.rotulo}
            </Button>
          ))}
        </div>
        <div className="mt-5 flex justify-center">
          {estado.data ? (
            estado.data.ligada ? (
              <Etiqueta tom="green">IA ligada{estado.data.modelo ? ` · ${estado.data.modelo}` : ""}</Etiqueta>
            ) : (
              <div className="flex flex-col items-center gap-1.5">
                <Etiqueta tom="amber">IA desligada · leitura por regras</Etiqueta>
                <AvisoIADesligada />
              </div>
            )
          ) : null}
        </div>
        <Fonte className="mt-[30px] text-left">
          Uma camada de IA compartilhada, com ferramentas de leitura por área e as permissões do seu perfil. Toda resposta traz evidência, fonte e
          limite; texto importado (e-mail, notas, WhatsApp) é dado, nunca instrução; ações sugeridas só viram registro após sua revisão.
        </Fonte>
      </div>

      <div className="mx-auto max-w-[850px]">
        <Painel
          titulo="Leitura do momento"
          acao={leitura.data ? <Etiqueta tom={leitura.data.origem === "ia" ? "green" : "neutra"}>{leitura.data.origem === "ia" ? "IA" : "Regras"}</Etiqueta> : null}
        >
          <div role="tablist" aria-label="Área da leitura" className="mb-4 flex flex-wrap gap-2">
            {AREAS.map((a) => (
              <button
                key={a.id}
                type="button"
                role="tab"
                aria-selected={modulo === a.id}
                onClick={() => setModulo(a.id)}
                className={cn(
                  "rounded-[7px] border px-3 py-1.5 text-xs transition",
                  modulo === a.id ? "border-primary bg-primary font-semibold text-primary-foreground" : "border-line bg-surface hover:border-primary",
                )}
              >
                {a.rotulo}
              </button>
            ))}
          </div>
          {leitura.isPending ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ) : leitura.isError ? (
            <p className="text-sm text-muted">Não foi possível calcular a leitura agora.</p>
          ) : leitura.data ? (
            <div className="text-[13px]">
              <CorpoRespostaIA r={leitura.data} />
            </div>
          ) : null}
        </Painel>
      </div>
    </>
  );
}
