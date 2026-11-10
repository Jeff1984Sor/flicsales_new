"use client";

/**
 * TelaPessoas — "Pessoas e contatos": lista com busca (nome, e-mail, cargo, empresa), situação, Exportar CSV e drawer.
 * Props: `embutida?: boolean` (sem cabeçalho) · `idInicial?: number | null` (abre o drawer; ?id= da busca global).
 */
import { useQuery } from "@tanstack/react-query";
import { Contact } from "lucide-react";
import { useState } from "react";

import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Pagina } from "@/lib/types";
import { ROTULO_CANAL, type Pessoa, type Situacao } from "@/lib/tipos-nucleo";

import { CHIPS_SITUACAO } from "./comum";
import { DrawerPessoa } from "./drawer-pessoa";
import { BotaoImportarPlanilha } from "./importar-planilha";

const POR_PAGINA = 50;

export function TelaPessoas({ embutida, idInicial = null }: { embutida?: boolean; idInicial?: number | null }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.cadastros.editar");
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [pagina, setPagina] = useState(1);
  const [aberta, setAberta] = useState<number | null>(idInicial);
  const [nova, setNova] = useState(false);
  useAtalhoNovo(() => podeEditar && setNova(true));

  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "pessoas", "lista", q, situacao, pagina],
    queryFn: () => api.get<Pagina<Pessoa>>("/nucleo/pessoas", { q, situacao, pagina, por_pagina: POR_PAGINA }),
  });

  const colunas: Coluna<Pessoa>[] = [
    {
      id: "nome",
      titulo: "Nome",
      celula: (p) => (
        <>
          <strong className="text-[13px]">{p.nome}</strong> {!p.ativo && <Etiqueta tom="amber">Inativo</Etiqueta>}
          <p className="text-muted">{p.cargo ?? "—"}</p>
        </>
      ),
    },
    { id: "empresa", titulo: "Empresa", celula: (p) => p.empresa_nome ?? <span className="text-muted">Sem empresa vinculada</span> },
    { id: "contato", titulo: "E-mail / telefone", celula: (p) => [p.email, p.telefone].filter(Boolean).join(" · ") || "—" },
    { id: "canal", titulo: "Canal preferido", celula: (p) => (p.canal_preferido ? ROTULO_CANAL[p.canal_preferido] : "—") },
    { id: "resp", titulo: "Responsável", celula: (p) => p.responsavel_nome ?? "—" },
  ];

  return (
    <>
      {!embutida && (
        <PageHeader
          titulo="Pessoas e contatos"
          descricao="Quem decide, quem influencia e como prefere ser procurado."
          acoes={<BotaoImportarPlanilha objeto="pessoas" />}
          acao={podeEditar && <Button onClick={() => setNova(true)}>+ Novo registro</Button>}
        />
      )}
      <BarraFiltros
        busca={{ valor: q, onChange: (v) => (setQ(v), setPagina(1)), placeholder: "Filtrar registros desta tela" }}
        chips={{ opcoes: CHIPS_SITUACAO, valor: situacao, onChange: (v) => (setSituacao(v as Situacao), setPagina(1)) }}
        exportar={{
          nome: "pessoas-e-contatos",
          linhas: data?.itens ?? [],
          colunas: [
            { titulo: "Nome", valor: (p) => p.nome },
            { titulo: "Empresa", valor: (p) => p.empresa_nome },
            { titulo: "Cargo / papel na compra", valor: (p) => p.cargo },
            { titulo: "E-mail", valor: (p) => p.email },
            { titulo: "Telefone / WhatsApp", valor: (p) => p.telefone },
            { titulo: "Responsável", valor: (p) => p.responsavel_nome },
            { titulo: "Canal preferido", valor: (p) => (p.canal_preferido ? ROTULO_CANAL[p.canal_preferido] : "") },
          ],
        }}
      >
        {embutida && <BotaoImportarPlanilha objeto="pessoas" />}
        {embutida && podeEditar && <Button onClick={() => setNova(true)}>+ Pessoa</Button>}
      </BarraFiltros>
      <DataTable
        colunas={colunas}
        linhas={data?.itens}
        chave={(p) => p.id}
        onLinha={(p) => setAberta(p.id)}
        carregando={isPending}
        vazio={{ icone: Contact, titulo: "Nenhum registro.", descricao: "Use “Novo registro” para começar." }}
        paginacao={data && data.total > POR_PAGINA ? { pagina, porPagina: POR_PAGINA, total: data.total, onChange: setPagina } : undefined}
      />
      <DrawerPessoa aberto={nova} onFechar={() => setNova(false)} pessoaId={null} />
      <DrawerPessoa aberto={aberta != null} onFechar={() => setAberta(null)} pessoaId={aberta} />
    </>
  );
}
