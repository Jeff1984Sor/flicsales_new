"use client";

/**
 * AssistenteDrawer — "Assistente de orquestração" (IA unificada, protótipo `openAI`).
 * Montado UMA vez no shell. Abra de qualquer tela com `abrirAssistente(escopo, registro?)` (components/flic/eventos.ts):
 *   abrirAssistente("Este módulo")
 *   abrirAssistente("Este registro", { tipo: "oportunidade", id: 12, rotulo: "Aurora · Projeto de consultoria" })
 * ou já com a pergunta: `perguntarAoAssistente(escopo, pergunta, registro?)` (components/orquestracao/eventos-ia.ts).
 *
 * Chama POST /bff/orquestracao/ia/perguntar (`PerguntaIA` → `RespostaIA`, formato único em lib/types.ts).
 * Sem IA configurada a resposta vem das regras (origem "regras") e o drawer diz isso, com link para Configurações › IA.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { CorpoRespostaIA } from "@/components/orquestracao/resposta-ia";
import type { DetalheIAComPergunta } from "@/components/orquestracao/eventos-ia";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import type { EscopoIA, PerguntaIA, RegistroContexto, RespostaIA } from "@/lib/types";

import { NativeSelect } from "./form";
import { CampoDrawer, Drawer } from "./drawer";
import { EVENTO_IA } from "./eventos";
import { notificar } from "./toast";
import { itemDaRota, moduloDaRota, moduloPorId } from "./nav";

const ESCOPOS: EscopoIA[] = ["Este registro", "Este módulo", "Toda a FlicSales"];
const ESCOPO_API: Record<EscopoIA, PerguntaIA["escopo"]> = {
  "Este registro": "registro",
  "Este módulo": "modulo",
  "Toda a FlicSales": "tudo",
};

function perguntaPadrao(escopo: EscopoIA) {
  return escopo === "Toda a FlicSales" ? "Quais negociações podem afetar os recebimentos?" : "O que precisa de atenção neste contexto?";
}

function mensagemErro(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 404) return e.message && !/^Erro \d+$/.test(e.message) ? e.message : "O assistente ainda não está disponível neste ambiente.";
    if (e.status === 403) return "Seu perfil não tem acesso a este contexto pelo assistente. Peça ao gestor para liberar.";
    return e.message;
  }
  return "Não foi possível consultar o assistente agora.";
}

interface Troca {
  pergunta: string;
  resposta?: RespostaIA;
  erro?: string;
}

export function AssistenteDrawer() {
  const pathname = usePathname();
  const [aberto, setAberto] = useState(false);
  const [escopo, setEscopo] = useState<EscopoIA>("Este módulo");
  const [registro, setRegistro] = useState<RegistroContexto | null>(null);
  const [pergunta, setPergunta] = useState("");
  const [ultima, setUltima] = useState<Troca | null>(null);
  const [conversaId, setConversaId] = useState<number | null>(null);
  const pendente = useRef<{ texto: string; escopo: EscopoIA; registro: RegistroContexto | null } | null>(null);
  // abriu sem pergunta: mostra a pergunta padrão do escopo com a leitura do momento do módulo (como no protótipo)
  const [inicial, setInicial] = useState(false);

  const moduloId = moduloDaRota(pathname);
  const modulo = moduloPorId(moduloId);
  // o módulo Assistente não tem "este módulo": as perguntas valem para toda a FlicSales
  const moduloApi = moduloId === "assistente" ? null : moduloId;
  const escopoApi = (esc: EscopoIA) => (!moduloApi && esc === "Este módulo" ? "tudo" : ESCOPO_API[esc]);
  const tela = itemDaRota(pathname)?.label ?? "Início";

  // mesma chave da tela Assistente: reaproveita o cache e não refaz a leitura a cada abertura
  const leitura = useQuery({
    queryKey: ["orquestracao", "leitura", moduloApi],
    queryFn: () => api.get<RespostaIA>("/orquestracao/leitura", { modulo: moduloApi ?? undefined }),
    enabled: aberto && inicial && !!moduloApi,
    staleTime: 5 * 60_000,
    meta: { silencioso: true },
  });

  const perguntar = useMutation({
    meta: { silencioso: true },
    mutationFn: (corpo: PerguntaIA) => api.post<RespostaIA>("/orquestracao/ia/perguntar", corpo),
    onSuccess: (resposta, corpo) => {
      setUltima({ pergunta: corpo.pergunta, resposta });
      setConversaId(resposta.conversa_id ?? null);
    },
    onError: (e, corpo) => setUltima({ pergunta: corpo.pergunta, erro: mensagemErro(e) }),
  });
  const { mutate } = perguntar;

  const enviarTexto = (texto: string, esc: EscopoIA, reg: RegistroContexto | null, conversa: number | null) => {
    mutate({
      pergunta: texto,
      escopo: escopoApi(esc),
      modulo: moduloApi,
      tela,
      registro: esc === "Este registro" && reg ? { tipo: reg.tipo, id: Number(reg.id) } : null,
      conversa_id: conversa,
    });
  };

  useEffect(() => {
    const h = (e: Event) => {
      const d = (e as CustomEvent<DetalheIAComPergunta>).detail;
      const pedido = d?.escopo ?? "Este módulo";
      // no módulo Assistente não há "este módulo": a conversa vale para toda a FlicSales
      const esc = pedido === "Este módulo" && moduloDaRota(window.location.pathname) === "assistente" ? "Toda a FlicSales" : pedido;
      setEscopo(esc);
      setRegistro(d?.registro ?? null);
      setUltima(null);
      setConversaId(null);
      setPergunta("");
      setAberto(true);
      setInicial(!d?.pergunta);
      if (d?.pergunta) pendente.current = { texto: d.pergunta, escopo: esc, registro: d.registro ?? null };
    };
    window.addEventListener(EVENTO_IA, h);
    return () => window.removeEventListener(EVENTO_IA, h);
  }, []);

  // pergunta vinda de um atalho (tela Assistente): envia assim que o drawer abre
  useEffect(() => {
    if (!aberto || !pendente.current) return;
    const p = pendente.current;
    pendente.current = null;
    mutate({
      pergunta: p.texto,
      escopo: escopoApi(p.escopo),
      modulo: moduloApi,
      tela,
      registro: p.escopo === "Este registro" && p.registro ? { tipo: p.registro.tipo, id: Number(p.registro.id) } : null,
      conversa_id: null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- escopoApi deriva de moduloApi
  }, [aberto, mutate, moduloApi, tela]);

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    const texto = pergunta.trim();
    if (!texto) {
      notificar("Digite uma pergunta");
      return;
    }
    setInicial(false);
    enviarTexto(texto, escopo, registro, conversaId);
    setPergunta("");
  };

  const r = ultima?.resposta;
  const mostrarInicial = inicial && !ultima && !perguntar.isPending;

  return (
    <Drawer aberto={aberto} onFechar={() => setAberto(false)} rotulo="ASSISTENTE DE ORQUESTRAÇÃO" titulo="Vamos conectar os pontos.">
      <form onSubmit={enviar}>
        <CampoDrawer rotulo="Escopo da conversa" htmlFor="ia-escopo">
          <NativeSelect
            id="ia-escopo"
            value={escopo}
            onChange={(e) => {
              setEscopo(e.target.value as EscopoIA);
              setConversaId(null);
            }}
          >
            {ESCOPOS.map((s) => (
              <option key={s} value={s} disabled={(s === "Este registro" && !registro) || (s === "Este módulo" && !moduloApi)}>
                {s}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <p className="mt-2 text-sm text-muted">
          Contexto: {modulo.nome} / {tela}
          {escopo === "Este registro" && registro?.rotulo ? ` / ${registro.rotulo}` : ""}
        </p>

        {mostrarInicial && (
          <>
            <div className="mt-[15px] rounded-[7px] bg-tint p-3 text-sm">{perguntaPadrao(escopo)}</div>
            <div className="my-5 rounded-[9px] bg-subtle p-[18px] text-[13px]" aria-live="polite">
              {!moduloApi ? (
                <p className="text-muted">
                  Pergunte sobre Núcleo, Comercial e Financeiro. As respostas trazem evidência, fonte e limite, dentro das permissões do seu perfil.
                </p>
              ) : leitura.isLoading ? (
                <p className="flex items-center gap-2 text-muted">
                  <Loader2 className="size-4 animate-spin" /> Consultando as fontes permitidas ao seu perfil…
                </p>
              ) : leitura.error ? (
                <p className="text-muted">{mensagemErro(leitura.error)}</p>
              ) : leitura.data ? (
                <CorpoRespostaIA r={leitura.data} />
              ) : null}
            </div>
            {leitura.data && (
              <details className="border-t border-line py-[15px] text-xs">
                <summary className="cursor-pointer font-semibold">Assistentes e fontes consultadas</summary>
                <p className="pt-2.5 leading-relaxed">
                  {leitura.data.ferramentas.length ? leitura.data.ferramentas.join(" · ") : "Nenhuma fonte disponível ao seu perfil neste escopo"}.{" "}
                  Leitura do momento de {modulo.nome}. {leitura.data.origem === "ia" ? "Interpretada pela IA configurada." : "Calculada pelas regras do produto (sem IA)."}{" "}
                  Fontes externas (agenda, e-mail, WhatsApp) só entram com conexão autorizada. Cada ferramenta respeita as permissões do seu perfil.
                </p>
              </details>
            )}
          </>
        )}

        {(ultima || perguntar.isPending) && (
          <>
            {ultima && <div className="mt-[15px] rounded-[7px] bg-tint p-3 text-sm">{ultima.pergunta}</div>}
            <div className="my-5 rounded-[9px] bg-subtle p-[18px] text-[13px]" aria-live="polite">
              {perguntar.isPending ? (
                <p className="flex items-center gap-2 text-muted">
                  <Loader2 className="size-4 animate-spin" /> Consultando as fontes permitidas ao seu perfil…
                </p>
              ) : ultima?.erro ? (
                <p className="text-muted">{ultima.erro}</p>
              ) : r ? (
                <CorpoRespostaIA r={r} />
              ) : null}
            </div>
            {r && !perguntar.isPending && (
              <details className="border-t border-line py-[15px] text-xs">
                <summary className="cursor-pointer font-semibold">Assistentes e fontes consultadas</summary>
                <p className="pt-2.5 leading-relaxed">
                  {r.ferramentas.length ? r.ferramentas.join(" · ") : "Nenhuma fonte disponível ao seu perfil neste escopo"}.{" "}
                  {r.origem === "ia" ? "Interpretado pela IA configurada." : "Calculado pelas regras do produto (sem IA)."} Fontes externas
                  (agenda, e-mail, WhatsApp) só entram com conexão autorizada. Cada ferramenta respeita as permissões do seu perfil.
                </p>
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
            maxLength={2000}
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
          A IA interpreta evidências dentro das suas permissões e mostra fonte e limite. Texto importado é dado, nunca instrução. Ações sugeridas
          só viram registro após sua revisão.
        </p>
      </form>
    </Drawer>
  );
}
