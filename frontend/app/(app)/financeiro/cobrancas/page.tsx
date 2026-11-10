"use client";

/** Financeiro › Cobranças e acordos (protótipo `schemas['Cobranças e acordos']`): CRUD ligado a título a receber. */
import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { useState } from "react";

import { CHAVE, EtiquetaEstado, Limite, ROTULO_CANAL, ROTULO_SIT_COBRANCA } from "@/components/financeiro/comum";
import { DetalheTitulo } from "@/components/financeiro/detalhe-titulo";
import { FormCobranca } from "@/components/financeiro/form-cobranca";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Etiqueta, type TomEtiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { useDebounce } from "@/hooks/use-debounce";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data } from "@/lib/format";
import type { Cobranca, SituacaoCobranca } from "@/lib/tipos-financeiro";

type Filtro = "todas" | SituacaoCobranca;
const TOM: Record<SituacaoCobranca, TomEtiqueta> = {
  em_acompanhamento: "azul",
  promessa_pagamento: "green",
  em_contestacao: "amber",
  resolvida: "neutra",
};

export default function FinanceiroCobrancasPage() {
  const { pode } = useAuth();
  const podeEditar = pode("financeiro.cobrancas.editar");
  const [q, setQ] = useState("");
  const busca = useDebounce(q, 300);
  const [situacao, setSituacao] = useState<Filtro>("todas");
  const [form, setForm] = useState<{ c: Cobranca | null } | null>(null);
  const [titulo, setTitulo] = useState<number | null>(null);
  useAtalhoNovo(() => podeEditar && setForm({ c: null }));
  const lista = useQuery({
    queryKey: [CHAVE, "cobrancas", situacao, busca],
    queryFn: () => api.get<Cobranca[]>("/financeiro/cobrancas", { situacao, q: busca }),
  });

  const colunas: Coluna<Cobranca>[] = [
    {
      id: "assunto",
      titulo: "Assunto",
      celula: (c) => (
        <>
          <strong>{c.assunto}</strong>
          <p className="text-muted">
            {c.empresa_nome} · {c.titulo_descricao}
          </p>
        </>
      ),
    },
    {
      id: "titulo",
      titulo: "Título a receber",
      celula: (c) => (
        <div className="flex flex-col items-start gap-1">
          <Dinheiro valor={c.titulo_saldo} />
          <EtiquetaEstado estado={c.titulo_estado} />
        </div>
      ),
    },
    {
      id: "resp",
      titulo: "Responsável",
      celula: (c) => (
        <>
          {c.responsavel_nome ?? "—"}
          <p className="text-muted">{ROTULO_CANAL[c.canal]}</p>
        </>
      ),
    },
    {
      id: "sit",
      titulo: "Situação",
      celula: (c) => (
        <div>
          <Etiqueta tom={TOM[c.situacao]}>{ROTULO_SIT_COBRANCA[c.situacao]}</Etiqueta>
          {c.situacao === "promessa_pagamento" && c.data_prometida && (
            <p className="mt-1 text-[11px] text-muted">
              prometido p/ {data(c.data_prometida)}
              {c.valor_prometido && (
                <>
                  {" · "}
                  <Dinheiro valor={c.valor_prometido} />
                </>
              )}
            </p>
          )}
        </div>
      ),
    },
    { id: "prox", titulo: "Próximo contato", celula: (c) => <span className="num">{data(c.proximo_contato)}</span> },
    {
      id: "cmd",
      titulo: "Comandos",
      alinhar: "direita",
      celula: (c) => (
        <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="outline" onClick={() => setForm({ c })}>
            Abrir / editar
          </Button>
          <Button size="sm" variant="outline" onClick={() => setTitulo(c.titulo_id)}>
            Título
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        titulo="Cobranças e acordos"
        descricao="Acompanhamento de recebíveis, promessas de pagamento e contestações."
        acao={podeEditar ? <Button onClick={() => setForm({ c: null })}>+ Novo registro</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar registros desta tela" }}
        chips={{
          opcoes: [{ valor: "todas", rotulo: "Todas" }, ...(Object.keys(ROTULO_SIT_COBRANCA) as SituacaoCobranca[]).map((s) => ({ valor: s, rotulo: ROTULO_SIT_COBRANCA[s] }))],
          valor: situacao,
          onChange: (v) => setSituacao(v as Filtro),
        }}
        exportar={{
          nome: "cobrancas-e-acordos",
          linhas: lista.data ?? [],
          colunas: [
            { titulo: "Assunto", valor: (c) => c.assunto },
            { titulo: "Empresa", valor: (c) => c.empresa_nome },
            { titulo: "Título", valor: (c) => c.titulo_descricao },
            { titulo: "Saldo do título", valor: (c) => c.titulo_saldo.replace(".", ",") },
            { titulo: "Responsável", valor: (c) => c.responsavel_nome },
            { titulo: "Canal", valor: (c) => ROTULO_CANAL[c.canal] },
            { titulo: "Situação", valor: (c) => ROTULO_SIT_COBRANCA[c.situacao] },
            { titulo: "Data prometida", valor: (c) => (c.data_prometida ? data(c.data_prometida) : "") },
            { titulo: "Valor prometido", valor: (c) => c.valor_prometido?.replace(".", ",") },
            { titulo: "Próximo contato", valor: (c) => (c.proximo_contato ? data(c.proximo_contato) : "") },
            { titulo: "Histórico / acordo", valor: (c) => c.historico },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista.data}
        chave={(c) => c.id}
        onLinha={(c) => setForm({ c })}
        carregando={lista.isPending}
        vazio={{ icone: ClipboardList, titulo: "Nenhum registro.", descricao: "Use “Novo registro” para começar." }}
      />
      <Limite>“Em contestação” suspende a cobrança automática do título. Nenhuma mensagem é enviada desta tela.</Limite>
      <FormCobranca aberto={form != null} onFechar={() => setForm(null)} cobranca={form?.c} />
      <DetalheTitulo id={titulo} onFechar={() => setTitulo(null)} />
    </>
  );
}
