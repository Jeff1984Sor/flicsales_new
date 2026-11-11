"use client";

/**
 * EnviarWhatsAppDrawer — envio por WhatsApp (Evolution API da organização), análogo ao EnviarEmailDrawer.
 *
 * Props:
 *  - `aberto`, `onFechar`
 *  - `destino`        { tipo: "comunicacao" } | { tipo: "proposta", id } | { tipo: "cobranca", id } — define a rota de envio
 *  - `empresaId?`     sugere os telefones das pessoas da empresa (opt-out aparece desabilitado)
 *  - `oportunidadeId?` usada na prévia dos modelos comerciais (e no vínculo da comunicação)
 *  - `modelos`        "comercial" (GET /comercial/modelos?canal=whatsapp) | "financeiro" (GET /financeiro/cobrancas/modelos?canal=whatsapp)
 *  - `contexto?`      linha cinza abaixo do título
 *  - `textoInicial?`
 *  - `vinculo?`       campos extras no topo (ex.: oportunidade/empresa em Comunicações)
 *  - `aoEnviar?`      chamado após o envio
 *
 * Também exporta `usePodeWhatsApp()` — true quando `GET /auth/me/envio` traz `whatsapp.pode_enviar`. Os botões
 * "WhatsApp" das telas só aparecem com permissão de editar E esse sinal.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Send, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import type { ModeloComunicacao, PreviaModelo } from "@/lib/tipos-comercial";
import type { Pessoa } from "@/lib/tipos-nucleo";
import type { EnvioWhatsAppIn, EnvioWhatsAppOut, Pagina, StatusEnvio } from "@/lib/types";
import { cn } from "@/lib/utils";

import { CampoDrawer, Drawer } from "./drawer";
import type { DestinoEmail } from "./enviar-email";
import { Etiqueta } from "./etiqueta";
import { NativeSelect } from "./form";
import { notificar } from "./toast";

export type DestinoWhatsApp = DestinoEmail;

const MAX_DESTINATARIOS = 10;
const MAX_TEXTO = 4000;

const ROTULO_REGISTRO: Record<DestinoWhatsApp["tipo"], string> = {
  comunicacao: "A mensagem vira uma comunicação de WhatsApp vinculada.",
  proposta: "A mensagem fica registrada na oportunidade da proposta.",
  cobranca: "A mensagem entra no histórico da cobrança.",
};

/** Mesma consulta do e-mail: `GET /auth/me/envio`. */
function useStatusEnvio() {
  return useQuery({
    queryKey: ["auth", "me", "envio"],
    queryFn: () => api.get<StatusEnvio>("/auth/me/envio"),
    retry: false,
    staleTime: 60_000,
    meta: { silencioso: true },
  });
}

/** WhatsApp liberado para o usuário (Evolution configurada e conectada). */
export function usePodeWhatsApp(): boolean {
  const { data } = useStatusEnvio();
  return data?.whatsapp?.pode_enviar === true;
}

/** "(11) 99999-0000", "+55 11 …" → "5511999990000"; inválido → null. */
export function normalizarTelefone(v: string): string | null {
  const d = v.replace(/\D/g, "");
  if (d.length === 10 || d.length === 11) return `55${d}`;
  if ((d.length === 12 || d.length === 13) && d.startsWith("55")) return d;
  return null;
}

/** "5511999990000" → "+55 (11) 99999-0000". */
export function formatarTelefone(d: string): string {
  if (!/^55\d{10,11}$/.test(d)) return d;
  const ddd = d.slice(2, 4);
  const resto = d.slice(4);
  const meio = resto.length === 9 ? resto.slice(0, 5) : resto.slice(0, 4);
  return `+55 (${ddd}) ${meio}-${resto.slice(meio.length)}`;
}

interface Contato {
  pessoaId: number;
  nome: string;
  telefone: string;
  optOut: boolean;
}

function contatosDe(pessoas: Pessoa[]): Contato[] {
  const lista: Contato[] = [];
  for (const p of pessoas) {
    const optOut = (p.permissoes_comunicacao ?? []).includes("opt_out");
    const numeros = p.telefones?.length
      ? [...p.telefones].sort((a, b) => Number(b.principal) - Number(a.principal)).map((t) => t.numero)
      : p.telefone
        ? [p.telefone]
        : [];
    const vistos = new Set<string>();
    for (const n of numeros) {
      const t = normalizarTelefone(n);
      if (!t || vistos.has(t)) continue;
      vistos.add(t);
      lista.push({ pessoaId: p.id, nome: p.nome, telefone: t, optOut });
    }
  }
  return lista;
}

export function EnviarWhatsAppDrawer({
  aberto,
  onFechar,
  destino,
  empresaId,
  oportunidadeId,
  modelos,
  contexto,
  textoInicial,
  vinculo,
  aoEnviar,
}: {
  aberto: boolean;
  onFechar: () => void;
  destino: DestinoWhatsApp;
  empresaId?: number | null;
  oportunidadeId?: number | null;
  modelos: "comercial" | "financeiro";
  contexto?: string;
  textoInicial?: string;
  vinculo?: React.ReactNode;
  aoEnviar?: (r: EnvioWhatsAppOut) => void;
}) {
  const chave = `${destino.tipo}-${"id" in destino ? destino.id : "novo"}`;
  return (
    <Drawer aberto={aberto} onFechar={onFechar} rotulo="WHATSAPP / ENVIO" titulo="Enviar WhatsApp" descricao={contexto} largura={560}>
      {aberto && (
        <Corpo
          key={chave}
          destino={destino}
          empresaId={empresaId ?? null}
          oportunidadeId={oportunidadeId ?? null}
          modelos={modelos}
          textoInicial={textoInicial ?? ""}
          vinculo={vinculo}
          onFechar={onFechar}
          aoEnviar={aoEnviar}
        />
      )}
    </Drawer>
  );
}

function Corpo({
  destino,
  empresaId,
  oportunidadeId,
  modelos,
  textoInicial,
  vinculo,
  onFechar,
  aoEnviar,
}: {
  destino: DestinoWhatsApp;
  empresaId: number | null;
  oportunidadeId: number | null;
  modelos: "comercial" | "financeiro";
  textoInicial: string;
  vinculo?: React.ReactNode;
  onFechar: () => void;
  aoEnviar?: (r: EnvioWhatsAppOut) => void;
}) {
  const qc = useQueryClient();
  const [para, setPara] = useState<string[]>([]);
  const [digitado, setDigitado] = useState("");
  const [modeloId, setModeloId] = useState("");
  const [texto, setTexto] = useState(textoInicial);
  const [faltando, setFaltando] = useState<string[]>([]);
  const [anexarPdf, setAnexarPdf] = useState(true);

  const status = useStatusEnvio();
  const whats = status.data?.whatsapp ?? null;
  const podeEnviar = whats?.pode_enviar === true;

  const pessoas = useQuery({
    queryKey: ["nucleo", "pessoas", "envio", empresaId],
    queryFn: () => api.get<Pagina<Pessoa>>("/nucleo/pessoas", { empresa_id: empresaId ?? undefined, por_pagina: 200 }),
    enabled: empresaId != null,
    retry: false,
    meta: { silencioso: true },
  });
  const contatos = useMemo(() => contatosDe(pessoas.data?.itens ?? []), [pessoas.data]);
  const optOut = useMemo(() => new Map(contatos.filter((c) => c.optOut).map((c) => [c.telefone, c.nome])), [contatos]);
  const nomes = useMemo(() => new Map(contatos.map((c) => [c.telefone, c.nome])), [contatos]);

  const listaModelos = useQuery({
    queryKey: ["modelos-envio", modelos, "whatsapp"],
    queryFn: () =>
      modelos === "financeiro"
        ? api.get<ModeloComunicacao[]>("/financeiro/cobrancas/modelos", { canal: "whatsapp" })
        : api.get<ModeloComunicacao[]>("/comercial/modelos", { contexto: "comercial", canal: "whatsapp" }),
    retry: false,
    meta: { silencioso: true },
  });

  const previa = useMutation({
    mutationFn: (m: ModeloComunicacao) => {
      if (modelos === "financeiro") {
        if (destino.tipo !== "cobranca") throw new ApiError(400, "Modelo financeiro só se aplica a uma cobrança.");
        return api.post<PreviaModelo>(`/financeiro/cobrancas/${destino.id}/modelos/${m.id}/previa`);
      }
      return api.post<PreviaModelo>(`/comercial/modelos/${m.id}/previa`, { oportunidade_id: oportunidadeId });
    },
    meta: { silencioso: true },
    onSuccess: (p) => {
      setTexto(p.conteudo);
      setFaltando(p.faltando);
    },
    onError: (_e, m) => {
      setTexto(m.conteudo);
      setFaltando(m.variaveis);
      notificar("Não foi possível preencher o modelo. As variáveis ficaram no texto para você revisar.");
    },
  });

  const enviar = useMutation({
    mutationFn: () => {
      const base: EnvioWhatsAppIn = { para, texto: texto.trim(), modelo_id: modeloId ? Number(modeloId) : null };
      if (destino.tipo === "comunicacao") {
        return api.post<EnvioWhatsAppOut>("/comercial/comunicacoes/enviar-whatsapp", { ...base, empresa_id: empresaId, oportunidade_id: oportunidadeId });
      }
      if (destino.tipo === "proposta") {
        return api.post<EnvioWhatsAppOut>(`/comercial/propostas/${destino.id}/enviar-whatsapp`, { ...base, anexar_pdf: anexarPdf });
      }
      return api.post<EnvioWhatsAppOut>(`/financeiro/cobrancas/${destino.id}/enviar-whatsapp`, base);
    },
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: [destino.tipo === "cobranca" ? "financeiro" : "comercial"] });
      notificar.sucesso(`WhatsApp enviado para ${r.enviado_para.map(formatarTelefone).join(", ")}`);
      if (r.registro) notificar.info(r.registro);
      aoEnviar?.(r);
      onFechar();
    },
  });

  const bloqueados = para.filter((t) => optOut.has(t));

  function incluir(t: string) {
    setPara((v) => (v.includes(t) ? v : [...v, t]));
  }

  function incluirDigitado() {
    if (!digitado.trim()) return;
    const t = normalizarTelefone(digitado);
    if (!t) {
      notificar.erro("Telefone inválido. Use DDD + número, ex.: (11) 99999-0000.");
      return;
    }
    incluir(t);
    setDigitado("");
  }

  function escolherModelo(id: string) {
    setModeloId(id);
    setFaltando([]);
    const m = (listaModelos.data ?? []).find((x) => String(x.id) === id);
    if (m) previa.mutate(m);
  }

  function validar(): string | null {
    if (!para.length) return "Informe ao menos um telefone.";
    if (para.length > MAX_DESTINATARIOS) return `No máximo ${MAX_DESTINATARIOS} telefones por envio.`;
    if (bloqueados.length) return `${optOut.get(bloqueados[0])} pediu para não receber comunicações (opt-out).`;
    if (!texto.trim()) return "Escreva a mensagem.";
    if (texto.length > MAX_TEXTO) return `A mensagem passa de ${MAX_TEXTO} caracteres.`;
    return null;
  }

  return (
    <form
      id="f-enviar-whatsapp"
      onSubmit={(e) => {
        e.preventDefault();
        if (!podeEnviar || enviar.isPending) return;
        const erro = validar();
        if (erro) {
          notificar.erro(erro);
          return;
        }
        enviar.mutate();
      }}
    >
      {vinculo}

      <CampoDrawer rotulo="Para" obrigatorio dica={`Até ${MAX_DESTINATARIOS} telefones, com DDD.`}>
        <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-input px-2 py-1.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30">
          {para.map((t) => (
            <span key={t} className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs", optOut.has(t) ? "bg-amber/15 text-amber-ink" : "bg-brand/12")}>
              <span className="num">{formatarTelefone(t)}</span>
              {nomes.get(t) && <span className="text-muted">· {nomes.get(t)}</span>}
              <button type="button" onClick={() => setPara((v) => v.filter((x) => x !== t))} aria-label={`Remover ${formatarTelefone(t)}`}>
                <X className="size-3" />
              </button>
            </span>
          ))}
          <input
            value={digitado}
            onChange={(e) => setDigitado(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "," || e.key === ";") {
                e.preventDefault();
                incluirDigitado();
              } else if (e.key === "Backspace" && !digitado && para.length) setPara((v) => v.slice(0, -1));
            }}
            onBlur={incluirDigitado}
            inputMode="tel"
            placeholder={para.length ? "" : "(11) 99999-0000 — Enter para adicionar"}
            className="min-w-[180px] flex-1 bg-transparent text-sm outline-none"
            aria-label="Telefone"
          />
        </div>
      </CampoDrawer>
      {bloqueados.length > 0 && (
        <p className="mt-2 rounded-[8px] bg-amber/15 p-2.5 text-xs text-amber-ink">
          Opt-out: {bloqueados.map((t) => optOut.get(t)).join(", ")} pediu para não receber comunicações. Remova antes de enviar.
        </p>
      )}

      {empresaId != null && (
        <div className="mt-3">
          <span className="eyebrow">PESSOAS DA EMPRESA</span>
          {pessoas.isPending ? (
            <p className="mt-2 text-xs text-muted">Carregando contatos…</p>
          ) : contatos.length === 0 ? (
            <p className="mt-2 text-xs text-muted">Nenhuma pessoa com telefone nesta empresa.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line rounded-[8px] border border-line">
              {contatos.map((c) => {
                const incluido = para.includes(c.telefone);
                return (
                  <li key={`${c.pessoaId}-${c.telefone}`} className={cn("flex items-center justify-between gap-2 px-3 py-2 text-sm", c.optOut && "opacity-60")}>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{c.nome}</p>
                      <p className="num truncate text-xs text-muted">{formatarTelefone(c.telefone)}</p>
                    </div>
                    {c.optOut ? (
                      <Etiqueta tom="amber">Opt-out</Etiqueta>
                    ) : (
                      <Button type="button" size="sm" variant={incluido ? "secondary" : "outline"} disabled={incluido} onClick={() => incluir(c.telefone)}>
                        {incluido ? "Incluído" : "Incluir"}
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      <CampoDrawer
        rotulo="Modelo"
        dica={listaModelos.isError ? "Modelos indisponíveis no momento. Escreva a mensagem abaixo." : "Modelos de WhatsApp. O texto fica editável."}
      >
        <NativeSelect value={modeloId} onChange={(e) => escolherModelo(e.target.value)} disabled={previa.isPending}>
          <option value="">Sem modelo</option>
          {(listaModelos.data ?? []).map((m) => (
            <option key={m.id} value={m.id}>
              {m.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      {previa.isPending && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
          <Loader2 className="size-3 animate-spin" /> Preenchendo o modelo…
        </p>
      )}
      {faltando.length > 0 && (
        <p className="mt-2 text-xs text-amber-ink">Sem valor no registro: {faltando.map((v) => `{{${v}}}`).join(", ")}. Revise antes de enviar.</p>
      )}

      <CampoDrawer rotulo="Mensagem" obrigatorio dica={`Seu nome é acrescentado no fim. ${texto.length}/${MAX_TEXTO}`}>
        <Textarea rows={9} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={MAX_TEXTO} />
      </CampoDrawer>

      {destino.tipo === "proposta" && (
        <label className="mt-4 flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4 accent-primary" checked={anexarPdf} onChange={(e) => setAnexarPdf(e.target.checked)} />
          Anexar PDF
        </label>
      )}

      <div className="mt-5 rounded-[10px] border border-line bg-subtle p-3 text-xs">
        {status.isPending ? (
          <p className="text-muted">Conferindo o WhatsApp de envio…</p>
        ) : status.isError ? (
          <p className="text-amber-ink">Envio por WhatsApp ainda indisponível no servidor.</p>
        ) : podeEnviar ? (
          <p>
            Enviar pelo número <strong className="num">{whats?.numero ? formatarTelefone(normalizarTelefone(whats.numero) ?? whats.numero) : "da organização"}</strong>
          </p>
        ) : (
          <p className="text-amber-ink">
            WhatsApp não conectado.{" "}
            <Link href="/nucleo/integracoes" className="font-medium text-primary underline">
              Configurar em Núcleo › Integrações
            </Link>
          </p>
        )}
        <p className="mt-1.5 text-muted">{ROTULO_REGISTRO[destino.tipo]} Pessoas com opt-out não recebem.</p>
      </div>

      <div className="mt-5 flex gap-2">
        <Button type="submit" disabled={!podeEnviar || enviar.isPending || previa.isPending}>
          {enviar.isPending ? <Loader2 className="animate-spin" /> : <Send />}
          Enviar
        </Button>
        <Button type="button" variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
