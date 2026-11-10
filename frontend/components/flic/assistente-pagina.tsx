"use client";

/**
 * AssistentePagina — tela "Assistente" dos 3 módulos (protótipo `assistant()`): porta de entrada da IA unificada.
 * Os atalhos abrem o AssistenteDrawer com o escopo certo; o contexto (módulo/tela) vem da rota atual.
 */
import { Button } from "@/components/ui/button";

import { abrirAssistente } from "./eventos";
import { Fonte } from "./fonte";
import { PageHeader } from "./page-header";

export function AssistentePagina() {
  return (
    <>
      <PageHeader titulo="Uma conversa. Todos os contextos." descricao="Os assistentes especializados trabalham juntos dentro das suas permissões." />
      <div className="card-surface mx-auto my-[35px] max-w-[850px] p-[45px] text-center">
        <div className="text-[44px] leading-none text-primary" aria-hidden>
          ✧
        </div>
        <h1 className="mt-[18px] text-[29px] font-bold tracking-[-0.9px]">O que você precisa decidir?</h1>
        <p className="mt-1.5 text-muted">Conecte evidências, entenda impactos e prepare a próxima ação.</p>
        <div className="mt-[25px] flex flex-wrap justify-center gap-2.5">
          <Button variant="outline" onClick={() => abrirAssistente("Este módulo")}>
            Analisar este módulo
          </Button>
          <Button variant="outline" onClick={() => abrirAssistente("Toda a FlicSales")}>
            Relacionar vendas e caixa
          </Button>
          <Button variant="outline" onClick={() => abrirAssistente("Este módulo")}>
            Priorizar minha semana
          </Button>
        </div>
        <Fonte className="mt-[30px] text-left">
          Uma camada de IA compartilhada, com ferramentas de leitura por área e as permissões do seu perfil. Toda resposta traz evidência, fonte e
          limite; ações sugeridas só viram registro após sua revisão.
        </Fonte>
      </div>
    </>
  );
}
