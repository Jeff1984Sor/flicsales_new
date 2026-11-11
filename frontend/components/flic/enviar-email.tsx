"use client";

/**
 * EnviarEmailDrawer — composição de e-mail reutilizável (Comunicações, Proposta, Cobrança).
 *
 * Props:
 *  - `aberto`, `onFechar`
 *  - `destino`        { tipo: "comunicacao" } | { tipo: "proposta", id } | { tipo: "cobranca", id } — define a rota de envio
 *  - `empresaId?`     empresa do registro: sugere as pessoas dela em Para/Cc (opt-out aparece desabilitado)
 *  - `oportunidadeId?` oportunidade usada na prévia dos modelos comerciais (e no vínculo da comunicação)
 *  - `modelos`        "comercial" (GET /comercial/modelos?contexto=comercial) | "financeiro" (GET /financeiro/cobrancas/modelos)
 *  - `contexto?`      linha cinza abaixo do título (ex.: "Proposta v2 · Aurora")
 *  - `assuntoInicial?`
 *  - `vinculo?`       campos extras no topo (ex.: empresa/oportunidade em Comunicações)
 *  - `aoEnviar?`      chamado após o envio (as queries do módulo já são invalidadas aqui)
 *
 * O botão Enviar segue `GET /auth/me/envio` ("Enviar como …"); sem e-mail de envio, leva a Minha conta.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Send } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api } from "@/lib/api";
import type { ModeloComunicacao, PreviaModelo } from "@/lib/tipos-comercial";
import type { Pessoa } from "@/lib/tipos-nucleo";
import type { EnvioEmailIn, EnvioEmailOut, Pagina, StatusEnvio } from "@/lib/types";
import { cn } from "@/lib/utils";

import { CampoDrawer, Drawer } from "./drawer";
import { EmailChips, emailsValidos } from "./email-chips";
import { Etiqueta } from "./etiqueta";
import { NativeSelect } from "./form";
import { notificar } from "./toast";

export type DestinoEmail = { tipo: "comunicacao" } | { tipo: "proposta"; id: number } | { tipo: "cobranca"; id: number };

const MAX_DESTINATARIOS = 20;

const ROTULO_REGISTRO: Record<DestinoEmail["tipo"], string> = {
  comunicacao: "A mensagem vira uma comunicação de e-mail vinculada.",
  proposta: "A mensagem fica registrada na oportunidade da proposta.",
  cobranca: "A mensagem entra no histórico da cobrança.",
};

interface Contato {
  pessoaId: number;
  nome: string;
  email: string;
  optOut: boolean;
}

function contatosDe(pessoas: Pessoa[]): Contato[] {
  const lista: Contato[] = [];
  for (const p of pessoas) {
    const optOut = (p.permissoes_comunicacao ?? []).includes("opt_out");
    const emails = p.emails?.length
      ? [...p.emails].sort((a, b) => Number(b.principal) - Number(a.principal)).map((e) => e.email)
      : p.email
        ? [p.email]
        : [];
    for (const e of new Set(emails.map((x) => x.trim().toLowerCase()).filter(Boolean))) {
      lista.push({ pessoaId: p.id, nome: p.nome, email: e, optOut });
    }
  }
  return lista;
}

export function EnviarEmailDrawer({
  aberto,
  onFechar,
  destino,
  empresaId,
  oportunidadeId,
  modelos,
  contexto,
  assuntoInicial,
  vinculo,
  aoEnviar,
}: {
  aberto: boolean;
  onFechar: () => void;
  destino: DestinoEmail;
  empresaId?: number | null;
  oportunidadeId?: number | null;
  modelos: "comercial" | "financeiro";
  contexto?: string;
  assuntoInicial?: string;
  vinculo?: React.ReactNode;
  aoEnviar?: (r: EnvioEmailOut) => void;
}) {
  const chave = `${destino.tipo}-${"id" in destino ? destino.id : "novo"}`;
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      rotulo="E-MAIL / ENVIO"
      titulo="Enviar e-mail"
      descricao={contexto}
      largura={560}
    >
      {aberto && (
        <Corpo
          key={chave}
          destino={destino}
          empresaId={empresaId ?? null}
          oportunidadeId={oportunidadeId ?? null}
          modelos={modelos}
          assuntoInicial={assuntoInicial ?? ""}
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
  assuntoInicial,
  vinculo,
  onFechar,
  aoEnviar,
}: {
  destino: DestinoEmail;
  empresaId: number | null;
  oportunidadeId: number | null;
  modelos: "comercial" | "financeiro";
  assuntoInicial: string;
  vinculo?: React.ReactNode;
  onFechar: () => void;
  aoEnviar?: (r: EnvioEmailOut) => void;
}) {
  const qc = useQueryClient();
  const [para, setPara] = useState<string[]>([]);
  const [cc, setCc] = useState<string[]>([]);
  const [modeloId, setModeloId] = useState("");
  const [assunto, setAssunto] = useState(assuntoInicial);
  const [corpo, setCorpo] = useState("");
  const [faltando, setFaltando] = useState<string[]>([]);
  const [anexarPdf, setAnexarPdf] = useState(true);

  const status = useQuery({
    queryKey: ["auth", "me", "envio"],
    queryFn: () => api.get<StatusEnvio>("/auth/me/envio"),
    retry: false,
    meta: { silencioso: true },
  });

  const pessoas = useQuery({
    queryKey: ["nucleo", "pessoas", "envio", empresaId],
    queryFn: () => api.get<Pagina<Pessoa>>("/nucleo/pessoas", { empresa_id: empresaId ?? undefined, por_pagina: 200 }),
    enabled: empresaId != null,
    retry: false,
    meta: { silencioso: true },
  });
  const contatos = useMemo(() => contatosDe(pessoas.data?.itens ?? []), [pessoas.data]);
  const optOut = useMemo(() => new Map(contatos.filter((c) => c.optOut).map((c) => [c.email, c.nome])), [contatos]);

  const listaModelos = useQuery({
    queryKey: ["modelos-envio", modelos],
    queryFn: () =>
      modelos === "financeiro"
        ? api.get<ModeloComunicacao[]>("/financeiro/cobrancas/modelos", { canal: "email" })
        : api.get<ModeloComunicacao[]>("/comercial/modelos", { contexto: "comercial", canal: "email" }),
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
      if (p.assunto) setAssunto(p.assunto);
      setCorpo(p.conteudo);
      setFaltando(p.faltando);
    },
    onError: (_e, m) => {
      // sem prévia: usa o texto do modelo com as variáveis à vista
      if (m.assunto) setAssunto(m.assunto);
      setCorpo(m.conteudo);
      setFaltando(m.variaveis);
      notificar("Não foi possível preencher o modelo. As variáveis ficaram no texto para você revisar.");
    },
  });

  const enviar = useMutation({
    mutationFn: () => {
      const base: EnvioEmailIn = { para, cc, assunto: assunto.trim(), corpo, modelo_id: modeloId ? Number(modeloId) : null };
      if (destino.tipo === "comunicacao") {
        return api.post<EnvioEmailOut>("/comercial/comunicacoes/enviar-email", { ...base, empresa_id: empresaId, oportunidade_id: oportunidadeId });
      }
      if (destino.tipo === "proposta") {
        return api.post<EnvioEmailOut>(`/comercial/propostas/${destino.id}/enviar-email`, { ...base, anexar_pdf: anexarPdf });
      }
      return api.post<EnvioEmailOut>(`/financeiro/cobrancas/${destino.id}/enviar-email`, base);
    },
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: [destino.tipo === "cobranca" ? "financeiro" : "comercial"] });
      notificar.sucesso(`E-mail enviado para ${r.enviado_para.join(", ")}`);
      if (r.registro) notificar.info(r.registro);
      aoEnviar?.(r);
      onFechar();
    },
  });

  const bloqueados = [...para, ...cc].filter((e) => optOut.has(e));
  const podeEnviar = status.data?.pode_enviar === true;

  function adicionar(c: Contato, campo: "para" | "cc") {
    if (c.optOut) return;
    if (campo === "para") {
      setPara((v) => (v.includes(c.email) ? v : [...v, c.email]));
      setCc((v) => v.filter((x) => x !== c.email));
    } else {
      setCc((v) => (v.includes(c.email) ? v : [...v, c.email]));
      setPara((v) => v.filter((x) => x !== c.email));
    }
  }

  function escolherModelo(id: string) {
    setModeloId(id);
    setFaltando([]);
    const m = (listaModelos.data ?? []).find((x) => String(x.id) === id);
    if (m) previa.mutate(m);
  }

  function validar(): string | null {
    if (!para.length) return "Informe ao menos um destinatário em Para.";
    if (!emailsValidos(para) || !emailsValidos(cc)) return "Há e-mail inválido nos destinatários.";
    if (para.length + cc.length > MAX_DESTINATARIOS) return `No máximo ${MAX_DESTINATARIOS} destinatários por envio.`;
    if (bloqueados.length) return `${optOut.get(bloqueados[0])} pediu para não receber comunicações (opt-out).`;
    if (!assunto.trim()) return "Informe o assunto.";
    if (!corpo.trim()) return "Escreva a mensagem.";
    return null;
  }

  return (
    <form
      id="f-enviar-email"
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

      <CampoDrawer rotulo="Para" obrigatorio>
        <EmailChips value={para} onChange={setPara} />
      </CampoDrawer>
      <CampoDrawer rotulo="Cc">
        <EmailChips value={cc} onChange={setCc} placeholder="Cópia (opcional)" />
      </CampoDrawer>
      {bloqueados.length > 0 && (
        <p className="mt-2 rounded-[8px] bg-amber/15 p-2.5 text-xs text-amber-ink">
          Opt-out: {bloqueados.map((e) => optOut.get(e)).join(", ")} pediu para não receber comunicações. Remova antes de enviar.
        </p>
      )}

      {empresaId != null && (
        <div className="mt-3">
          <span className="eyebrow">PESSOAS DA EMPRESA</span>
          {pessoas.isPending ? (
            <p className="mt-2 text-xs text-muted">Carregando contatos…</p>
          ) : contatos.length === 0 ? (
            <p className="mt-2 text-xs text-muted">Nenhuma pessoa com e-mail nesta empresa.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line rounded-[8px] border border-line">
              {contatos.map((c) => {
                const emPara = para.includes(c.email);
                const emCc = cc.includes(c.email);
                return (
                  <li key={`${c.pessoaId}-${c.email}`} className={cn("flex items-center justify-between gap-2 px-3 py-2 text-sm", c.optOut && "opacity-60")}>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{c.nome}</p>
                      <p className="truncate text-xs text-muted">{c.email}</p>
                    </div>
                    {c.optOut ? (
                      <Etiqueta tom="amber">Opt-out</Etiqueta>
                    ) : (
                      <div className="flex shrink-0 gap-1">
                        <Button type="button" size="sm" variant={emPara ? "secondary" : "outline"} disabled={emPara} onClick={() => adicionar(c, "para")}>
                          Para
                        </Button>
                        <Button type="button" size="sm" variant={emCc ? "secondary" : "outline"} disabled={emCc} onClick={() => adicionar(c, "cc")}>
                          Cc
                        </Button>
                      </div>
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
        dica={
          listaModelos.isError
            ? "Modelos indisponíveis no momento. Escreva a mensagem abaixo."
            : modelos === "financeiro"
              ? "Modelos financeiros e gerais. O texto fica editável."
              : "Modelos comerciais e gerais. O texto fica editável."
        }
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

      <CampoDrawer rotulo="Assunto" obrigatorio>
        <Input value={assunto} onChange={(e) => setAssunto(e.target.value)} maxLength={200} />
      </CampoDrawer>
      <CampoDrawer rotulo="Mensagem" obrigatorio dica="Sua assinatura é acrescentada no fim.">
        <Textarea rows={10} value={corpo} onChange={(e) => setCorpo(e.target.value)} />
      </CampoDrawer>

      {destino.tipo === "proposta" && (
        <label className="mt-4 flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4 accent-primary" checked={anexarPdf} onChange={(e) => setAnexarPdf(e.target.checked)} />
          Anexar o PDF da proposta (se houver)
        </label>
      )}

      <div className="mt-5 rounded-[10px] border border-line bg-subtle p-3 text-xs">
        {status.isPending ? (
          <p className="text-muted">Conferindo o e-mail de envio…</p>
        ) : status.isError ? (
          <p className="text-amber-ink">Envio por e-mail ainda indisponível no servidor.</p>
        ) : podeEnviar ? (
          <p>
            Enviar como <strong>{status.data?.remetente ?? "e-mail da organização"}</strong>
            {status.data?.via === "outbox" && <span className="text-muted"> · ambiente de teste: a mensagem fica na caixa de saída</span>}
          </p>
        ) : (
          <p className="text-amber-ink">
            Nenhum e-mail de envio configurado.{" "}
            <Link href="/minha-conta" className="font-medium text-primary underline">
              Configurar em Minha conta
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
