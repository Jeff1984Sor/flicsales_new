"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Target } from "lucide-react";
import { useState } from "react";

import { lerForm, nulo, numeroOuNulo, pct, useInvalidarComercial, useOpcoes, useUsuarios } from "@/components/comercial/dados";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { NativeSelect } from "@/components/flic/form";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, numero } from "@/lib/format";
import { type Forecast, INDICADORES_META, type IndicadorMeta, type Meta } from "@/lib/tipos-comercial";

const ehMoeda = (i: string) => INDICADORES_META.find((x) => x.valor === i)?.moeda ?? false;
const rotuloIndicador = (i: string) => INDICADORES_META.find((x) => x.valor === i)?.rotulo ?? i;
const valorMeta = (i: string, v: string) => (ehMoeda(i) ? <Dinheiro valor={v} /> : <span className="num">{numero(v)}</span>);

export default function MetasPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.metas.editar");
  const [q, setQ] = useState("");
  const [form, setForm] = useState<{ aberto: boolean; meta: Meta | null }>({ aberto: false, meta: null });
  useAtalhoNovo(() => editar && setForm({ aberto: true, meta: null }));

  const { data: metas, isPending } = useQuery({ queryKey: ["comercial", "metas"], queryFn: () => api.get<Meta[]>("/comercial/metas") });
  const { data: fc, isPending: carregandoFc } = useQuery({ queryKey: ["comercial", "forecast"], queryFn: () => api.get<Forecast>("/comercial/forecast") });

  const filtradas = (metas ?? []).filter((m) => `${m.nome} ${m.responsavel_nome ?? ""} ${m.equipe ?? ""}`.toLowerCase().includes(q.toLowerCase()));

  const colunas: Coluna<Meta>[] = [
    {
      id: "nome",
      titulo: "Nome da meta",
      celula: (m) => (
        <>
          <strong>{m.nome}</strong>
          <p className="text-muted">{rotuloIndicador(m.indicador)}</p>
        </>
      ),
    },
    { id: "resp", titulo: "Pessoa / equipe", celula: (m) => (m.responsavel_tipo === "equipe" ? m.equipe : m.responsavel_nome) ?? "—" },
    { id: "periodo", titulo: "Período", celula: (m) => `${data(m.inicio)} – ${data(m.fim)}` },
    { id: "alvo", titulo: "Meta", alinhar: "direita", celula: (m) => valorMeta(m.indicador, m.alvo) },
    {
      id: "apuracao",
      titulo: "Realizado",
      celula: (m) => {
        const p = Math.min(100, Math.max(0, Number(m.percentual ?? 0)));
        return (
          <div className="min-w-[160px]" title={`Fórmula: ${m.formula}`}>
            <div className="flex justify-between gap-2">
              {valorMeta(m.indicador, m.realizado)}
              <span className="num text-muted">{pct(m.percentual)}</span>
            </div>
            <div className="mt-1.5 h-1.5 rounded-full bg-subtle">
              <div className="h-1.5 rounded-full bg-primary" style={{ width: `${p}%` }} />
            </div>
            <p className="mt-1 text-[10px] text-muted">{m.formula}</p>
          </div>
        );
      },
    },
  ];

  return (
    <>
      <PageHeader
        titulo="Metas e forecast"
        descricao="Metas por período e pessoa, com apuração verificável e projeção por parâmetros."
        acao={editar ? <Button onClick={() => setForm({ aberto: true, meta: null })}>+ Novo registro</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar registros desta tela" }}
        exportar={{
          nome: "metas",
          linhas: filtradas,
          colunas: [
            { titulo: "Meta", valor: (m: Meta) => m.nome },
            { titulo: "Indicador", valor: (m: Meta) => rotuloIndicador(m.indicador) },
            { titulo: "Responsável", valor: (m: Meta) => (m.responsavel_tipo === "equipe" ? m.equipe : m.responsavel_nome) ?? "" },
            { titulo: "Início", valor: (m: Meta) => data(m.inicio) },
            { titulo: "Fim", valor: (m: Meta) => data(m.fim) },
            { titulo: "Alvo", valor: (m: Meta) => m.alvo },
            { titulo: "Realizado", valor: (m: Meta) => m.realizado },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={filtradas}
        chave={(m) => m.id}
        onLinha={editar ? (m) => setForm({ aberto: true, meta: m }) : undefined}
        carregando={isPending}
        vazio={{ icone: Target, titulo: "Nenhuma meta cadastrada.", descricao: "Use “Novo registro” para começar." }}
      />

      <Painel titulo="Forecast comercial configurado">
        <Metricas>
          <KpiCard rotulo="Pipeline único aberto" valor={<Dinheiro valor={fc?.pipeline_aberto} />} detalhe="Exclui ganhos e perdas" formula={fc?.formulas.pipeline_aberto} carregando={carregandoFc} />
          <KpiCard rotulo="Valor ponderado" valor={<Dinheiro valor={fc?.ponderado} />} detalhe="Valor × probabilidade da etapa" formula={fc?.formulas.ponderado} carregando={carregandoFc} />
          <KpiCard rotulo="MRR potencial" valor={<Dinheiro valor={fc?.mrr_potencial} />} detalhe="Separado do valor único" formula={fc?.formulas.mrr_potencial} carregando={carregandoFc} />
          <KpiCard rotulo="Sem previsão" valor={fc?.sem_previsao ?? 0} detalhe="Datas de fechamento ausentes" formula={fc?.formulas.sem_previsao} carregando={carregandoFc} tom={fc && fc.sem_previsao > 0 ? "atencao" : "padrao"} />
        </Metricas>
        {fc && fc.por_etapa.length > 0 && (
          <div className="mb-4 grid gap-2 text-xs">
            {fc.por_etapa.map((e) => (
              <div key={e.etapa} className="flex flex-wrap justify-between gap-2 border-b border-line pb-2">
                <span>
                  {e.etapa} · <span className="num">{e.probabilidade}%</span> · {e.quantidade} oportunidade(s)
                </span>
                <span>
                  <Dinheiro valor={e.valor} /> → <Dinheiro valor={e.ponderado} />
                </span>
              </div>
            ))}
          </div>
        )}
        <p className="text-sm text-muted">
          {fc?.limite ?? "Projeção comercial por parâmetros, sem previsão estatística e sem compor o caixa."} Metas cadastradas precisam do histórico do período para apuração confiável.
        </p>
      </Painel>

      <MetaForm aberto={form.aberto} meta={form.meta} onFechar={() => setForm({ aberto: false, meta: null })} />
    </>
  );
}

function MetaForm({ aberto, meta, onFechar }: { aberto: boolean; meta: Meta | null; onFechar: () => void }) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} titulo={meta ? "Editar · Metas e forecast" : "Novo registro · Metas e forecast"}>
      {aberto && <MetaCorpo key={meta?.id ?? "nova"} meta={meta} onFechar={onFechar} />}
    </Drawer>
  );
}

function MetaCorpo({ meta, onFechar }: { meta: Meta | null; onFechar: () => void }) {
  const { data: usuarios } = useUsuarios();
  const { data: opcoes } = useOpcoes();
  const invalidar = useInvalidarComercial();
  const [tipo, setTipo] = useState<"pessoa" | "equipe">(meta?.responsavel_tipo ?? "pessoa");
  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) => (meta ? api.patch<Meta>(`/comercial/metas/${meta.id}`, corpo) : api.post<Meta>("/comercial/metas", corpo)),
    onSuccess: () => {
      invalidar();
      notificar("Meta salva");
      onFechar();
    },
  });

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = lerForm(e.currentTarget);
    if (f.fim < f.inicio) {
      notificar("A data final deve ser igual ou posterior ao início");
      return;
    }
    salvar.mutate({
      nome: f.nome.trim(),
      responsavel_tipo: tipo,
      responsavel_id: tipo === "pessoa" ? numeroOuNulo(f.responsavel_id) : null,
      equipe: tipo === "equipe" ? nulo(f.equipe) : null,
      inicio: f.inicio,
      fim: f.fim,
      indicador: f.indicador as IndicadorMeta,
      alvo: f.alvo,
      funil_id: numeroOuNulo(f.funil_id),
    });
  }

  return (
    <form id="form-meta" onSubmit={enviar}>
      <CampoDrawer rotulo="Nome da meta" obrigatorio>
        <Input name="nome" required defaultValue={meta?.nome ?? ""} maxLength={150} />
      </CampoDrawer>
      <CampoDrawer rotulo="Pessoa / equipe" obrigatorio>
        <NativeSelect value={tipo} onChange={(e) => setTipo(e.target.value as "pessoa" | "equipe")}>
          <option value="pessoa">Pessoa</option>
          <option value="equipe">Equipe</option>
        </NativeSelect>
      </CampoDrawer>
      {tipo === "pessoa" ? (
        <CampoDrawer rotulo="Pessoa" obrigatorio>
          <NativeSelect name="responsavel_id" required defaultValue={String(meta?.responsavel_id ?? "")}>
            <option value="">Selecione</option>
            {(usuarios ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
      ) : (
        <CampoDrawer rotulo="Equipe" obrigatorio>
          <Input name="equipe" required defaultValue={meta?.equipe ?? ""} placeholder="Ex.: Comercial" />
        </CampoDrawer>
      )}
      <div className="grid grid-cols-2 gap-3">
        <CampoDrawer rotulo="Início" obrigatorio>
          <Input name="inicio" type="date" required defaultValue={meta?.inicio ?? ""} />
        </CampoDrawer>
        <CampoDrawer rotulo="Fim" obrigatorio>
          <Input name="fim" type="date" required defaultValue={meta?.fim ?? ""} />
        </CampoDrawer>
      </div>
      <CampoDrawer rotulo="Indicador" obrigatorio>
        <NativeSelect name="indicador" defaultValue={meta?.indicador ?? "receita_unica_ganha"}>
          {INDICADORES_META.map((i) => (
            <option key={i.valor} value={i.valor}>
              {i.rotulo}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Meta numérica" obrigatorio dica="Moeda (R$) para receita e MRR; quantidade para vendas e atividades.">
        <Input name="alvo" type="number" min="0.01" step="0.01" required defaultValue={meta?.alvo ?? ""} />
      </CampoDrawer>
      <CampoDrawer rotulo="Funil">
        <NativeSelect name="funil_id" defaultValue={String(meta?.funil_id ?? "")}>
          <option value="">Todos os funis</option>
          {(opcoes?.funis ?? []).map((f) => (
            <option key={f.id} value={f.id}>
              {f.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <div className="mt-5 flex gap-2">
        <Button type="submit" disabled={salvar.isPending}>
          {salvar.isPending && <Loader2 className="animate-spin" />}
          Salvar registro
        </Button>
        <Button type="button" variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
