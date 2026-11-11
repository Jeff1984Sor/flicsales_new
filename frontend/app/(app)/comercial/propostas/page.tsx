"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useState } from "react";

import { useInvalidarComercial } from "@/components/comercial/dados";
import { PropostaForm } from "@/components/comercial/proposta-form";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { EnviarEmailDrawer } from "@/components/flic/enviar-email";
import { Etiqueta, type TomEtiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, decimal, moeda } from "@/lib/format";
import { type Proposta, STATUS_PROPOSTA } from "@/lib/tipos-comercial";

const rotuloStatus = (s: string) => STATUS_PROPOSTA.find((x) => x.valor === s)?.rotulo ?? s;
const tomStatus = (s: string): TomEtiqueta =>
  s === "aceita" ? "green" : s === "recusada" ? "amber" : s === "aprovada_internamente" || s === "enviada" ? "azul" : "neutra";

export default function PropostasPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.propostas.editar");
  const invalidar = useInvalidarComercial();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("todos");
  const [form, setForm] = useState<{ aberto: boolean; proposta: Proposta | null }>({ aberto: false, proposta: null });
  const [doc, setDoc] = useState<Proposta | null>(null);
  const [email, setEmail] = useState<Proposta | null>(null);
  useAtalhoNovo(() => editar && setForm({ aberto: true, proposta: null }));

  const { data: lista, isPending } = useQuery({
    queryKey: ["comercial", "propostas", q, status],
    queryFn: () => api.get<Proposta[]>("/comercial/propostas", { q, status: status === "todos" ? undefined : status }),
  });

  const duplicar = useMutation({
    mutationFn: (p: Proposta) => api.post<Proposta>(`/comercial/propostas/${p.id}/duplicar`),
    onSuccess: (p) => {
      invalidar();
      setDoc(p);
      notificar(`Versão ${p.versao} criada em rascunho`);
    },
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

      <Drawer aberto={!!doc} onFechar={() => setDoc(null)} rotulo={doc ? `PROPOSTA / VERSÃO ${doc.versao}` : undefined} titulo={doc?.titulo} descricao={doc ? `${doc.empresa_nome ?? "—"} · ${doc.responsavel_nome ?? "—"}` : undefined}>
        {doc && (
          <>
            <div className="rounded-[10px] border border-line bg-subtle p-5">
              <h3 className="text-sm font-bold">Escopo</h3>
              <p className="mt-2 text-sm whitespace-pre-wrap">{doc.escopo}</p>
              <p className="mt-4 text-sm">
                <span className="num">{decimal(doc.quantidade)}</span> × {moeda(doc.preco_unitario)} · desconto <span className="num">{decimal(doc.desconto_pct)}%</span>
              </p>
              <h2 className="mt-3 text-[29px] font-bold">
                <Dinheiro valor={doc.total} />
              </h2>
              <p className="mt-2 text-sm leading-relaxed">
                Mensalidade adicional: <Dinheiro valor={doc.mensalidade_adicional} />
                <br />
                Condição: {doc.condicao}
                <br />
                Validade: {data(doc.validade)}
              </p>
              {Number(doc.desconto_pct) > 0 && (
                <p className="mt-3 text-xs text-muted">
                  Justificativa do desconto: {doc.justificativa_desconto ?? "—"}. Desconto passa por aprovação interna antes do envio.
                </p>
              )}
            </div>
            <div className="mt-4">
              <Etiqueta tom={tomStatus(doc.status)}>{rotuloStatus(doc.status)}</Etiqueta>
            </div>
            <p className="mt-4 text-xs text-muted">O envio por e-mail fica registrado na oportunidade. Assinatura e aceite externo não estão disponíveis.</p>
            {editar && (
              <div className="mt-5 flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setForm({ aberto: true, proposta: doc });
                    setDoc(null);
                  }}
                >
                  Editar proposta
                </Button>
                <Button variant="outline" disabled={duplicar.isPending} onClick={() => duplicar.mutate(doc)}>
                  Duplicar (nova versão)
                </Button>
                <Button variant="outline" onClick={() => setEmail(doc)}>
                  ✉ Enviar e-mail
                </Button>
              </div>
            )}
          </>
        )}
      </Drawer>

      <EnviarEmailDrawer
        aberto={!!email}
        onFechar={() => setEmail(null)}
        destino={{ tipo: "proposta", id: email?.id ?? 0 }}
        empresaId={email?.empresa_id}
        oportunidadeId={email?.oportunidade_id}
        modelos="comercial"
        contexto={email ? `${email.titulo} · v${email.versao}${email.empresa_nome ? ` · ${email.empresa_nome}` : ""}` : undefined}
        assuntoInicial={email ? `Proposta: ${email.titulo}` : undefined}
        aoEnviar={() => setDoc(null)}
      />
    </>
  );
}
