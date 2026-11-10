"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AtividadeForm } from "@/components/comercial/atividade-form";
import { CHAVE, hora, useInvalidarComercial } from "@/components/comercial/dados";
import { NovoFunilDrawer } from "@/components/comercial/funil-drawers";
import { OportunidadeDrawer } from "@/components/comercial/oportunidade-drawer";
import { OportunidadeForm } from "@/components/comercial/oportunidade-form";
import { PropostaForm } from "@/components/comercial/proposta-form";
import { AcessoRapido } from "@/components/flic/acesso-rapido";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Etiqueta } from "@/components/flic/etiqueta";
import { abrirAssistente, useAtalhoNovo } from "@/components/flic/eventos";
import { Fonte } from "@/components/flic/fonte";
import { Insight } from "@/components/flic/insight";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { PageHeader } from "@/components/flic/page-header";
import { GradePaineis, Painel } from "@/components/flic/painel";
import { Passos } from "@/components/flic/passos";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, numero } from "@/lib/format";
import { type Atividade, type Hoje, rotuloTipoAtividade } from "@/lib/tipos-comercial";
import { cn } from "@/lib/utils";

const CORES_FUNIL = ["bg-subtle", "bg-electric", "bg-primary", "bg-ink", "bg-accent", "bg-electric/60"];

function saudacao() {
  const h = Number(new Intl.DateTimeFormat("pt-BR", { hour: "numeric", hour12: false, timeZone: "America/Sao_Paulo" }).format(new Date()));
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

function quando(a: Atividade, hojeIso: string) {
  const dia = a.prazo === hojeIso ? "Hoje" : a.atrasada ? `Atrasada desde ${data(a.prazo)}` : data(a.prazo);
  return `${dia}${a.hora_inicio ? `, ${hora(a.hora_inicio)}` : ""}`;
}

export default function ComercialHojePage() {
  const router = useRouter();
  const { pode, usuario } = useAuth();
  const invalidar = useInvalidarComercial();
  const [novaOp, setNovaOp] = useState(false);
  const [novaAtividade, setNovaAtividade] = useState(false);
  const [novaProposta, setNovaProposta] = useState(false);
  const [novoFunil, setNovoFunil] = useState(false);
  const [aberta, setAberta] = useState<number | null>(null);
  const [atividade, setAtividade] = useState<Atividade | null>(null);
  const podeOp = pode("comercial.oportunidades.editar");
  useAtalhoNovo(() => podeOp && setNovaOp(true));

  const { data: h, isPending } = useQuery({ queryKey: [CHAVE, "hoje"], queryFn: () => api.get<Hoje>("/comercial/hoje") });

  const concluir = useMutation({
    mutationFn: (a: Atividade) => api.post<Atividade>(`/comercial/atividades/${a.id}/concluir`, {}),
    onSuccess: (a) => {
      invalidar();
      notificar(`Concluída: ${a.assunto}`);
    },
  });

  function entenderEAgir() {
    const acao = h?.leitura.acoes_sugeridas[0];
    const reg = acao?.registro ?? h?.leitura.evidencias[0]?.registro;
    if (!reg) {
      abrirAssistente("Este módulo");
      return;
    }
    if (reg.tipo === "oportunidade") setAberta(reg.id);
    else if (reg.tipo === "atividade") {
      const a = [...(h?.atencao ?? []), ...(h?.agenda ?? [])].find((x) => x.id === reg.id);
      if (a) setAtividade(a);
      else router.push("/comercial/atividades");
    } else if (reg.tipo === "titulo") router.push("/financeiro/receber");
    else abrirAssistente("Este módulo");
  }

  const primeiroNome = (h?.nome ?? usuario?.nome ?? "").split(" ")[0];
  const totalFunil = (h?.saude_funil ?? []).reduce((s, e) => s + e.quantidade, 0);

  return (
    <>
      <AcessoRapido
        itens={[
          ...(podeOp ? [{ rotulo: "+ Oportunidade", onClick: () => setNovaOp(true) }] : []),
          ...(pode("comercial.atividades.editar") ? [{ rotulo: "+ Atividade", onClick: () => setNovaAtividade(true) }] : []),
          ...(pode("comercial.propostas.editar") ? [{ rotulo: "+ Proposta", onClick: () => setNovaProposta(true) }] : []),
          ...(pode("nucleo.cadastros.editar") ? [{ rotulo: "+ Empresa", href: "/comercial/empresas" }] : []),
          ...(podeOp ? [{ rotulo: "+ Criar funil", onClick: () => setNovoFunil(true) }] : []),
        ]}
      />
      <PageHeader
        titulo="Seu dia, em perspectiva."
        descricao={`${saudacao()}${primeiroNome ? `, ${primeiroNome}` : ""}. Seu próximo movimento começa aqui.`}
        acao={podeOp ? <Button onClick={() => setNovaOp(true)}>+ Oportunidade</Button> : undefined}
      />

      {isPending || !h ? (
        <Skeleton className="mb-[25px] h-28 w-full rounded-[10px]" />
      ) : (
        <Insight
          titulo={h.leitura.titulo}
          texto={
            <>
              {h.leitura.analise}
              {h.leitura.proxima_acao && (
                <>
                  {" "}
                  <strong className="text-ink">Próxima ação sugerida:</strong> {h.leitura.proxima_acao}.
                </>
              )}
            </>
          }
          iaDesligada={!h.ia_ligada}
          acao={{ rotulo: "Entender e agir", onClick: entenderEAgir }}
        >
          <Fonte
            evidencia={h.leitura.evidencias.slice(0, 3).map((e) => e.texto ?? e.trecho ?? "")}
            fonte={h.leitura.evidencias.slice(0, 3).map((e) => e.fonte)}
            limite={h.leitura.limites}
          />
        </Insight>
      )}

      <Metricas>
        <KpiCard
          rotulo="Pipeline aberto"
          carregando={isPending}
          valor={<Dinheiro valor={h?.pipeline_aberto} />}
          detalhe={`${numero(h?.oportunidades_ativas)} oportunidades ativas`}
          formula="Σ valor único das oportunidades abertas"
        />
        <KpiCard
          rotulo="Em negociação"
          carregando={isPending}
          valor={<Dinheiro valor={h?.em_negociacao} />}
          detalhe={h?.em_negociacao_qtd ? `${h.em_negociacao_qtd} em ${h.em_negociacao_etapa}` : "Confirmar escopo e próximo passo"}
          formula="Σ valor único das abertas na última etapa do funil"
        />
        <KpiCard rotulo="Tarefas do dia" carregando={isPending} valor={numero(h?.tarefas_do_dia)} detalhe="Prioridades com responsável" formula="Atividades pendentes com prazo até hoje" />
        <KpiCard
          rotulo="Recebíveis vinculados"
          carregando={isPending}
          valor={numero(h?.recebiveis_vinculados)}
          detalhe="Vendas ≠ recebimentos"
          formula="Títulos a receber com origem em oportunidade (não compõem o caixa)"
        />
      </Metricas>

      <GradePaineis>
        <div>
          <Painel titulo="O que merece sua atenção" acao={<Etiqueta tom="green">Próximas ações</Etiqueta>}>
            {(h?.atencao ?? []).map((a) => (
              <div key={a.id} className="flex items-center gap-3 border-b border-line py-3 last:border-0">
                <span className={cn("size-2 shrink-0 rounded-full", a.atrasada ? "bg-amber" : "bg-accent")} aria-hidden />
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => (a.oportunidade_id ? setAberta(a.oportunidade_id) : setAtividade(a))}>
                  <strong className="block truncate">{a.assunto}</strong>
                  <p className={cn("text-xs", a.atrasada ? "text-amber-ink" : "text-muted")}>
                    {a.responsavel_nome} · {quando(a, h?.hoje ?? "")} · {rotuloTipoAtividade(a.tipo)}
                    {a.empresa_nome ? ` · ${a.empresa_nome}` : ""}
                  </p>
                </button>
                {pode("comercial.atividades.editar") && (
                  <Button variant="outline" size="sm" onClick={() => concluir.mutate(a)} disabled={concluir.isPending}>
                    Concluir
                  </Button>
                )}
              </div>
            ))}
            {h && h.atencao.length === 0 && <p className="text-muted">Tudo em dia.</p>}
          </Painel>
          <Painel
            titulo="Do negócio ao recebimento"
            acao={
              <Button variant="outline" size="sm" render={<Link href="/comercial/oportunidades" />}>
                Explorar fluxo
              </Button>
            }
          >
            <Passos passos={["Oportunidade", "Condição comercial", "Recebível em rascunho", "Recebimento"]} />
            <p className="text-sm text-muted">Dados reaproveitados. Cada transição mantém origem, responsável e histórico.</p>
          </Painel>
        </div>
        <div>
          <Painel titulo="Agenda conectada" acao={!h?.agenda_conectada ? <Etiqueta>Prévia • sem conexão</Etiqueta> : <Etiqueta tom="green">Conectada</Etiqueta>}>
            {(h?.agenda ?? []).map((a) => (
              <div key={a.id} className="grid grid-cols-[52px_1fr] gap-3 border-b border-line py-3 last:border-0">
                <time className="num text-sm font-semibold text-primary">{a.hora_inicio ? hora(a.hora_inicio) : "—"}</time>
                <div>
                  <strong>{a.assunto}</strong>
                  <p className="text-xs text-muted">
                    {a.responsavel_nome} · {rotuloTipoAtividade(a.tipo)}
                    {a.hora_fim && a.hora_inicio ? ` · até ${hora(a.hora_fim)}` : ""}
                  </p>
                </div>
              </div>
            ))}
            {h && h.agenda.length === 0 && <p className="text-muted">Nenhum compromisso para hoje.</p>}
            <p className="mt-3 text-xs text-muted">Agenda vem das atividades registradas. Google Calendar e Outlook dependem de conexão autorizada.</p>
            <Button variant="outline" size="sm" className="mt-3" render={<Link href="/comercial/atividades" />}>
              Ver atividades
            </Button>
          </Painel>
          <Painel titulo="Saúde da operação">
            <p className="text-sm">{h?.funil_nome ? `${h.funil_nome} · Comercial → Financeiro` : "Comercial → Financeiro"}</p>
            <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-subtle" role="img" aria-label="Oportunidades abertas por etapa">
              {(h?.saude_funil ?? []).map((e, i) =>
                e.quantidade > 0 ? <div key={e.etapa_id} className={CORES_FUNIL[i % CORES_FUNIL.length]} style={{ flex: e.quantidade }} title={`${e.etapa}: ${e.quantidade}`} /> : null,
              )}
            </div>
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              {(h?.saude_funil ?? []).map((e, i) => (
                <li key={e.etapa_id} className="inline-flex items-center gap-1.5">
                  <span className={cn("size-2 rounded-full", CORES_FUNIL[i % CORES_FUNIL.length])} aria-hidden />
                  {e.etapa} <span className="num">{e.quantidade}</span>
                </li>
              ))}
            </ul>
            {totalFunil === 0 && h && <p className="mt-2 text-xs text-muted">Sem oportunidades abertas.</p>}
            <p className="mt-5 text-sm text-muted">Veja evidências antes de decidir.</p>
            <Button variant="outline" size="sm" className="mt-3" onClick={() => abrirAssistente("Toda a FlicSales")}>
              Analisar operação
            </Button>
          </Painel>
        </div>
      </GradePaineis>

      <OportunidadeForm aberto={novaOp} onFechar={() => setNovaOp(false)} aoSalvar={() => router.push("/comercial/oportunidades")} />
      <AtividadeForm aberto={novaAtividade} onFechar={() => setNovaAtividade(false)} />
      <AtividadeForm aberto={!!atividade} atividade={atividade} onFechar={() => setAtividade(null)} />
      <PropostaForm aberto={novaProposta} onFechar={() => setNovaProposta(false)} />
      <NovoFunilDrawer aberto={novoFunil} onFechar={() => setNovoFunil(false)} aoCriar={() => router.push("/comercial/oportunidades")} />
      <OportunidadeDrawer id={aberta} onFechar={() => setAberta(null)} />
    </>
  );
}
