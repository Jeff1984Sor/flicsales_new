"use client";

/** Financeiro › Recorrências (protótipo `entityList('Recorrências')` + `generateCycle`): CRUD e "Gerar competência". */
import { useQuery } from "@tanstack/react-query";
import { Repeat } from "lucide-react";
import { useState } from "react";

import { CHAVE, Limite, ROTULO_FREQUENCIA, ROTULO_SIT_RECORRENCIA } from "@/components/financeiro/comum";
import { DetalheTitulo } from "@/components/financeiro/detalhe-titulo";
import { FormGerarCompetencia, FormRecorrencia } from "@/components/financeiro/form-recorrencia";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { useDebounce } from "@/hooks/use-debounce";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { competencia, data } from "@/lib/format";
import type { Recorrencia, SituacaoRecorrencia } from "@/lib/tipos-financeiro";

type Filtro = "todas" | SituacaoRecorrencia;

export default function FinanceiroRecorrenciasPage() {
  const { pode } = useAuth();
  const podeEditar = pode("financeiro.recorrencias.editar");
  const [q, setQ] = useState("");
  const busca = useDebounce(q, 300);
  const [situacao, setSituacao] = useState<Filtro>("todas");
  const [form, setForm] = useState<{ r: Recorrencia | null } | null>(null);
  const [gerar, setGerar] = useState<Recorrencia | null>(null);
  const [titulo, setTitulo] = useState<number | null>(null);
  useAtalhoNovo(() => podeEditar && setForm({ r: null }));
  const lista = useQuery({
    queryKey: [CHAVE, "recorrencias", situacao, busca],
    queryFn: () => api.get<Recorrencia[]>("/financeiro/recorrencias", { situacao, q: busca }),
  });

  const colunas: Coluna<Recorrencia>[] = [
    {
      id: "desc",
      titulo: "Descrição",
      celula: (r) => (
        <>
          <strong>{r.descricao}</strong>
          <p className="text-muted">
            {r.empresa_nome} · {r.direcao === "receber" ? "A receber" : "A pagar"}
          </p>
        </>
      ),
    },
    { id: "valor", titulo: "Valor por ciclo", alinhar: "direita", celula: (r) => <Dinheiro valor={r.valor_ciclo} /> },
    {
      id: "freq",
      titulo: "Frequência",
      celula: (r) => (
        <>
          {ROTULO_FREQUENCIA[r.frequencia]}
          <p className="text-muted">dia {r.dia_vencimento}</p>
        </>
      ),
    },
    {
      id: "vig",
      titulo: "Vigência",
      celula: (r) => (
        <span className="num">
          {data(r.inicio)} – {data(r.fim)}
        </span>
      ),
    },
    {
      id: "sit",
      titulo: "Situação",
      celula: (r) => (
        <div>
          <Etiqueta tom={r.situacao === "ativa" ? "green" : "neutra"}>{ROTULO_SIT_RECORRENCIA[r.situacao]}</Etiqueta>
          {r.proxima_competencia && <p className="mt-1 text-[11px] text-muted">próxima: {competencia(r.proxima_competencia)}</p>}
        </div>
      ),
    },
    {
      id: "cmd",
      titulo: "Comandos",
      alinhar: "direita",
      celula: (r) => (
        <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="outline" onClick={() => setForm({ r })}>
            Abrir / editar
          </Button>
          {podeEditar && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                if (r.situacao !== "ativa") {
                  notificar.erro("A recorrência deve estar ativa");
                  return;
                }
                setGerar(r);
              }}
            >
              Gerar competência
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        titulo="Recorrências"
        descricao="Contratos e obrigações por competência, gerados em rascunho para revisão."
        acao={podeEditar ? <Button onClick={() => setForm({ r: null })}>+ Novo registro</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar registros desta tela" }}
        chips={{
          opcoes: [
            { valor: "todas", rotulo: "Todas" },
            { valor: "ativa", rotulo: "Ativas" },
            { valor: "pausada", rotulo: "Pausadas" },
            { valor: "cancelada", rotulo: "Canceladas" },
          ],
          valor: situacao,
          onChange: (v) => setSituacao(v as Filtro),
        }}
        exportar={{
          nome: "recorrencias",
          linhas: lista.data ?? [],
          colunas: [
            { titulo: "Descrição", valor: (r) => r.descricao },
            { titulo: "Natureza", valor: (r) => (r.direcao === "receber" ? "A receber" : "A pagar") },
            { titulo: "Cliente / fornecedor", valor: (r) => r.empresa_nome },
            { titulo: "Valor por ciclo", valor: (r) => r.valor_ciclo.replace(".", ",") },
            { titulo: "Frequência", valor: (r) => ROTULO_FREQUENCIA[r.frequencia] },
            { titulo: "Início", valor: (r) => data(r.inicio) },
            { titulo: "Fim", valor: (r) => data(r.fim) },
            { titulo: "Dia do vencimento", valor: (r) => r.dia_vencimento },
            { titulo: "Situação", valor: (r) => ROTULO_SIT_RECORRENCIA[r.situacao] },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista.data}
        chave={(r) => r.id}
        onLinha={(r) => setForm({ r })}
        carregando={lista.isPending}
        vazio={{ icone: Repeat, titulo: "Nenhuma recorrência.", descricao: "Use “Novo registro” para começar." }}
      />
      <Limite>
        Um título em rascunho por competência, sem duplicar, só dentro da vigência e alinhado à frequência. A próxima competência (até 30 dias à frente) também é
        gerada sozinha, em rascunho, para revisão.
      </Limite>
      <FormRecorrencia aberto={form != null} onFechar={() => setForm(null)} recorrencia={form?.r} />
      <FormGerarCompetencia recorrencia={gerar} onFechar={() => setGerar(null)} onGerado={(t) => setTitulo(t.id)} />
      <DetalheTitulo id={titulo} onFechar={() => setTitulo(null)} />
    </>
  );
}
