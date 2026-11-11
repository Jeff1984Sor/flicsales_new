"use client";

/**
 * TelaOpcoesLista — aba da Governança de ajustes para uma lista de opções (Segmentos · Portes · Motivos de perda):
 * busca, chips Ativos/Inativos/Todos, Exportar CSV, reordenar (arrastar pela alça ⋮⋮; ↑ ↓ pelo teclado), drawer para criar/renomear e inativar/reativar.
 * Nada se exclui. Editar exige `nucleo.administracao.editar`.
 *
 * Props: `tipo: TipoLista`.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, GripVertical, ListTree, Loader2 } from "lucide-react";
import { useState } from "react";

import { rotaAusente } from "@/components/cadastros/consultas";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { EmptyState } from "@/components/flic/empty-state";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data as formatarData } from "@/lib/format";
import { ROTULO_LISTA, type OpcaoLista, type TipoLista } from "@/lib/tipos-governanca";
import { cn } from "@/lib/utils";

import { chaveLista } from "./opcoes-lista";

type Situacao = "ativos" | "inativos" | "todos";

const ordenar = (l: OpcaoLista[]) => [...l].sort((a, b) => a.ordem - b.ordem || a.nome.localeCompare(b.nome));

export function TelaOpcoesLista({ tipo }: { tipo: TipoLista }) {
  const rotulo = ROTULO_LISTA[tipo];
  const qc = useQueryClient();
  const { pode } = useAuth();
  const editar = pode("nucleo.administracao.editar");
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [form, setForm] = useState<{ aberto: boolean; item: OpcaoLista | null }>({ aberto: false, item: null });
  const [arrastando, setArrastando] = useState<number | null>(null);
  const [sobre, setSobre] = useState<number | null>(null);
  useAtalhoNovo(() => editar && setForm({ aberto: true, item: null }));

  const chave = [...chaveLista(tipo), "todas"] as const;
  const consulta = useQuery({
    queryKey: chave,
    queryFn: () => api.get<OpcaoLista[]>(`/nucleo/listas/${tipo}`, { incluir_inativos: true }),
    retry: false,
    meta: { silencioso: true },
  });
  const todos = ordenar(consulta.data ?? []);
  const termo = q.trim().toLocaleLowerCase("pt-BR");
  const linhas = todos.filter(
    (o) =>
      (situacao === "todos" || (situacao === "ativos" ? o.ativo : !o.ativo)) &&
      (!termo || o.nome.toLocaleLowerCase("pt-BR").includes(termo)),
  );
  const contagem = { ativos: todos.filter((o) => o.ativo).length, inativos: todos.filter((o) => !o.ativo).length, todos: todos.length };
  // reordenar só com a lista inteira à vista (sem busca); a ordem vale para todas as opções
  const podeReordenar = editar && !termo;

  const invalidar = () => qc.invalidateQueries({ queryKey: chaveLista(tipo) });

  const reordenar = useMutation({
    mutationFn: (ids: number[]) => api.post<OpcaoLista[]>(`/nucleo/listas/${tipo}/reordenar`, { ids }),
    onMutate: (ids) => {
      const anterior = qc.getQueryData<OpcaoLista[]>(chave);
      if (anterior) {
        const pos = new Map(ids.map((id, i) => [id, i + 1]));
        qc.setQueryData<OpcaoLista[]>(chave, anterior.map((o) => ({ ...o, ordem: pos.get(o.id) ?? o.ordem })));
      }
      return { anterior };
    },
    onError: (_e, _ids, ctx) => {
      if (ctx?.anterior) qc.setQueryData(chave, ctx.anterior);
    },
    onSettled: invalidar,
  });

  function mover(item: OpcaoLista, passo: -1 | 1) {
    // troca com o vizinho visível (a ordem das ocultas pelo filtro de situação é preservada)
    const i = linhas.findIndex((o) => o.id === item.id);
    const vizinho = linhas[i + passo];
    if (!vizinho) return;
    const ids = todos.map((o) => o.id);
    const a = ids.indexOf(item.id);
    const b = ids.indexOf(vizinho.id);
    [ids[a], ids[b]] = [ids[b], ids[a]];
    reordenar.mutate(ids);
  }

  /** Arrastar e soltar: o item arrastado passa a ocupar a posição do alvo (os demais deslizam). */
  function soltar(alvoId: number) {
    const de = arrastando;
    setArrastando(null);
    setSobre(null);
    if (de == null || de === alvoId) return;
    const ids = todos.map((o) => o.id);
    const a = ids.indexOf(de);
    const b = ids.indexOf(alvoId);
    if (a < 0 || b < 0) return;
    ids.splice(b, 0, ...ids.splice(a, 1));
    reordenar.mutate(ids);
  }

  // qualquer célula da linha aceita o soltar
  const alvo = (o: OpcaoLista, node: React.ReactNode) =>
    podeReordenar ? (
      <div
        className={cn(sobre === o.id && arrastando !== o.id && "rounded-sm outline-2 outline-primary/50 outline-dashed")}
        onDragOver={(e) => {
          if (arrastando == null) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          if (sobre !== o.id) setSobre(o.id);
        }}
        onDrop={(e) => {
          e.preventDefault();
          soltar(o.id);
        }}
      >
        {node}
      </div>
    ) : (
      node
    );

  const colunas: Coluna<OpcaoLista>[] = [
    {
      id: "ordem",
      titulo: "Ordem",
      className: "w-[140px]",
      celula: (o) => {
        const i = linhas.findIndex((x) => x.id === o.id);
        return alvo(
          o,
          <div className="flex items-center gap-1">
            {podeReordenar && (
              <span
                draggable={!reordenar.isPending}
                onClick={(e) => e.stopPropagation()}
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = "move";
                  e.dataTransfer.setData("text/plain", String(o.id));
                  setArrastando(o.id);
                }}
                onDragEnd={() => {
                  setArrastando(null);
                  setSobre(null);
                }}
                className={cn("cursor-grab rounded p-1 text-muted hover:text-ink active:cursor-grabbing", arrastando === o.id && "opacity-50")}
                aria-hidden
                title="Arrastar para reordenar"
              >
                <GripVertical className="size-4" />
              </span>
            )}
            <span className="w-6 font-mono text-muted">{todos.findIndex((x) => x.id === o.id) + 1}</span>
            {podeReordenar && (
              <>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={`Subir ${o.nome}`}
                  disabled={i === 0 || reordenar.isPending}
                  onClick={(e) => {
                    e.stopPropagation();
                    mover(o, -1);
                  }}
                >
                  <ArrowUp />
                </Button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={`Descer ${o.nome}`}
                  disabled={i === linhas.length - 1 || reordenar.isPending}
                  onClick={(e) => {
                    e.stopPropagation();
                    mover(o, 1);
                  }}
                >
                  <ArrowDown />
                </Button>
              </>
            )}
          </div>,
        );
      },
    },
    { id: "nome", titulo: "Nome", celula: (o) => alvo(o, <strong>{o.nome}</strong>) },
    {
      id: "situacao",
      titulo: "Situação",
      celula: (o) => alvo(o, <Etiqueta tom={o.ativo ? "green" : "neutra"}>{o.ativo ? "Ativo" : "Inativo"}</Etiqueta>),
    },
    { id: "criado", titulo: "Criado em", celula: (o) => alvo(o, o.criado_em ? formatarData(o.criado_em.slice(0, 10)) : "—") },
  ];

  if (consulta.isError) {
    return (
      <EmptyState
        icone={ListTree}
        titulo={rotaAusente(consulta.error) ? "Lista ainda indisponível no servidor." : "Não foi possível carregar a lista."}
        descricao="Tente de novo em instantes. Enquanto isso, os cadastros aceitam texto livre."
      />
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">{rotulo.descricao}</p>
        {editar && <Button onClick={() => setForm({ aberto: true, item: null })}>{rotulo.novo}</Button>}
      </div>
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: `Buscar ${rotulo.plural.toLocaleLowerCase("pt-BR")}` }}
        chips={{
          opcoes: [
            { valor: "ativos", rotulo: "Ativos", contagem: contagem.ativos },
            { valor: "inativos", rotulo: "Inativos", contagem: contagem.inativos },
            { valor: "todos", rotulo: "Todos", contagem: contagem.todos },
          ],
          valor: situacao,
          onChange: (v) => setSituacao(v as Situacao),
        }}
        exportar={{
          nome: `governanca-${tipo.replace("_", "-")}`,
          linhas,
          colunas: [
            { titulo: "Ordem", valor: (o: OpcaoLista) => String(todos.findIndex((x) => x.id === o.id) + 1) },
            { titulo: "Nome", valor: (o: OpcaoLista) => o.nome },
            { titulo: "Situação", valor: (o: OpcaoLista) => (o.ativo ? "Ativo" : "Inativo") },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={consulta.isPending ? undefined : linhas}
        chave={(o) => o.id}
        onLinha={(o) => setForm({ aberto: true, item: o })}
        carregando={consulta.isPending}
        vazio={{
          icone: ListTree,
          titulo: todos.length ? "Nada com estes filtros." : "Nenhuma opção ainda.",
          descricao: todos.length ? "Troque a busca ou a situação." : `Use “${rotulo.novo.replace("+ ", "")}” para começar.`,
        }}
      />
      <Drawer
        aberto={form.aberto}
        onFechar={() => setForm({ aberto: false, item: null })}
        rotulo={`GOVERNANÇA / ${rotulo.plural.toLocaleUpperCase("pt-BR")}`}
        titulo={form.item ? form.item.nome : `Novo ${rotulo.singular.toLocaleLowerCase("pt-BR")}`}
      >
        {form.aberto && (
          <FormOpcao
            key={form.item?.id ?? "novo"}
            tipo={tipo}
            item={form.item}
            editar={editar}
            onSalvo={invalidar}
            onFechar={() => setForm({ aberto: false, item: null })}
          />
        )}
      </Drawer>
    </>
  );
}

function FormOpcao({
  tipo,
  item,
  editar,
  onSalvo,
  onFechar,
}: {
  tipo: TipoLista;
  item: OpcaoLista | null;
  editar: boolean;
  onSalvo: () => void;
  onFechar: () => void;
}) {
  const rotulo = ROTULO_LISTA[tipo];
  const [nome, setNome] = useState(item?.nome ?? "");
  const salvar = useMutation({
    mutationFn: (corpo: { nome: string }) =>
      item ? api.patch<OpcaoLista>(`/nucleo/listas/${tipo}/${item.id}`, corpo) : api.post<OpcaoLista>(`/nucleo/listas/${tipo}`, corpo),
    onSuccess: () => {
      onSalvo();
      notificar(item ? `${rotulo.singular} atualizado` : `${rotulo.singular} criado`);
      onFechar();
    },
  });
  const ativar = useMutation({
    mutationFn: (ativo: boolean) => api.patch<OpcaoLista>(`/nucleo/listas/${tipo}/${item?.id}`, { ativo }),
    onSuccess: (r) => {
      onSalvo();
      notificar(r.ativo ? `${rotulo.singular} reativado` : `${rotulo.singular} inativado. Registros que já usam o valor não mudam.`);
      onFechar();
    },
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const limpo = nome.trim();
        if (!limpo) {
          notificar("Informe o nome");
          return;
        }
        if (item && limpo === item.nome) {
          onFechar();
          return;
        }
        salvar.mutate({ nome: limpo });
      }}
    >
      <fieldset disabled={!editar}>
        <CampoDrawer rotulo="Nome" obrigatorio>
          <Input value={nome} onChange={(e) => setNome(e.target.value)} required maxLength={120} autoFocus />
        </CampoDrawer>
      </fieldset>
      {item && (
        <p className="mt-3 text-xs text-muted">
          Situação: {item.ativo ? "ativo, aparece nas listas suspensas." : "inativo, não aparece em cadastros novos."}
        </p>
      )}
      {editar && (
        <div className="mt-5 flex flex-wrap gap-2">
          <Button type="submit" disabled={salvar.isPending}>
            {salvar.isPending && <Loader2 className="animate-spin" />}
            Salvar
          </Button>
          {item && (
            <Button type="button" variant="outline" disabled={ativar.isPending} onClick={() => ativar.mutate(!item.ativo)}>
              {item.ativo ? "Inativar" : "Reativar"}
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onFechar}>
            Cancelar
          </Button>
        </div>
      )}
      <p className="mt-4 text-xs text-muted">Nada é excluído: inativar só tira a opção das listas.</p>
    </form>
  );
}
