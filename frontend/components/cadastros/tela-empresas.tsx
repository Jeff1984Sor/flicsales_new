"use client";

/**
 * TelaEmpresas — "Empresas e clientes" (protótipo `companyList`): lista com busca, papel e situação, Exportar CSV,
 * contagem de oportunidades e de recebíveis, atalhos "Cadastro" e "Novo contato". Usada em /comercial/empresas,
 * /financeiro/empresas e na aba Empresas de /nucleo/cadastros (`embutida` tira o cabeçalho).
 *
 * Props:
 *  - `embutida?: boolean`             sem PageHeader (dentro de outra tela)
 *  - `papelPadrao?: Papel | ""`       filtro inicial de papel
 *  - `idInicial?: number | null`      abre o drawer desta empresa (links da busca global: ?id=)
 * Usa `useSearchParams` na página: envolva a página em <Suspense>.
 */
import { useQuery } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { useState } from "react";

import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { NativeSelect } from "@/components/flic/form";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Pagina } from "@/lib/types";
import { PAPEIS, ROTULO_PAPEL, type Empresa, type Papel, type Situacao } from "@/lib/tipos-nucleo";

import { CHIPS_SITUACAO } from "./comum";
import { DrawerEmpresa } from "./drawer-empresa";
import { DrawerPessoa } from "./drawer-pessoa";

const POR_PAGINA = 50;

export function TelaEmpresas({ embutida, papelPadrao = "", idInicial = null }: { embutida?: boolean; papelPadrao?: Papel | ""; idInicial?: number | null }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.cadastros.editar");
  const [q, setQ] = useState("");
  const [papel, setPapel] = useState<Papel | "">(papelPadrao);
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [pagina, setPagina] = useState(1);
  const [aberta, setAberta] = useState<number | null>(idInicial);
  const [nova, setNova] = useState(false);
  const [contatoDe, setContatoDe] = useState<number | null>(null);
  useAtalhoNovo(() => podeEditar && setNova(true));

  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "empresas", "lista", q, papel, situacao, pagina],
    queryFn: () => api.get<Pagina<Empresa>>("/nucleo/empresas", { q, papel, situacao, pagina, por_pagina: POR_PAGINA }),
  });

  const colunas: Coluna<Empresa>[] = [
    {
      id: "empresa",
      titulo: "Empresa",
      celula: (e) => (
        <>
          <strong className="text-[13px]">{e.nome}</strong>
          <p className="text-muted">{[e.segmento, e.documento].filter(Boolean).join(" · ") || "Cadastro compartilhado"}</p>
        </>
      ),
    },
    {
      id: "papeis",
      titulo: "Papéis",
      celula: (e) => (
        <div className="flex flex-wrap gap-1">
          {!e.ativo && <Etiqueta tom="amber">Inativa</Etiqueta>}
          {e.papeis.map((p) => (
            <Etiqueta key={p}>{ROTULO_PAPEL[p]}</Etiqueta>
          ))}
        </div>
      ),
    },
    // Cadastros mestres (embutida): coluna Origem, como no protótipo
    ...(embutida ? [{ id: "origem", titulo: "Origem", celula: (e: Empresa) => e.origem || "—" }] : []),
    { id: "opp", titulo: "Oportunidades", alinhar: "direita", celula: (e) => <span className="num">{e.oportunidades}</span> },
    {
      id: "receber",
      titulo: "A receber",
      alinhar: "direita",
      celula: (e) => (
        <>
          <span className="num">{e.titulos_receber}</span>
          {Number(e.saldo_receber) > 0 && (
            <p className="text-muted">
              <Dinheiro valor={e.saldo_receber} />
            </p>
          )}
        </>
      ),
    },
    {
      id: "atalhos",
      titulo: "Atalhos",
      alinhar: "direita",
      celula: (e) => (
        <div className="flex justify-end gap-2" onClick={(ev) => ev.stopPropagation()}>
          <Button size="sm" variant="outline" onClick={() => setAberta(e.id)}>
            Cadastro
          </Button>
          {podeEditar && (
            <Button size="sm" variant="outline" onClick={() => setContatoDe(e.id)}>
              Novo contato
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      {!embutida && (
        <PageHeader
          titulo="Empresas e clientes"
          descricao="Base compartilhada. Comercial e Financeiro reutilizam os mesmos registros."
          acao={podeEditar && <Button onClick={() => setNova(true)}>+ Empresa</Button>}
        />
      )}
      <BarraFiltros
        busca={{ valor: q, onChange: (v) => (setQ(v), setPagina(1)), placeholder: "Filtrar por nome, documento ou segmento" }}
        chips={{ opcoes: CHIPS_SITUACAO, valor: situacao, onChange: (v) => (setSituacao(v as Situacao), setPagina(1)) }}
        exportar={{
          nome: "empresas",
          linhas: data?.itens ?? [],
          colunas: [
            { titulo: "Empresa", valor: (e) => e.nome },
            { titulo: "CNPJ / CPF", valor: (e) => e.documento },
            { titulo: "Segmento", valor: (e) => e.segmento },
            { titulo: "Papéis", valor: (e) => e.papeis.map((p) => ROTULO_PAPEL[p]).join(" / ") },
            { titulo: "Origem", valor: (e) => e.origem },
            { titulo: "Responsável", valor: (e) => e.responsavel_nome },
            { titulo: "E-mail financeiro", valor: (e) => e.email_financeiro },
            { titulo: "Telefone", valor: (e) => e.telefone },
            { titulo: "Oportunidades", valor: (e) => e.oportunidades },
            { titulo: "Recebíveis", valor: (e) => e.titulos_receber },
            { titulo: "Saldo a receber", valor: (e) => e.saldo_receber },
            { titulo: "Ativa", valor: (e) => (e.ativo ? "Sim" : "Não") },
          ],
        }}
      >
        <div className="w-44">
          <NativeSelect aria-label="Papel" value={papel} onChange={(e) => (setPapel(e.target.value as Papel | ""), setPagina(1))}>
            <option value="">Todos os papéis</option>
            {PAPEIS.map((p) => (
              <option key={p.valor} value={p.valor}>
                {p.rotulo}
              </option>
            ))}
          </NativeSelect>
        </div>
      </BarraFiltros>
      <DataTable
        colunas={colunas}
        linhas={data?.itens}
        chave={(e) => e.id}
        onLinha={(e) => setAberta(e.id)}
        carregando={isPending}
        vazio={{
          icone: Building2,
          titulo: q ? "Nenhuma empresa com este filtro." : "Nenhuma empresa ainda.",
          descricao: "O nome basta para começar. A empresa fica disponível nos três módulos.",
          acao: podeEditar ? <Button onClick={() => setNova(true)}>+ Empresa</Button> : undefined,
        }}
        paginacao={data && data.total > POR_PAGINA ? { pagina, porPagina: POR_PAGINA, total: data.total, onChange: setPagina } : undefined}
      />
      <DrawerEmpresa aberto={nova} onFechar={() => setNova(false)} empresaId={null} papeisIniciais={papel ? [papel] : undefined} />
      <DrawerEmpresa aberto={aberta != null} onFechar={() => setAberta(null)} empresaId={aberta} />
      <DrawerPessoa aberto={contatoDe != null} onFechar={() => setContatoDe(null)} pessoaId={null} empresaIdInicial={contatoDe} />
    </>
  );
}
