"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { CHAVE, useInvalidarComercial, useOpcoes, useUsuarios } from "@/components/comercial/dados";
import { EtapasDrawer, NovoFunilDrawer } from "@/components/comercial/funil-drawers";
import { OportunidadeDrawer } from "@/components/comercial/oportunidade-drawer";
import { OportunidadeForm } from "@/components/comercial/oportunidade-form";
import { SearchInput } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { NativeSelect } from "@/components/flic/form";
import { CartaoKanban, Kanban } from "@/components/flic/kanban";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data } from "@/lib/format";
import type { Oportunidade } from "@/lib/tipos-comercial";

export default function OportunidadesPage() {
  const { pode, usuario } = useAuth();
  const editar = pode("comercial.oportunidades.editar");
  const invalidar = useInvalidarComercial();
  const { data: opcoes } = useOpcoes();
  const { data: usuarios } = useUsuarios();
  const [funilEscolhido, setFunilEscolhido] = useState<number | null>(null);
  const [responsavel, setResponsavel] = useState("");
  const [q, setQ] = useState("");
  const [nova, setNova] = useState(false);
  const [novoFunil, setNovoFunil] = useState(false);
  const [etapasAberto, setEtapasAberto] = useState(false);
  const [aberta, setAberta] = useState<number | null>(null);
  useAtalhoNovo(() => editar && setNova(true));

  const funis = opcoes?.funis ?? [];
  const funil = funis.find((f) => f.id === funilEscolhido) ?? funis[0] ?? null;

  const { data: lista, isPending } = useQuery({
    queryKey: [CHAVE, "oportunidades", funil?.id, responsavel, q],
    queryFn: () => api.get<Oportunidade[]>("/comercial/oportunidades", { funil_id: funil?.id, responsavel_id: responsavel, q }),
    enabled: !!funil,
  });

  const mover = useMutation({
    mutationFn: ({ op, etapaId }: { op: Oportunidade; etapaId: number }) => api.post<Oportunidade>(`/comercial/oportunidades/${op.id}/mover`, { etapa_id: etapaId }),
    onSuccess: (r) => {
      invalidar();
      notificar(`${r.titulo} movida para ${r.etapa_nome}`);
    },
  });
  const reabrir = useMutation({
    mutationFn: (id: number) => api.post<Oportunidade>(`/comercial/oportunidades/${id}/reabrir`),
    onSuccess: () => {
      invalidar();
      notificar("Oportunidade reaberta");
    },
  });

  const abertas = (lista ?? []).filter((o) => o.resultado === "aberta");
  const ganhas = (lista ?? []).filter((o) => o.resultado === "ganha");
  const perdidas = (lista ?? []).filter((o) => o.resultado === "perdida");

  const colunas = (funil?.etapas ?? []).map((e) => ({
    id: String(e.id),
    titulo: e.nome,
    subtitulo: `${e.probabilidade}% · ${e.limite_dias ? `limite de ${e.limite_dias} dias` : "sem limite"}`,
    itens: abertas.filter((o) => o.etapa_id === e.id),
  }));

  return (
    <>
      <PageHeader
        titulo="Oportunidades"
        descricao="Funis configuráveis, critérios de avanço e próximos passos."
        acao={editar ? <Button onClick={() => setNova(true)}>+ Oportunidade</Button> : undefined}
      />

      <div className="mb-5 flex flex-wrap items-center gap-2.5">
        <div className="w-[230px]">
          <NativeSelect aria-label="Funil de vendas" value={String(funil?.id ?? "")} onChange={(e) => setFunilEscolhido(Number(e.target.value))}>
            {funis.map((f) => (
              <option key={f.id} value={f.id}>
                {f.nome}
              </option>
            ))}
          </NativeSelect>
        </div>
        {editar && (
          <>
            <Button variant="outline" onClick={() => setNovoFunil(true)}>
              + Criar funil
            </Button>
            <Button variant="outline" onClick={() => setEtapasAberto(true)} disabled={!funil}>
              Configurar etapas
            </Button>
          </>
        )}
        <Button variant="outline" render={<Link href="/comercial/gestao" />}>
          Campos e processo
        </Button>
        {!usuario?.somente_meus_registros && (
          <div className="w-[200px]">
            <NativeSelect aria-label="Responsável" value={responsavel} onChange={(e) => setResponsavel(e.target.value)}>
              <option value="">Todas as pessoas</option>
              {(usuarios ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nome}
                </option>
              ))}
            </NativeSelect>
          </div>
        )}
        <SearchInput value={q} onChange={setQ} placeholder="Buscar oportunidade ou empresa" className="sm:w-64" />
        <span className="ml-auto text-xs text-muted">Clique em um negócio para explorar · arraste para mudar de etapa</span>
      </div>

      {isPending && !!funil ? (
        <div className="grid gap-3 md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[350px] rounded-[9px]" />
          ))}
        </div>
      ) : (
        <Kanban
          colunas={colunas}
          chave={(o) => o.id}
          onCartao={(o) => setAberta(o.id)}
          onMover={editar ? (o, col) => mover.mutate({ op: o, etapaId: Number(col) }) : undefined}
          cartao={(o) => (
            <CartaoKanban
              etiqueta={
                <span className="flex flex-wrap gap-1">
                  {o.interesse && <Etiqueta tom={o.interesse === "Alto" ? "green" : "neutra"}>{o.interesse} interesse</Etiqueta>}
                  {o.alem_do_limite && <Etiqueta tom="amber">{o.dias_na_etapa} dias na etapa</Etiqueta>}
                </span>
              }
              titulo={o.titulo}
              subtitulo={o.empresa_nome ?? "Empresa a definir"}
              valor={<Dinheiro valor={o.valor_unico} />}
              rodape={`${o.responsavel_nome ?? ""} · ${o.proxima_acao ?? "Próxima ação a definir"}`}
            />
          )}
        />
      )}

      <Painel titulo="Resultados do funil" className="mt-5">
        <p>
          Ganhos: <span className="num">{ganhas.length}</span> · Perdidos: <span className="num">{perdidas.length}</span>
        </p>
        {(ganhas.length > 0 || perdidas.length > 0) && (
          <ul className="mt-3 divide-y divide-line text-sm">
            {[...ganhas, ...perdidas].map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-2 py-2">
                <Etiqueta tom={o.resultado === "ganha" ? "green" : "amber"}>{o.resultado === "ganha" ? "Ganha" : "Perdida"}</Etiqueta>
                <span className="font-medium">{o.empresa_nome ?? "—"}</span>
                <span className="text-muted">· {o.titulo} ·</span>
                <Dinheiro valor={o.valor_unico} />
                <span className="text-xs text-muted">{data(o.resultado === "ganha" ? o.ganha_em : o.perdida_em)}</span>
                <span className="ml-auto flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setAberta(o.id)}>
                    Ver origem
                  </Button>
                  {o.resultado === "perdida" && editar && (
                    <Button variant="outline" size="sm" onClick={() => reabrir.mutate(o.id)}>
                      Reabrir
                    </Button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted">
          Probabilidades são parâmetros configurados, não previsões de IA. Campos exigidos por etapa são conferidos ao mover.
        </p>
      </Painel>

      <OportunidadeForm aberto={nova} onFechar={() => setNova(false)} funilId={funil?.id} />
      <OportunidadeDrawer id={aberta} onFechar={() => setAberta(null)} />
      <NovoFunilDrawer aberto={novoFunil} onFechar={() => setNovoFunil(false)} aoCriar={(f) => setFunilEscolhido(f.id)} />
      <EtapasDrawer funil={funil} aberto={etapasAberto} onFechar={() => setEtapasAberto(false)} />
    </>
  );
}
