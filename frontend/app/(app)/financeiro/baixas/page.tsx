"use client";

/** Financeiro › Baixas e estornos (protótipo `settlementList/reverseForm`): trilha das liquidações, sem apagar movimentos. */
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
import { useState } from "react";

import { CHAVE, LIMITE_BAIXA, Limite, ROTULO_FORMA, useInvalidarFinanceiro } from "@/components/financeiro/comum";
import { DetalheTitulo } from "@/components/financeiro/detalhe-titulo";
import { FormMotivo } from "@/components/financeiro/form-baixa";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Etiqueta } from "@/components/flic/etiqueta";
import { PageHeader } from "@/components/flic/page-header";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { useDebounce } from "@/hooks/use-debounce";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data } from "@/lib/format";
import type { Baixa } from "@/lib/tipos-financeiro";
import type { Pagina } from "@/lib/types";

type Situacao = "todas" | "confirmada" | "estornada";
const POR_PAGINA = 50;

export default function FinanceiroBaixasPage() {
  const { pode } = useAuth();
  const podeEstornar = pode("financeiro.baixas.editar");
  const invalidar = useInvalidarFinanceiro();
  const [q, setQ] = useState("");
  const busca = useDebounce(q, 300);
  const [situacao, setSituacao] = useState<Situacao>("todas");
  const [pagina, setPagina] = useState(1);
  const [estornar, setEstornar] = useState<Baixa | null>(null);
  const [titulo, setTitulo] = useState<number | null>(null);
  const lista = useQuery({
    queryKey: [CHAVE, "baixas", situacao, busca, pagina],
    queryFn: () => api.get<Pagina<Baixa>>("/financeiro/baixas", { situacao, q: busca, pagina, por_pagina: POR_PAGINA }),
    placeholderData: keepPreviousData,
  });
  const estornarM = useMutation({
    mutationFn: ({ b, motivo }: { b: Baixa; motivo: string }) => api.post<Baixa>(`/financeiro/baixas/${b.id}/estornar`, { motivo }),
    onSuccess: () => {
      invalidar();
      setEstornar(null);
      notificar.sucesso("Estorno registrado com histórico preservado");
    },
  });

  const colunas: Coluna<Baixa>[] = [
    { id: "data", titulo: "Data", celula: (b) => <span className="num">{data(b.data)}</span> },
    {
      id: "contra",
      titulo: "Contraparte",
      celula: (b) => (
        <>
          <strong>{b.empresa_nome}</strong>
          <p className="text-muted">
            {b.direcao === "receber" ? "Recebimento" : "Pagamento"} · {b.titulo_descricao}
          </p>
        </>
      ),
    },
    { id: "valor", titulo: "Valor", alinhar: "direita", celula: (b) => <Dinheiro valor={b.valor} /> },
    {
      id: "conta",
      titulo: "Conta",
      celula: (b) => (
        <>
          {b.conta_nome}
          <p className="text-muted">{ROTULO_FORMA[b.forma]}</p>
        </>
      ),
    },
    {
      id: "sit",
      titulo: "Situação",
      celula: (b) =>
        b.estornada ? (
          <div>
            <Etiqueta>Estornada</Etiqueta>
            {b.estorno_motivo && <p className="mt-1 max-w-56 text-[11px] text-muted">{b.estorno_motivo}</p>}
          </div>
        ) : (
          <Etiqueta tom="green">Confirmada</Etiqueta>
        ),
    },
    {
      id: "cmd",
      titulo: "Comando",
      alinhar: "direita",
      celula: (b) =>
        b.estornada || !podeEstornar ? (
          <span className="text-muted">—</span>
        ) : (
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              setEstornar(b);
            }}
          >
            Estornar
          </Button>
        ),
    },
  ];

  return (
    <>
      <PageHeader titulo="Baixas e estornos" descricao="Trilha das liquidações gerenciais, sem apagar movimentos." />
      <BarraFiltros
        busca={{
          valor: q,
          onChange: (v) => {
            setQ(v);
            setPagina(1);
          },
          placeholder: "Filtrar por empresa, título ou comprovante",
        }}
        chips={{
          opcoes: [
            { valor: "todas", rotulo: "Todas" },
            { valor: "confirmada", rotulo: "Confirmadas" },
            { valor: "estornada", rotulo: "Estornadas" },
          ],
          valor: situacao,
          onChange: (v) => {
            setSituacao(v as Situacao);
            setPagina(1);
          },
        }}
        exportar={{
          nome: "baixas-e-estornos",
          linhas: lista.data?.itens ?? [],
          colunas: [
            { titulo: "Data", valor: (b) => data(b.data) },
            { titulo: "Contraparte", valor: (b) => b.empresa_nome },
            { titulo: "Tipo", valor: (b) => (b.direcao === "receber" ? "Recebimento" : "Pagamento") },
            { titulo: "Título", valor: (b) => b.titulo_descricao },
            { titulo: "Valor", valor: (b) => b.valor.replace(".", ",") },
            { titulo: "Conta", valor: (b) => b.conta_nome },
            { titulo: "Situação", valor: (b) => (b.estornada ? "Estornada" : "Confirmada") },
            { titulo: "Motivo do estorno", valor: (b) => b.estorno_motivo },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista.data?.itens}
        chave={(b) => b.id}
        onLinha={(b) => setTitulo(b.titulo_id)}
        carregando={lista.isPending}
        vazio={{ icone: RotateCcw, titulo: "Nenhuma baixa registrada.", descricao: "Recebimentos e pagamentos aparecem aqui, inclusive os estornados." }}
        paginacao={lista.data ? { pagina, porPagina: POR_PAGINA, total: lista.data.total, onChange: setPagina } : undefined}
      />
      <Limite>{LIMITE_BAIXA} Corrigir é estornar: o movimento original fica preservado com motivo, autor e data.</Limite>
      <DetalheTitulo id={titulo} onFechar={() => setTitulo(null)} />
      <FormMotivo
        aberto={!!estornar}
        onFechar={() => setEstornar(null)}
        rotulo="BAIXA / ESTORNO"
        titulo="Estornar baixa"
        descricao={
          estornar && (
            <>
              {estornar.empresa_nome} · <Dinheiro valor={estornar.valor} />
            </>
          )
        }
        aviso="O título volta a ter saldo e o efeito gerencial da baixa é revertido. O movimento original fica preservado."
        botao="Confirmar estorno"
        enviando={estornarM.isPending}
        onConfirmar={(motivo) => estornar && estornarM.mutate({ b: estornar, motivo })}
      />
    </>
  );
}
