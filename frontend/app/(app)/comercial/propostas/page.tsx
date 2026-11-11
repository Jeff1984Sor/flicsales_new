"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useState } from "react";

import { GerarPropostaDrawer } from "@/components/comercial/gerar-proposta";
import { PropostaDrawer, rotuloStatusProposta as rotuloStatus, tomStatusProposta as tomStatus } from "@/components/comercial/proposta-drawer";
import { PropostaForm } from "@/components/comercial/proposta-form";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, decimal } from "@/lib/format";
import { type Proposta, STATUS_PROPOSTA } from "@/lib/tipos-comercial";

export default function PropostasPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.propostas.editar");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("todos");
  const [form, setForm] = useState<{ aberto: boolean; proposta: Proposta | null }>({ aberto: false, proposta: null });
  const [doc, setDoc] = useState<Proposta | null>(null);
  const [gerar, setGerar] = useState(false);
  useAtalhoNovo(() => editar && setForm({ aberto: true, proposta: null }));

  const { data: lista, isPending } = useQuery({
    queryKey: ["comercial", "propostas", q, status],
    queryFn: () => api.get<Proposta[]>("/comercial/propostas", { q, status: status === "todos" ? undefined : status }),
  });

  const colunas: Coluna<Proposta>[] = [
    {
      id: "titulo",
      titulo: "Título",
      celula: (p) => (
        <>
          <strong>{p.titulo}</strong>
          <p className="text-muted">{p.oportunidade_titulo}</p>
        </>
      ),
    },
    { id: "empresa", titulo: "Empresa", celula: (p) => p.empresa_nome ?? "—" },
    { id: "versao", titulo: "Versão", celula: (p) => <span className="num">v{p.versao}</span> },
    { id: "total", titulo: "Total", alinhar: "direita", celula: (p) => <Dinheiro valor={p.total} /> },
    { id: "validade", titulo: "Validade", celula: (p) => data(p.validade) },
    { id: "status", titulo: "Status", celula: (p) => <Etiqueta tom={tomStatus(p.status)}>{rotuloStatus(p.status)}</Etiqueta> },
    {
      id: "cmd",
      titulo: "Comandos",
      celula: (p) => (
        <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
          {editar && (
            <Button size="sm" variant="outline" onClick={() => setForm({ aberto: true, proposta: p })}>
              Abrir / editar
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => setDoc(p)}>
            Ver documento
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        titulo="Propostas"
        descricao="Escopo, condições, versões e aprovação de desconto."
        acoes={
          editar ? (
            <Button variant="outline" onClick={() => setGerar(true)}>
              <span className="text-accent">✧</span> Gerar proposta
            </Button>
          ) : undefined
        }
        acao={editar ? <Button onClick={() => setForm({ aberto: true, proposta: null })}>+ Novo registro</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar registros desta tela" }}
        chips={{ opcoes: [{ valor: "todos", rotulo: "Todos" }, ...STATUS_PROPOSTA.map((s) => ({ valor: s.valor, rotulo: s.rotulo }))], valor: status, onChange: setStatus }}
        exportar={{
          nome: "propostas",
          linhas: lista ?? [],
          colunas: [
            { titulo: "Título", valor: (p: Proposta) => p.titulo },
            { titulo: "Oportunidade", valor: (p: Proposta) => p.oportunidade_titulo ?? "" },
            { titulo: "Empresa", valor: (p: Proposta) => p.empresa_nome ?? "" },
            { titulo: "Versão", valor: (p: Proposta) => p.versao },
            { titulo: "Total", valor: (p: Proposta) => decimal(p.total) },
            { titulo: "Validade", valor: (p: Proposta) => data(p.validade) },
            { titulo: "Status", valor: (p: Proposta) => rotuloStatus(p.status) },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista}
        chave={(p) => p.id}
        onLinha={setDoc}
        carregando={isPending}
        vazio={{ icone: FileText, titulo: "Nenhuma proposta ainda.", descricao: "Use “Novo registro” para começar." }}
      />
      <p className="text-xs text-muted">
        Registrar “Aceita” não fecha a oportunidade automaticamente. Use o fechamento para revisar o financeiro. Não há assinatura eletrônica.
      </p>

      <PropostaForm aberto={form.aberto} proposta={form.proposta} onFechar={() => setForm({ aberto: false, proposta: null })} />

      <GerarPropostaDrawer aberto={gerar} onFechar={() => setGerar(false)} aoCriar={setDoc} />
      <PropostaDrawer proposta={doc} onTrocar={setDoc} />
    </>
  );
}
