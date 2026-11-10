"use client";

/**
 * TelaTitulos — "A receber" e "A pagar" (protótipo `finance`): chips de estado (com "Vencido" derivado), busca,
 * Exportar CSV, tabela (empresa/descrição, valor original, saldo aberto, vencimento, estado [+ aprovação], comandos)
 * e drawers (detalhe, novo). Alt+N abre um novo título desta direção. `?novo=1` abre o formulário e `?titulo=<id>`
 * abre o detalhe (links do Hoje e de outras telas).
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { BarraFiltros, type OpcaoChip } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { PageHeader } from "@/components/flic/page-header";
import { Button } from "@/components/ui/button";
import { useDebounce } from "@/hooks/use-debounce";
import { api } from "@/lib/api";
import type { ColunaCsv } from "@/lib/csv";
import { data } from "@/lib/format";
import type { ContagensEstado, Direcao, FiltroEstado, Titulo } from "@/lib/tipos-financeiro";
import type { Pagina } from "@/lib/types";

import { CHAVE, EtiquetaAprovacao, EtiquetaEstado, Limite, ROTULO_ESTADO } from "./comum";
import { DetalheTitulo } from "./detalhe-titulo";
import { FormTitulo } from "./form-titulo";

const CHIPS: { valor: FiltroEstado; rotulo: string }[] = [
  { valor: "todos", rotulo: "Todos" },
  { valor: "aberto", rotulo: "Aberto" },
  { valor: "rascunho", rotulo: "Rascunho" },
  { valor: "parcial", rotulo: "Parcial" },
  { valor: "liquidado", rotulo: "Liquidado" },
  { valor: "cancelado", rotulo: "Cancelado" },
  { valor: "vencido", rotulo: "Vencido" },
];

const POR_PAGINA = 50;

export function TelaTitulos({ direcao }: { direcao: Direcao }) {
  const pagar = direcao === "pagar";
  const params = useSearchParams();
  const router = useRouter();
  const [q, setQ] = useState("");
  const busca = useDebounce(q, 300);
  const [estado, setEstado] = useState<FiltroEstado>("todos");
  const [pagina, setPagina] = useState(1);
  const [sel, setSel] = useState<number | null>(null);
  const [novo, setNovo] = useState(false);
  useAtalhoNovo(() => setNovo(true));

  // links vindos de outras telas: ?novo=1 / ?id=<id> (busca global, IA) / ?titulo=<id> (compatibilidade)
  const pNovo = params.get("novo");
  const pTitulo = params.get("id") ?? params.get("titulo");
  useEffect(() => {
    if (!pNovo && !pTitulo) return;
    // abre o drawer pedido pelo link e limpa a URL (estado derivado de parâmetro externo)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (pNovo) setNovo(true);
    if (pTitulo) setSel(Number(pTitulo));
    router.replace(pagar ? "/financeiro/pagar" : "/financeiro/receber", { scroll: false });
  }, [pNovo, pTitulo, pagar, router]);

  const lista = useQuery({
    queryKey: [CHAVE, "titulos", direcao, estado, busca, pagina],
    queryFn: () => api.get<Pagina<Titulo>>("/financeiro/titulos", { direcao, estado, q: busca, pagina, por_pagina: POR_PAGINA }),
    placeholderData: keepPreviousData,
  });
  const contagens = useQuery({
    queryKey: [CHAVE, "contagens", direcao, busca],
    queryFn: () => api.get<ContagensEstado>("/financeiro/titulos/contagens", { direcao, q: busca }),
    placeholderData: keepPreviousData,
  });

  const chips: OpcaoChip[] = CHIPS.map((c) => ({ ...c, contagem: contagens.data?.[c.valor] }));

  const colunas: Coluna<Titulo>[] = [
    {
      id: "empresa",
      titulo: "Empresa / descrição",
      celula: (t) => (
        <>
          <strong>{t.empresa_nome}</strong>
          <p className="text-muted">
            {t.descricao}
            {t.parcela && t.parcelas_total && !t.descricao.includes(`${t.parcela}/${t.parcelas_total}`) ? ` · ${t.parcela}/${t.parcelas_total}` : ""}
          </p>
        </>
      ),
    },
    { id: "valor", titulo: "Valor original", alinhar: "direita", celula: (t) => <Dinheiro valor={t.valor_original} /> },
    { id: "saldo", titulo: "Saldo aberto", alinhar: "direita", celula: (t) => <Dinheiro valor={t.saldo} /> },
    { id: "venc", titulo: "Vencimento", celula: (t) => <span className="num">{data(t.vencimento)}</span> },
    {
      id: "estado",
      titulo: "Estado",
      celula: (t) => (
        <div className="flex flex-col items-start gap-1">
          <EtiquetaEstado estado={t.estado} />
          {pagar && t.status !== "cancelado" && <EtiquetaAprovacao aprovacao={t.aprovacao} />}
        </div>
      ),
    },
    {
      id: "cmd",
      titulo: "Comandos",
      alinhar: "direita",
      celula: (t) => (
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => {
            e.stopPropagation();
            setSel(t.id);
          }}
        >
          Abrir
        </Button>
      ),
    },
  ];

  const csv: ColunaCsv<Titulo>[] = [
    { titulo: "Empresa", valor: (t) => t.empresa_nome },
    { titulo: "Descrição", valor: (t) => t.descricao },
    { titulo: "Documento", valor: (t) => t.documento },
    { titulo: "Competência", valor: (t) => t.competencia },
    { titulo: "Vencimento", valor: (t) => data(t.vencimento) },
    { titulo: "Valor original", valor: (t) => t.valor_original.replace(".", ",") },
    { titulo: "Saldo aberto", valor: (t) => t.saldo.replace(".", ",") },
    { titulo: "Estado", valor: (t) => ROTULO_ESTADO[t.estado] },
    ...(pagar ? [{ titulo: "Aprovação", valor: (t: Titulo) => (t.aprovacao === "aprovado" ? "Aprovado" : "Pendente") }] : []),
    { titulo: "Categoria", valor: (t) => t.categoria_nome },
    { titulo: "Centro de custo", valor: (t) => t.centro_custo_nome },
    { titulo: "Responsável", valor: (t) => t.responsavel_nome },
  ];

  return (
    <>
      <PageHeader
        titulo={pagar ? "A pagar" : "A receber"}
        descricao="Lançamentos, vencimentos, baixas, histórico e responsáveis."
        acao={<Button onClick={() => setNovo(true)}>+ Lançamento</Button>}
      />
      <BarraFiltros
        busca={{
          valor: q,
          onChange: (v) => {
            setQ(v);
            setPagina(1);
          },
          placeholder: "Filtrar registros desta tela",
        }}
        chips={{
          opcoes: chips,
          valor: estado,
          onChange: (v) => {
            setEstado(v as FiltroEstado);
            setPagina(1);
          },
        }}
        exportar={{ nome: pagar ? "a-pagar" : "a-receber", colunas: csv, linhas: lista.data?.itens ?? [] }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista.data?.itens}
        chave={(t) => t.id}
        onLinha={(t) => setSel(t.id)}
        carregando={lista.isPending}
        vazio={{
          titulo: estado === "todos" && !busca ? "Nenhum lançamento ainda." : "Nada com estes filtros.",
          descricao: pagar ? "Registre obrigações para acompanhar vencimentos e aprovações." : "Vendas ganhas chegam aqui como recebíveis em rascunho.",
          acao: <Button onClick={() => setNovo(true)}>+ Lançamento</Button>,
        }}
        paginacao={lista.data ? { pagina, porPagina: POR_PAGINA, total: lista.data.total, onChange: setPagina } : undefined}
      />
      <Limite>Saldo calculado sobre baixas gerenciais. Nenhuma operação bancária, emissão fiscal ou conciliação automática.</Limite>
      <DetalheTitulo id={sel} onFechar={() => setSel(null)} />
      <FormTitulo aberto={novo} onFechar={() => setNovo(false)} direcao={direcao} onSalvo={(t) => setSel(t.id)} />
    </>
  );
}
