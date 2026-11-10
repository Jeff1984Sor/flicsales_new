"use client";

import { useQuery } from "@tanstack/react-query";
import { Gauge } from "lucide-react";
import { useState } from "react";

import { AtividadeForm } from "@/components/comercial/atividade-form";
import { pct } from "@/components/comercial/dados";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { Fonte } from "@/components/flic/fonte";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, hojeISO, numero } from "@/lib/format";
import type { Desempenho, Evidencias, Oportunidade, VendedorDesempenho } from "@/lib/tipos-comercial";

const inicioDoMes = () => `${hojeISO().slice(0, 8)}01`;

export default function DesempenhoPage() {
  const { pode } = useAuth();
  const [inicio, setInicio] = useState(inicioDoMes);
  const [fim, setFim] = useState(hojeISO);
  const [sel, setSel] = useState<VendedorDesempenho | null>(null);
  const [acao, setAcao] = useState<string | null>(null);

  const periodoOk = !!inicio && !!fim && fim >= inicio;
  const { data: d, isPending } = useQuery({
    queryKey: ["comercial", "desempenho", inicio, fim],
    queryFn: () => api.get<Desempenho>("/comercial/desempenho", { inicio, fim }),
    enabled: periodoOk,
  });
  const { data: ev, isPending: carregandoEv } = useQuery({
    queryKey: ["comercial", "desempenho", "evidencias", sel?.usuario_id, inicio, fim],
    queryFn: () => api.get<Evidencias>("/comercial/desempenho/evidencias", { usuario_id: sel?.usuario_id, inicio, fim }),
    enabled: !!sel && periodoOk,
  });

  const colunas: Coluna<VendedorDesempenho>[] = [
    { id: "nome", titulo: "Vendedor", celula: (v) => <strong>{v.nome}</strong> },
    { id: "ge", titulo: "Ganhas / encerradas", celula: (v) => <span className="num">{`${v.ganhas} / ${v.encerradas}`}</span> },
    { id: "conv", titulo: "Conversão", celula: (v) => <span className="num">{pct(v.conversao)}</span> },
    { id: "receita", titulo: "Receita ganha", alinhar: "direita", celula: (v) => <Dinheiro valor={v.receita} /> },
    { id: "sem", titulo: "Sem próxima ação", alinhar: "centro", celula: (v) => <span className="num">{v.sem_proxima_acao}</span> },
    {
      id: "analise",
      titulo: "Análise",
      celula: (v) => (
        <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setSel(v); }}>
          Ver evidências
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader titulo="Desempenho da equipe" descricao="Indicadores verificáveis para orientar o desenvolvimento." />
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <label className="text-xs">
          Início
          <Input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} className="mt-1 w-auto" />
        </label>
        <label className="text-xs">
          Fim
          <Input type="date" value={fim} onChange={(e) => setFim(e.target.value)} className="mt-1 w-auto" />
        </label>
        {!periodoOk && <Etiqueta tom="amber">A data final deve ser igual ou posterior ao início</Etiqueta>}
        {d && <Etiqueta>{`${d.encerradas} oportunidades encerradas`}</Etiqueta>}
      </div>
      <Metricas>
        <KpiCard rotulo="Conversão" valor={pct(d?.conversao.valor)} detalhe={d?.conversao.detalhe} formula={d?.conversao.formula} carregando={isPending && periodoOk} />
        <KpiCard rotulo="Receita ganha" valor={<Dinheiro valor={d?.receita_ganha.valor} compacto />} detalhe={d?.receita_ganha.detalhe} formula={d?.receita_ganha.formula} carregando={isPending && periodoOk} />
        <KpiCard rotulo="Ticket médio" valor={<Dinheiro valor={d?.ticket_medio.valor} compacto />} detalhe={d?.ticket_medio.detalhe} formula={d?.ticket_medio.formula} carregando={isPending && periodoOk} />
        <KpiCard
          rotulo="Ciclo mediano"
          valor={d?.ciclo_mediano.valor != null ? `${numero(d.ciclo_mediano.valor)} dias` : "—"}
          detalhe={d?.ciclo_mediano.detalhe}
          formula={d?.ciclo_mediano.formula}
          carregando={isPending && periodoOk}
        />
      </Metricas>
      <DataTable
        colunas={colunas}
        linhas={d?.vendedores}
        chave={(v) => v.usuario_id}
        onLinha={setSel}
        carregando={isPending && periodoOk}
        vazio={{ icone: Gauge, titulo: "Sem oportunidades no escopo.", descricao: "Os indicadores aparecem quando houver registros no período." }}
      />
      <Painel titulo="Critérios transparentes">
        <p className="text-sm text-muted">
          Sem ranking, nota única ou inferência de personalidade. Vendedores em ordem alfabética. Comparações exigem carteiras e períodos equivalentes.
        </p>
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium">Fórmulas e limites</summary>
          <p className="mt-2 leading-relaxed">
            Conversão = ganhas ÷ (ganhas + perdidas). Ticket = receita única ganha ÷ quantidade de vendas. Ciclo = mediana dos dias da criação ao ganho.
          </p>
          {d?.limites.map((l) => (
            <p key={l} className="text-muted">
              {l}
            </p>
          ))}
        </details>
      </Painel>

      <Drawer aberto={!!sel} onFechar={() => setSel(null)} titulo={sel ? `Desenvolvimento · ${sel.nome}` : undefined} descricao={`${data(inicio)} – ${data(fim)}`}>
        {carregandoEv || !ev ? (
          <p className="text-sm text-muted">Carregando evidências…</p>
        ) : (
          <>
            <div className="rounded-[10px] border border-line bg-subtle p-4">
              <h3 className="text-sm font-bold">Gargalo observado</h3>
              <p className="mt-1 text-sm">{ev.gargalo}</p>
              <h3 className="mt-4 text-sm font-bold">Ação sugerida</h3>
              <p className="mt-1 text-sm">{ev.acao_sugerida}</p>
              <Fonte limite={ev.limites} />
            </div>
            <ListaOps titulo="Ganhas no período" ops={ev.ganhas} />
            <ListaOps titulo="Perdidas no período" ops={ev.perdidas} />
            <ListaOps titulo="Abertas sem próxima ação" ops={ev.sem_proxima_acao} />
            <ListaOps titulo="Além do limite da etapa" ops={ev.alem_do_limite} />
            <h3 className="mt-5 text-sm font-bold">Atividades atrasadas ({ev.atividades_atrasadas.length})</h3>
            {ev.atividades_atrasadas.length === 0 ? (
              <p className="text-xs text-muted">Nenhuma.</p>
            ) : (
              <ul className="mt-1 text-xs">
                {ev.atividades_atrasadas.map((a) => (
                  <li key={a.id} className="border-b border-line py-1.5">
                    {a.assunto} · {data(a.prazo)}
                    {a.empresa_nome ? ` · ${a.empresa_nome}` : ""}
                  </li>
                ))}
              </ul>
            )}
            {pode("comercial.atividades.editar") && (
              <Button className="mt-5" onClick={() => setAcao(ev.nome)}>
                Criar ação de desenvolvimento
              </Button>
            )}
          </>
        )}
      </Drawer>
      <AtividadeForm
        aberto={!!acao}
        onFechar={() => setAcao(null)}
        titulo="Ação de desenvolvimento"
        inicial={{ assunto: `Revisar próximas ações com ${acao ?? ""}`, tipo: "tarefa", objetivo: ev?.acao_sugerida }}
      />
    </>
  );
}

function ListaOps({ titulo, ops }: { titulo: string; ops: Oportunidade[] }) {
  return (
    <>
      <h3 className="mt-5 text-sm font-bold">
        {titulo} ({ops.length})
      </h3>
      {ops.length === 0 ? (
        <p className="text-xs text-muted">Nenhuma.</p>
      ) : (
        <ul className="mt-1 text-xs">
          {ops.map((o) => (
            <li key={o.id} className="flex justify-between gap-2 border-b border-line py-1.5">
              <span>
                {o.titulo}
                {o.empresa_nome ? ` · ${o.empresa_nome}` : ""}
                {o.etapa_nome && o.resultado === "aberta" ? ` · ${o.etapa_nome}` : ""}
              </span>
              <Dinheiro valor={o.valor_unico} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
