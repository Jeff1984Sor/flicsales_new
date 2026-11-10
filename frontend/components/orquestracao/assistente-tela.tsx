"use client";

/**
 * Tela "Assistente" dos 3 módulos (protótipo `assistant()`): porta de entrada da IA unificada.
 * Atalhos abrem o drawer JÁ perguntando: Analisar este módulo · Relacionar vendas e caixa · Priorizar minha semana.
 * Mostra se a IA está ligada (senão: leitura por regras + link para Configurações › IA) e a leitura do momento do módulo.
 */
import { useQuery } from "@tanstack/react-query";
import { usePathname } from "next/navigation";

import { Fonte } from "@/components/flic/fonte";
import { moduloDaRota } from "@/components/flic/nav";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { Etiqueta } from "@/components/flic/etiqueta";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { EstadoIA } from "@/lib/tipos-orquestracao";
import type { RespostaIA } from "@/lib/types";

import { perguntarAoAssistente } from "./eventos-ia";
import { AvisoIADesligada, CorpoRespostaIA } from "./resposta-ia";

const ATALHOS = [
  { rotulo: "Analisar este módulo", escopo: "Este módulo", pergunta: "Analise este módulo: o que merece atenção agora e por quê?" },
  {
    rotulo: "Relacionar vendas e caixa",
    escopo: "Toda a FlicSales",
    pergunta: "Quais negociações podem afetar os recebimentos e o caixa? Separe potencial comercial de recebível e de saldo.",
  },
  { rotulo: "Priorizar minha semana", escopo: "Este módulo", pergunta: "Priorize minha semana: quais são as próximas ações mais importantes e por quê?" },
] as const;

export function AssistenteTela() {
  const modulo = moduloDaRota(usePathname());
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
      <PageHeader titulo="Uma conversa. Todos os contextos." descricao="Os assistentes especializados trabalham juntos dentro das suas permissões." />
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
