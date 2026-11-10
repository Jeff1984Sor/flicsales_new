"use client";

/**
 * AssistenteDrawer — "Assistente de orquestração" (IA unificada, protótipo `openAI`).
 * Montado UMA vez no shell. Abra de qualquer tela com `abrirAssistente(escopo, registro?)` (components/flic/eventos.ts):
 *   abrirAssistente("Este módulo")
 *   abrirAssistente("Este registro", { tipo: "oportunidade", id: 12, rotulo: "Aurora · Projeto de consultoria" })
 *
 * Chama POST /bff/orquestracao/ia/perguntar (corpo `PerguntaIA`, resposta `RespostaIA` em lib/types.ts).
 * Enquanto a rota não existir (404) ou a IA estiver desligada, mostra mensagem amigável — o produto segue útil.
 */
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import type { EscopoIA, PerguntaIA, RegistroContexto, RespostaIA } from "@/lib/types";

import { NativeSelect } from "./form";
import { CampoDrawer, Drawer } from "./drawer";
import { EVENTO_IA, type DetalheIA } from "./eventos";
import { Fonte } from "./fonte";
import { itemDaRota, moduloDaRota, moduloPorId } from "./nav";
import { notificar } from "./toast";

const ESCOPOS: EscopoIA[] = ["Este registro", "Este módulo", "Toda a FlicSales"];
const ESCOPO_API: Record<EscopoIA, PerguntaIA["escopo"]> = {
  "Este registro": "registro",
  "Este módulo": "modulo",
  "Toda a FlicSales": "global",
};

function mensagemErro(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 404) return "O assistente ainda não está disponível neste ambiente. As telas continuam úteis com as regras de cada módulo.";
    if (e.status === 403) return "Seu perfil não tem acesso ao assistente. Peça ao gestor para liberar.";
    if (e.status === 503 || e.status === 409)
      return e.message && !/^Erro \d+$/.test(e.message) ? e.message : "A IA está desligada. Configure em Configurações › Inteligência Artificial.";
    return e.message;
  }
  return "Não foi possível consultar o assistente agora.";
}

export function AssistenteDrawer() {
  const pathname = usePathname();
  const [aberto, setAberto] = useState(false);
  const [escopo, setEscopo] = useState<EscopoIA>("Este módulo");
  const [registro, setRegistro] = useState<RegistroContexto | null>(null);
  const [pergunta, setPergunta] = useState("");
  const [ultima, setUltima] = useState<{ pergunta: string; resposta?: RespostaIA; erro?: string } | null>(null);

  const modulo = moduloPorId(moduloDaRota(pathname));
  const tela = itemDaRota(pathname)?.label ?? "Início";

  useEffect(() => {
    const h = (e: Event) => {
      const d = (e as CustomEvent<DetalheIA>).detail;
      setEscopo(d?.escopo ?? "Este módulo");
      setRegistro(d?.registro ?? null);
      setUltima(null);
      setAberto(true);
    };
    window.addEventListener(EVENTO_IA, h);
    return () => window.removeEventListener(EVENTO_IA, h);
  }, []);

  const perguntar = useMutation({
    meta: { silencioso: true },
    mutationFn: (corpo: PerguntaIA) => api.post<RespostaIA>("/orquestracao/ia/perguntar", corpo),
    onSuccess: (resposta, corpo) => setUltima({ pergunta: corpo.pergunta, resposta }),
    onError: (e, corpo) => setUltima({ pergunta: corpo.pergunta, erro: mensagemErro(e) }),
  });

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    const texto = pergunta.trim() || (escopo === "Toda a FlicSales" ? "Quais negociações podem afetar os recebimentos?" : "O que precisa de atenção neste contexto?");
    perguntar.mutate({
      pergunta: texto,
      escopo: ESCOPO_API[escopo],
      contexto: { modulo: modulo.nome, tela, rota: pathname, registro: escopo === "Este registro" ? registro : null },
    });
    setPergunta("");
  };

  const r = ultima?.resposta;

  return (
    <Drawer aberto={aberto} onFechar={() => setAberto(false)} rotulo="ASSISTENTE DE ORQUESTRAÇÃO" titulo="Vamos conectar os pontos.">
      <form onSubmit={enviar}>
        <CampoDrawer rotulo="Escopo da conversa" htmlFor="ia-escopo">
          <NativeSelect id="ia-escopo" value={escopo} onChange={(e) => setEscopo(e.target.value as EscopoIA)}>
            {ESCOPOS.map((s) => (
              <option key={s} value={s} disabled={s === "Este registro" && !registro}>
                {s}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <p className="mt-2 text-sm text-muted">
          Contexto: {modulo.nome} / {tela}
          {escopo === "Este registro" && registro?.rotulo ? ` / ${registro.rotulo}` : ""}
        </p>

        {ultima && (
          <>
            <div className="mt-[15px] rounded-[7px] bg-tint p-3 text-sm">{ultima.pergunta}</div>
            <div className="my-5 rounded-[9px] bg-subtle p-[18px] text-[13px]" aria-live="polite">
              {ultima.erro ? (
                <p className="text-muted">{ultima.erro}</p>
              ) : r ? (
                <>
                  <h3 className="mb-2.5 text-sm font-bold">{r.titulo || "Leitura do contexto"}</h3>
                  <p className="mb-3 leading-relaxed whitespace-pre-line">{r.resumo}</p>
                  {r.proxima_acao && (
                    <>
                      <h3 className="mb-2.5 text-sm font-bold">Próxima ação sugerida</h3>
                      <p className="mb-3 leading-relaxed">{r.proxima_acao}</p>
                    </>
                  )}
                  <Fonte evidencia={r.evidencias} fonte={r.fontes} limite={r.limites} />
                  {r.ia_ativa === false && <p className="text-xs text-muted">IA desligada: leitura calculada pelas regras do produto.</p>}
                  {(r.acoes_sugeridas?.length ?? 0) > 0 && (
                    <Button
                      type="button"
                      variant="outline"
                      className="mt-2"
                      onClick={() => notificar("Ação registrada como proposta. Revise antes de confirmar no módulo.")}
                    >
                      Criar tarefa após revisão
                    </Button>
                  )}
                </>
              ) : null}
            </div>
            {r && (r.ferramentas?.length ?? 0) > 0 && (
              <details className="border-t border-line py-[15px] text-xs">
                <summary className="cursor-pointer font-semibold">Assistentes e fontes consultadas</summary>
                <p className="pt-2.5 leading-relaxed">{r.ferramentas?.join(" · ")}. Cada ferramenta respeita as permissões do seu perfil.</p>
              </details>
            )}
          </>
        )}

        <CampoDrawer rotulo="Sua pergunta" htmlFor="ia-pergunta">
          <Textarea
            id="ia-pergunta"
            value={pergunta}
            onChange={(e) => setPergunta(e.target.value)}
            placeholder="Ex.: Por que esta negociação está parada?"
            className="min-h-[85px]"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) enviar(e);
            }}
          />
        </CampoDrawer>
        <Button type="submit" className="mt-4" disabled={perguntar.isPending}>
          {perguntar.isPending && <Loader2 className="animate-spin" />}
          {perguntar.isPending ? "Conectando os pontos…" : "Perguntar"}
        </Button>
        <p className="mt-3 text-[11px] text-muted">
          A IA interpreta evidências dentro das suas permissões e mostra fonte e limite. Ações sugeridas só viram registro após sua revisão.
        </p>
      </form>
    </Drawer>
  );
}
