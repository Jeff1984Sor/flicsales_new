"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AtividadeForm } from "@/components/comercial/atividade-form";
import { CHAVE, hora, useInvalidarComercial } from "@/components/comercial/dados";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { type Coluna, DataTable } from "@/components/flic/data-table";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data } from "@/lib/format";
import { type Atividade, rotuloTipoAtividade, TIPOS_ATIVIDADE } from "@/lib/tipos-comercial";

const CHIPS = [
  { valor: "todos", rotulo: "Todos" },
  ...TIPOS_ATIVIDADE.map((t) => ({ valor: t.valor, rotulo: t.rotulo })),
  { valor: "concluida", rotulo: "Concluída" },
  { valor: "pendente", rotulo: "Pendente" },
  { valor: "atrasadas", rotulo: "Atrasadas" },
];

export default function AtividadesPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.atividades.editar");
  const invalidar = useInvalidarComercial();
  const [q, setQ] = useState("");
  const [chip, setChip] = useState("todos");
  const [form, setForm] = useState<{ aberto: boolean; atividade: Atividade | null }>({ aberto: false, atividade: null });
  useAtalhoNovo(() => editar && setForm({ aberto: true, atividade: null }));

  const filtro = {
    q,
    tipo: TIPOS_ATIVIDADE.some((t) => t.valor === chip) ? chip : undefined,
    status: chip === "concluida" || chip === "pendente" ? chip : undefined,
    atrasadas: chip === "atrasadas" ? true : undefined,
  };
  const { data: lista, isPending } = useQuery({
    queryKey: [CHAVE, "atividades", filtro],
    queryFn: () => api.get<Atividade[]>("/comercial/atividades", filtro),
  });

  const concluir = useMutation({
    mutationFn: (a: Atividade) => api.post<Atividade>(`/comercial/atividades/${a.id}/concluir`, {}),
    onSuccess: (a) => {
      invalidar();
      notificar(`Concluída: ${a.assunto}`);
    },
  });

  const colunas: Coluna<Atividade>[] = [
    {
      id: "atividade",
      titulo: "Atividade",
      celula: (a) => (
        <>
          <strong>{a.assunto}</strong>
          <p className="text-muted">
            {a.empresa_nome ?? "Sem empresa vinculada"}
            {a.oportunidade_titulo ? ` · ${a.oportunidade_titulo}` : ""}
          </p>
        </>
      ),
    },
    {
      id: "tipo",
      titulo: "Tipo",
      celula: (a) => (
        <>
          {rotuloTipoAtividade(a.tipo)}
          {a.origem !== "manual" && (
            <Etiqueta className="ml-1.5" tom="green">
              {a.origem === "ia" ? "Sugerida pela IA" : "Automação"}
            </Etiqueta>
          )}
        </>
      ),
    },
    { id: "resp", titulo: "Responsável", celula: (a) => a.responsavel_nome ?? "—" },
    {
      id: "prazo",
      titulo: "Prazo",
      celula: (a) => (
        <span className={a.atrasada ? "text-amber-ink" : undefined}>
          {data(a.prazo)}
          {a.hora_inicio && ` · ${hora(a.hora_inicio)}${a.hora_fim ? `–${hora(a.hora_fim)}` : ""}`}
        </span>
      ),
    },
    {
      id: "status",
      titulo: "Status",
      celula: (a) =>
        a.status === "concluida" ? <Etiqueta tom="green">Concluída</Etiqueta> : a.atrasada ? <Etiqueta tom="amber">Atrasada</Etiqueta> : <Etiqueta>Pendente</Etiqueta>,
    },
    {
      id: "cmd",
      titulo: "Comandos",
      alinhar: "direita",
      celula: (a) =>
        editar ? (
          <span className="inline-flex gap-1.5" onClick={(e) => e.stopPropagation()}>
            <Button variant="outline" size="sm" onClick={() => setForm({ aberto: true, atividade: a })}>
              Editar
            </Button>
            {a.status !== "concluida" && (
              <Button variant="outline" size="sm" onClick={() => concluir.mutate(a)} disabled={concluir.isPending}>
                Concluir
              </Button>
            )}
          </span>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        titulo="Atividades"
        descricao="Tarefas, e-mails, ligações, WhatsApp e reuniões no mesmo ambiente."
        acao={editar ? <Button onClick={() => setForm({ aberto: true, atividade: null })}>+ Atividade</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar atividade ou empresa" }}
        chips={{ opcoes: CHIPS, valor: chip, onChange: setChip }}
        exportar={{
          nome: "atividades",
          linhas: lista ?? [],
          colunas: [
            { titulo: "Assunto", valor: (a) => a.assunto },
            { titulo: "Tipo", valor: (a) => rotuloTipoAtividade(a.tipo) },
            { titulo: "Empresa", valor: (a) => a.empresa_nome ?? "" },
            { titulo: "Oportunidade", valor: (a) => a.oportunidade_titulo ?? "" },
            { titulo: "Responsável", valor: (a) => a.responsavel_nome ?? "" },
            { titulo: "Prazo", valor: (a) => data(a.prazo) },
            { titulo: "Status", valor: (a) => (a.status === "concluida" ? "Concluída" : "Pendente") },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista}
        chave={(a) => a.id}
        carregando={isPending}
        onLinha={editar ? (a) => setForm({ aberto: true, atividade: a }) : undefined}
        vazio={{ icone: CalendarCheck, titulo: "Nenhuma atividade por aqui.", descricao: "Uma próxima ação visível para cada relacionamento." }}
      />
      <Painel titulo="Agenda e sincronização">
        <p className="leading-relaxed">
          Google Calendar e Outlook entram por conexão autorizada em Integrações. Criar atividade não envia mensagens nem convites: o envio depende de um
          canal conectado.
        </p>
        <Button variant="outline" className="mt-4" render={<Link href="/nucleo/integracoes" />}>
          Ver integrações
        </Button>
      </Painel>
      <AtividadeForm aberto={form.aberto} atividade={form.atividade} onFechar={() => setForm({ aberto: false, atividade: null })} />
    </>
  );
}
