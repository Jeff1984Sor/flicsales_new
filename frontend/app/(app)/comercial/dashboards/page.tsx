"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { lerForm, nulo, numeroOuNulo, useInvalidarComercial, useOpcoes } from "@/components/comercial/dados";
import { Dinheiro } from "@/components/flic/dinheiro";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { NativeSelect } from "@/components/flic/form";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { PageHeader } from "@/components/flic/page-header";
import { GradePaineis, Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { moeda, moedaCompacta, numero } from "@/lib/format";
import type { Dashboard, IndicadorConfig, PreviaIndicador } from "@/lib/tipos-comercial";

type Metrica = "soma_valor_unico" | "quantidade";
const valorIndicador = (m: Metrica, v: string) => (m === "soma_valor_unico" ? <Dinheiro valor={v} /> : <span className="num">{numero(v)}</span>);

export default function DashboardsPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.desempenho.editar");
  const [config, setConfig] = useState(false);
  useAtalhoNovo(() => editar && setConfig(true));
  const { data: d, isPending, isError, refetch } = useQuery({ queryKey: ["comercial", "dashboards"], queryFn: () => api.get<Dashboard>("/comercial/dashboards") });
  // erro ≠ zero: sem dados, os KPIs mostram "—" e um aviso, nunca "0"
  const kpi = (v: number | undefined) => (isError ? "—" : (v ?? 0));
  const grafico = (d?.pipeline_por_etapa ?? []).map((e) => ({ etapa: e.etapa, valor: Number(e.valor), quantidade: e.quantidade }));

  return (
    <>
      <PageHeader
        titulo="Dashboards"
        descricao="Sua visão de gestão, com campos padrão e personalizados."
        acao={editar ? <Button onClick={() => setConfig(true)}>+ Configurar indicador</Button> : undefined}
      />
      {isError && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-[10px] border border-amber/40 bg-amber/10 p-3 text-sm" role="alert">
          <span>Não foi possível carregar os dashboards agora. Os números abaixo não estão disponíveis.</span>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Tentar de novo
          </Button>
        </div>
      )}
      <Metricas>
        <KpiCard rotulo="Pipeline · alto interesse" valor={isError ? "—" : <Dinheiro valor={d?.pipeline_alto_interesse} />} detalhe="Filtro por campo personalizado" formula="Σ valor único das abertas com Interesse = Alto" carregando={isPending && !isError} />
        <KpiCard rotulo="Oportunidades" valor={kpi(d?.oportunidades)} detalhe="Registros no seu escopo" carregando={isPending && !isError} />
        <KpiCard rotulo="Recebíveis" valor={kpi(d?.recebiveis)} detalhe="Gerados por vendas ganhas" carregando={isPending && !isError} />
        <KpiCard rotulo="Próximas ações" valor={kpi(d?.proximas_acoes)} detalhe="Atividades pendentes" carregando={isPending && !isError} />
      </Metricas>
      <GradePaineis>
        <Painel titulo="Pipeline por etapa">
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={grafico} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--line)" />
                <XAxis dataKey="etapa" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v: number) => moedaCompacta(v)} tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} width={70} />
                <Tooltip
                  cursor={{ fill: "var(--subtle)" }}
                  formatter={(v) => [moeda(Number(v)), "Valor único"]}
                  contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="valor" fill="var(--electric)" radius={[6, 6, 0, 0]} maxBarSize={56} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-sm text-muted">Valores únicos abertos. O funil não compõe o saldo de caixa.</p>
        </Painel>
        <Painel titulo="Personalização compartilhada">
          <p className="text-sm">Campos personalizados podem ser usados nos filtros, indicadores e condições dos fluxos.</p>
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer font-medium">Definição do indicador de interesse</summary>
            <p className="mt-2 text-muted">Soma de valor único das oportunidades abertas em que Interesse = Alto. Exclui ganhos e perdas.</p>
          </details>
          <Button variant="outline" className="mt-4" render={<Link href="/nucleo/campos" />}>
            Ver campos
          </Button>
        </Painel>
      </GradePaineis>

      <Painel titulo="Indicadores configurados" acao={<Etiqueta>{isError ? "Indisponível" : `${d?.indicadores.length ?? 0} ativo(s)`}</Etiqueta>}>
        {isError ? (
          <p className="text-sm text-muted">Não foi possível carregar os indicadores configurados.</p>
        ) : (d?.indicadores ?? []).length === 0 ? (
          <p className="text-sm text-muted">Nenhum indicador configurado. Use “Configurar indicador” para criar um com filtro por campo personalizado.</p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 min-[1100px]:grid-cols-3">
            {d?.indicadores.map((i) => <CartaoIndicador key={i.id} i={i} editar={editar} />)}
          </div>
        )}
      </Painel>

      <Drawer aberto={config} onFechar={() => setConfig(false)} titulo="Configurar indicador">
        {config && <FormIndicador onFechar={() => setConfig(false)} />}
      </Drawer>
    </>
  );
}

function CartaoIndicador({ i, editar }: { i: IndicadorConfig; editar: boolean }) {
  const invalidar = useInvalidarComercial();
  const inativar = useMutation({
    mutationFn: () => api.patch<IndicadorConfig>(`/comercial/indicadores/${i.id}`, { ativo: false }),
    onSuccess: () => {
      invalidar();
      notificar("Indicador inativado");
    },
  });
  return (
    <div className="rounded-[10px] border border-line p-4" title={i.resultado?.formula}>
      <span className="text-muted">{i.nome}</span>
      <strong className="num mt-2 block text-[23px]">{i.resultado ? valorIndicador(i.metrica, i.resultado.valor) : "—"}</strong>
      <p className="text-xs text-primary">{i.resultado?.descricao ?? (i.filtro_campo_nome ? `${i.filtro_campo_nome} = ${i.filtro_valor}` : "Oportunidades abertas")}</p>
      {i.resultado && <p className="mt-1 text-[11px] text-muted">Fórmula: {i.resultado.formula}</p>}
      {editar && (
        <Button size="sm" variant="ghost" className="mt-2" disabled={inativar.isPending} onClick={() => inativar.mutate()}>
          Inativar
        </Button>
      )}
    </div>
  );
}

function FormIndicador({ onFechar }: { onFechar: () => void }) {
  const { data: opcoes } = useOpcoes();
  const invalidar = useInvalidarComercial();
  const campos = (opcoes?.campos ?? []).filter((c) => c.objeto === "oportunidade");
  const [campoId, setCampoId] = useState<string>("");
  const [previa, setPrevia] = useState<PreviaIndicador | null>(null);
  const campo = campos.find((c) => String(c.id) === campoId);

  const corpo = (form: HTMLFormElement) => {
    const f = lerForm(form);
    return {
      nome: f.nome.trim(),
      metrica: f.metrica as Metrica,
      filtro_campo_id: numeroOuNulo(f.filtro_campo_id),
      filtro_valor: nulo(f.filtro_valor),
    };
  };
  const calcular = useMutation({
    mutationFn: (c: ReturnType<typeof corpo>) => api.post<PreviaIndicador>("/comercial/indicadores/previa", c),
    onSuccess: setPrevia,
  });
  const salvar = useMutation({
    mutationFn: (c: ReturnType<typeof corpo>) => api.post<IndicadorConfig>("/comercial/indicadores", c),
    onSuccess: () => {
      invalidar();
      notificar("Indicador salvo no dashboard");
      onFechar();
    },
  });
  const [metrica, setMetrica] = useState<Metrica>("soma_valor_unico");

  return (
    <form
      id="form-indicador"
      onSubmit={(e) => {
        e.preventDefault();
        salvar.mutate(corpo(e.currentTarget));
      }}
    >
      <CampoDrawer rotulo="Nome" obrigatorio>
        <Input name="nome" required defaultValue="Pipeline por interesse" maxLength={150} />
      </CampoDrawer>
      <CampoDrawer rotulo="Objeto">
        <NativeSelect disabled defaultValue="oportunidade">
          <option value="oportunidade">Oportunidades</option>
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Métrica">
        <NativeSelect name="metrica" value={metrica} onChange={(e) => setMetrica(e.target.value as Metrica)}>
          <option value="soma_valor_unico">Soma do valor único</option>
          <option value="quantidade">Quantidade</option>
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Filtro de campo personalizado">
        <NativeSelect name="filtro_campo_id" value={campoId} onChange={(e) => setCampoId(e.target.value)}>
          <option value="">Sem filtro</option>
          {campos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      {campo && (
        <CampoDrawer rotulo={`Valor de ${campo.nome}`} obrigatorio>
          {campo.opcoes.length > 0 ? (
            <NativeSelect key={campo.id} name="filtro_valor" defaultValue={campo.opcoes[campo.opcoes.length - 1]}>
              {campo.opcoes.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </NativeSelect>
          ) : (
            <Input key={campo.id} name="filtro_valor" required />
          )}
        </CampoDrawer>
      )}
      <Button
        type="button"
        className="mt-5"
        disabled={calcular.isPending}
        onClick={(e) => {
          const form = e.currentTarget.form;
          if (form) calcular.mutate(corpo(form));
        }}
      >
        Calcular prévia
      </Button>
      <div className="mt-4 rounded-[10px] border border-line bg-subtle p-4 text-sm">
        {previa ? (
          <>
            <p>
              {previa.descricao}: <strong>{valorIndicador(metrica, previa.valor)}</strong> ({previa.quantidade} oportunidade(s))
            </p>
            <p className="mt-1 text-xs text-muted">Fórmula: {previa.formula}</p>
          </>
        ) : (
          "Escolha o filtro e calcule."
        )}
      </div>
      <p className="mt-3 text-xs text-muted">O cálculo usa os registros do seu escopo e exclui ganhos e perdas.</p>
      <div className="mt-5 flex gap-2">
        <Button type="submit" variant="outline" disabled={salvar.isPending}>
          Salvar indicador
        </Button>
        <Button type="button" variant="ghost" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
