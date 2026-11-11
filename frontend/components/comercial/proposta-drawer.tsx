"use client";

/**
 * PropostaDrawer — documento da proposta no painel lateral (usado em Propostas e no drawer da Oportunidade).
 *
 * Props:
 *  - `proposta: Proposta | null`            proposta aberta (null = fechado)
 *  - `onTrocar: (p: Proposta | null) => void` fecha (null) ou troca a proposta aberta (ex.: nova versão duplicada)
 *
 * Comandos: Baixar PDF (todos que veem), Editar, Duplicar, ✉ Enviar e-mail e WhatsApp (permissão de editar;
 * WhatsApp só com a Evolution conectada — `GET /auth/me/envio` → `whatsapp.pode_enviar`).
 */
import { useMutation } from "@tanstack/react-query";
import { FileDown } from "lucide-react";
import { useState } from "react";

import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { EnviarEmailDrawer } from "@/components/flic/enviar-email";
import { EnviarWhatsAppDrawer, usePodeWhatsApp } from "@/components/flic/enviar-whatsapp";
import { Etiqueta, type TomEtiqueta } from "@/components/flic/etiqueta";
import { notificar } from "@/components/flic/toast";
import { Button, buttonVariants } from "@/components/ui/button";
import { API_URL, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, decimal, moeda } from "@/lib/format";
import { type Proposta, STATUS_PROPOSTA } from "@/lib/tipos-comercial";

import { useInvalidarComercial } from "./dados";
import { PropostaForm } from "./proposta-form";

export const rotuloStatusProposta = (s: string) => STATUS_PROPOSTA.find((x) => x.valor === s)?.rotulo ?? s;
export const tomStatusProposta = (s: string): TomEtiqueta =>
  s === "aceita" ? "green" : s === "recusada" ? "amber" : s === "aprovada_internamente" || s === "enviada" ? "azul" : "neutra";

/** Endereço do PDF pelo BFF (abre em nova aba; a sessão vai no cookie). */
export const urlPdfProposta = (id: number) => `${API_URL}/comercial/propostas/${id}/pdf`;

export function PropostaDrawer({ proposta, onTrocar }: { proposta: Proposta | null; onTrocar: (p: Proposta | null) => void }) {
  const { pode } = useAuth();
  const editar = pode("comercial.propostas.editar");
  const podeWhats = usePodeWhatsApp();
  const invalidar = useInvalidarComercial();
  const [edicao, setEdicao] = useState<Proposta | null>(null);
  const [email, setEmail] = useState<Proposta | null>(null);
  const [whats, setWhats] = useState<Proposta | null>(null);

  const duplicar = useMutation({
    mutationFn: (p: Proposta) => api.post<Proposta>(`/comercial/propostas/${p.id}/duplicar`),
    onSuccess: (p) => {
      invalidar();
      onTrocar(p);
      notificar(`Versão ${p.versao} criada em rascunho`);
    },
  });

  const doc = proposta;
  const rascunho = doc ? doc.status === "rascunho" || (doc.status === "em_aprovacao" && Number(doc.desconto_pct) > 0) : false;

  return (
    <>
      <Drawer
        aberto={!!doc}
        onFechar={() => onTrocar(null)}
        rotulo={doc ? `PROPOSTA / VERSÃO ${doc.versao}` : undefined}
        titulo={doc?.titulo}
        descricao={doc ? `${doc.empresa_nome ?? "—"} · ${doc.responsavel_nome ?? "—"}` : undefined}
      >
        {doc && (
          <>
            <div className="rounded-[10px] border border-line bg-subtle p-5">
              <h3 className="text-sm font-bold">Escopo</h3>
              <p className="mt-2 text-sm whitespace-pre-wrap">{doc.escopo}</p>
              <p className="mt-4 text-sm">
                <span className="num">{decimal(doc.quantidade)}</span> × {moeda(doc.preco_unitario)} · desconto <span className="num">{decimal(doc.desconto_pct)}%</span>
              </p>
              <h2 className="mt-3 text-[29px] font-bold">
                <Dinheiro valor={doc.total} />
              </h2>
              <p className="mt-2 text-sm leading-relaxed">
                Mensalidade adicional: <Dinheiro valor={doc.mensalidade_adicional} />
                <br />
                Condição: {doc.condicao}
                <br />
                Validade: {data(doc.validade)}
              </p>
              {Number(doc.desconto_pct) > 0 && (
                <p className="mt-3 text-xs text-muted">
                  Justificativa do desconto: {doc.justificativa_desconto ?? "—"}. Desconto passa por aprovação interna antes do envio.
                </p>
              )}
            </div>
            <div className="mt-4">
              <Etiqueta tom={tomStatusProposta(doc.status)}>{rotuloStatusProposta(doc.status)}</Etiqueta>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <a href={urlPdfProposta(doc.id)} target="_blank" rel="noopener noreferrer" className={buttonVariants({ variant: "outline" })}>
                <FileDown />
                Baixar PDF
              </a>
              {editar && (
                <>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setEdicao(doc);
                      onTrocar(null);
                    }}
                  >
                    Editar proposta
                  </Button>
                  <Button variant="outline" disabled={duplicar.isPending} onClick={() => duplicar.mutate(doc)}>
                    Duplicar (nova versão)
                  </Button>
                  <Button variant="outline" onClick={() => setEmail(doc)}>
                    ✉ Enviar e-mail
                  </Button>
                  {podeWhats && (
                    <Button variant="outline" onClick={() => setWhats(doc)}>
                      WhatsApp
                    </Button>
                  )}
                </>
              )}
            </div>
            {rascunho && <p className="mt-3 text-xs text-amber-ink">Em rascunho o PDF sai com a faixa “RASCUNHO — não enviar”.</p>}
            <p className="mt-4 text-xs text-muted">O envio por e-mail ou WhatsApp fica registrado na oportunidade. Assinatura e aceite externo não estão disponíveis.</p>
          </>
        )}
      </Drawer>

      <PropostaForm aberto={!!edicao} proposta={edicao} onFechar={() => setEdicao(null)} />

      <EnviarEmailDrawer
        aberto={!!email}
        onFechar={() => setEmail(null)}
        destino={{ tipo: "proposta", id: email?.id ?? 0 }}
        empresaId={email?.empresa_id}
        oportunidadeId={email?.oportunidade_id}
        modelos="comercial"
        contexto={email ? `${email.titulo} · v${email.versao}${email.empresa_nome ? ` · ${email.empresa_nome}` : ""}` : undefined}
        assuntoInicial={email ? `Proposta: ${email.titulo}` : undefined}
        aoEnviar={() => onTrocar(null)}
      />

      <EnviarWhatsAppDrawer
        aberto={!!whats}
        onFechar={() => setWhats(null)}
        destino={{ tipo: "proposta", id: whats?.id ?? 0 }}
        empresaId={whats?.empresa_id}
        oportunidadeId={whats?.oportunidade_id}
        modelos="comercial"
        contexto={whats ? `${whats.titulo} · v${whats.versao}${whats.empresa_nome ? ` · ${whats.empresa_nome}` : ""}` : undefined}
        textoInicial={whats ? `Olá! Segue a proposta “${whats.titulo}”.` : undefined}
        aoEnviar={() => onTrocar(null)}
      />
    </>
  );
}
