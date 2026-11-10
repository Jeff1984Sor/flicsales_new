"use client";

/**
 * OportunidadeDrawer — detalhe da oportunidade no painel lateral (protótipo `detail` + extensão "Gestão da oportunidade").
 *
 * Props:
 *  - `id: number | null`      oportunidade aberta (null = fechado)
 *  - `onFechar: () => void`
 *
 * Etapa (inclui Ganha → "Revisar fechamento" e Perdida → motivo), Contexto da negociação com fonte e limite,
 * Analisar registro (IA unificada, escopo "Este registro"), Histórico compartilhado, nota, recebíveis de origem.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { abrirAssistente } from "@/components/flic/eventos";
import { NativeSelect } from "@/components/flic/form";
import { Fonte } from "@/components/flic/fonte";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, dataHora } from "@/lib/format";
import type { Evento, Oportunidade, OportunidadeDetalhe } from "@/lib/tipos-comercial";

import { CHAVE, useInvalidarComercial, useOpcoes } from "./dados";
import { GanhoDrawer, PerdaDrawer } from "./ganho-perda";
import { OportunidadeForm } from "./oportunidade-form";

const ROTULO_EVENTO: Record<Evento["tipo"], string> = {
  criada: "Criada",
  etapa: "Etapa",
  ganha: "Ganha",
  perdida: "Perdida",
  reaberta: "Reaberta",
  proxima_acao: "Próxima ação",
  proposta: "Proposta",
  reuniao: "Reunião vinculada",
  nota: "Nota",
};

export function OportunidadeDrawer({ id, onFechar }: { id: number | null; onFechar: () => void }) {
  const { pode } = useAuth();
  const editar = pode("comercial.oportunidades.editar");
  const invalidar = useInvalidarComercial();
  const { data: opcoes } = useOpcoes();
  const [ganho, setGanho] = useState(false);
  const [perda, setPerda] = useState(false);
  const [edicao, setEdicao] = useState(false);
  const [nota, setNota] = useState("");

  const { data: o, isPending } = useQuery({
    queryKey: [CHAVE, "oportunidade", id],
    queryFn: () => api.get<OportunidadeDetalhe>(`/comercial/oportunidades/${id}`),
    enabled: id != null,
  });
  const { data: historico } = useQuery({
    queryKey: [CHAVE, "oportunidade", id, "historico"],
    queryFn: () => api.get<Evento[]>(`/comercial/oportunidades/${id}/historico`),
    enabled: id != null,
  });

  const mover = useMutation({
    mutationFn: (etapaId: number) => api.post<Oportunidade>(`/comercial/oportunidades/${id}/mover`, { etapa_id: etapaId }),
    onSuccess: (r) => {
      invalidar();
      notificar(`Movida para ${r.etapa_nome}`);
    },
  });
  const reabrir = useMutation({
    mutationFn: () => api.post<Oportunidade>(`/comercial/oportunidades/${id}/reabrir`),
    onSuccess: () => {
      invalidar();
      notificar("Oportunidade reaberta");
    },
  });
  const anotar = useMutation({
    mutationFn: () => api.post<Evento>(`/comercial/oportunidades/${id}/notas`, { texto: nota.trim() }),
    onSuccess: () => {
      setNota("");
      invalidar();
      notificar("Nota registrada no histórico");
    },
  });

  const etapas = opcoes?.funis.find((f) => f.id === o?.funil_id)?.etapas ?? [];
  const valorSelect = o ? (o.resultado === "aberta" ? String(o.etapa_id ?? "") : o.resultado) : "";

  function trocarEtapa(v: string) {
    if (!o) return;
    if (v === "ganha") setGanho(true);
    else if (v === "perdida") setPerda(true);
    else if (v && Number(v) !== o.etapa_id) mover.mutate(Number(v));
  }

  const rotulo = o ? `OPORTUNIDADE / ${(o.resultado === "aberta" ? (o.etapa_nome ?? "Aberta") : o.resultado === "ganha" ? "Ganha" : "Perdida").toUpperCase()}` : undefined;

  return (
    <>
      <Drawer aberto={id != null} onFechar={onFechar} rotulo={rotulo} titulo={o?.titulo} descricao={o ? `${o.empresa_nome ?? "Empresa a definir"} · ${o.responsavel_nome ?? ""}` : undefined}>
        {isPending || !o ? (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <>
            <Metricas colunas={2} className="mt-0 min-[1100px]:grid-cols-2">
              <KpiCard rotulo="Valor único" valor={<Dinheiro valor={o.valor_unico} />} detalhe="Receita potencial" />
              <KpiCard rotulo="Interesse" valor={o.interesse ?? "—"} detalhe="Campo personalizado" />
            </Metricas>

            <label className="mb-[7px] block text-xs" htmlFor="op-etapa">
              Etapa
            </label>
            <NativeSelect id="op-etapa" value={valorSelect} onChange={(e) => trocarEtapa(e.target.value)} disabled={!editar || o.resultado !== "aberta" || mover.isPending}>
              {etapas.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.nome}
                </option>
              ))}
              <option value="ganha">Ganha</option>
              <option value="perdida">Perdida</option>
            </NativeSelect>
            {o.alem_do_limite && (
              <p className="mt-2 text-xs text-amber-ink">
                Há {o.dias_na_etapa} dias nesta etapa, além do limite configurado.
              </p>
            )}

            <div className="mt-5 rounded-[8px] border border-electric/20 bg-electric/5 p-4">
              <h3 className="text-sm font-bold">✧ Contexto da negociação</h3>
              <p className="mt-2 text-sm leading-relaxed">{o.contexto.texto}</p>
              <Fonte fonte={o.contexto.fonte ?? undefined} limite={o.contexto.limite} />
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => abrirAssistente("Este registro", { tipo: "oportunidade", id: o.id, rotulo: `${o.empresa_nome ?? ""} · ${o.titulo}` })}>
                ✧ Analisar registro
              </Button>
              {o.resultado === "aberta" && editar && <Button onClick={() => setGanho(true)}>Marcar como ganha</Button>}
              {o.resultado === "ganha" && <Etiqueta tom="green">Venda ganha • revisar financeiro</Etiqueta>}
              {o.resultado === "perdida" && (
                <>
                  <Etiqueta tom="amber">Perdida</Etiqueta>
                  {editar && (
                    <Button variant="outline" onClick={() => reabrir.mutate()} disabled={reabrir.isPending}>
                      Reabrir
                    </Button>
                  )}
                </>
              )}
            </div>

            {o.resultado === "perdida" && (
              <Fonte className="mt-4">
                <p>Motivo: {o.motivo_perda}</p>
                {o.concorrente && <p>Concorrente: {o.concorrente}</p>}
                {o.data_retomada && <p>Possível retomada: {data(o.data_retomada)}</p>}
              </Fonte>
            )}

            {o.recebiveis.length > 0 && (
              <section className="mt-6">
                <h3 className="text-sm font-bold">Recebíveis de origem</h3>
                <ul className="mt-2 divide-y divide-line text-sm">
                  {o.recebiveis.map((t) => (
                    <li key={t.id} className="flex items-center justify-between gap-2 py-2">
                      <span>
                        {t.descricao}
                        <span className="block text-xs text-muted">Vence {data(t.vencimento)}</span>
                      </span>
                      <span className="text-right">
                        <Dinheiro valor={t.valor_original} />
                        <Etiqueta className="ml-2" tom={t.status === "rascunho" ? "amber" : "neutra"}>
                          {t.status === "rascunho" ? "Rascunho" : t.status}
                        </Etiqueta>
                      </span>
                    </li>
                  ))}
                </ul>
                <Button variant="link" className="px-0" render={<Link href="/financeiro/receber" />}>
                  Revisar no Financeiro › A receber
                </Button>
              </section>
            )}

            <section className="card-surface mt-6 p-4">
              <h3 className="text-sm font-bold">Gestão da oportunidade</h3>
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                <dt className="text-muted">Funil</dt>
                <dd>{o.funil_nome}</dd>
                <dt className="text-muted">Contato</dt>
                <dd>{o.contato_nome ?? "Não informado"}</dd>
                <dt className="text-muted">Recorrência mensal</dt>
                <dd>
                  <Dinheiro valor={o.valor_recorrente_mensal} />
                </dd>
                <dt className="text-muted">Previsão</dt>
                <dd>{o.previsao_fechamento ? data(o.previsao_fechamento) : "Não definida"}</dd>
                <dt className="text-muted">Próxima ação</dt>
                <dd>
                  {o.proxima_acao ?? "Não definida"}
                  {o.proxima_acao_prazo && <span className="text-muted"> · até {data(o.proxima_acao_prazo)}</span>}
                </dd>
                <dt className="text-muted">Vínculos</dt>
                <dd>
                  {o.atividades_pendentes} atividade(s) pendente(s) · {o.comunicacoes} comunicação(ões) · {o.propostas} proposta(s)
                </dd>
              </dl>
              {editar && (
                <Button variant="outline" className="mt-3" onClick={() => setEdicao(true)}>
                  Atualizar etapa e próxima ação
                </Button>
              )}
            </section>

            <h3 className="mt-6 text-sm font-bold">Histórico compartilhado</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {(historico ?? []).map((e) => (
                <li key={e.id} className="border-l-2 border-line pl-3">
                  <span className="text-xs text-muted">
                    {dataHora(e.quando)} · {ROTULO_EVENTO[e.tipo] ?? e.tipo}
                    {e.usuario_nome ? ` · ${e.usuario_nome}` : ""}
                  </span>
                  <p>{e.texto}</p>
                </li>
              ))}
              {historico?.length === 0 && <li className="text-muted">Sem eventos ainda.</li>}
            </ul>
            {editar && (
              <form
                className="mt-3 flex flex-col gap-2"
                onSubmit={(ev) => {
                  ev.preventDefault();
                  if (nota.trim()) anotar.mutate();
                }}
              >
                <Textarea value={nota} onChange={(ev) => setNota(ev.target.value)} placeholder="Registrar uma nota no histórico" aria-label="Nota" />
                <Button type="submit" variant="outline" size="sm" className="self-start" disabled={!nota.trim() || anotar.isPending}>
                  Registrar nota
                </Button>
              </form>
            )}
          </>
        )}
      </Drawer>
      <GanhoDrawer oportunidade={o ?? null} aberto={ganho} onFechar={() => setGanho(false)} />
      <PerdaDrawer oportunidade={o ?? null} aberto={perda} onFechar={() => setPerda(false)} />
      <OportunidadeForm aberto={edicao} onFechar={() => setEdicao(false)} oportunidade={o ?? null} />
    </>
  );
}
