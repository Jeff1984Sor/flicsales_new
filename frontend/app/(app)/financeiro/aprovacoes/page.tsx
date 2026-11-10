"use client";

/** Financeiro › Aprovações (protótipo `approvals/approvePayable`): contas a pagar pendentes; Conferir e Aprovar (alçada). */
import { useMutation, useQuery } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { useState } from "react";

import { CHAVE, EtiquetaAprovacao, Limite, useInvalidarFinanceiro } from "@/components/financeiro/comum";
import { DetalheTitulo } from "@/components/financeiro/detalhe-titulo";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data } from "@/lib/format";
import type { Titulo } from "@/lib/tipos-financeiro";

type Situacao = "pendente" | "aprovado" | "todos";

export default function FinanceiroAprovacoesPage() {
  const { pode } = useAuth();
  const podeAprovar = pode("financeiro.aprovacoes.editar");
  const invalidar = useInvalidarFinanceiro();
  const [situacao, setSituacao] = useState<Situacao>("pendente");
  const [sel, setSel] = useState<number | null>(null);
  const lista = useQuery({
    queryKey: [CHAVE, "aprovacoes", situacao],
    queryFn: () => api.get<Titulo[]>("/financeiro/aprovacoes", { situacao }),
  });
  const aprovar = useMutation({
    mutationFn: (id: number) => api.post<Titulo>(`/financeiro/titulos/${id}/aprovar`),
    onSuccess: () => {
      invalidar();
      notificar.sucesso("Aprovação gerencial registrada");
    },
  });

  const colunas: Coluna<Titulo>[] = [
    {
      id: "forn",
      titulo: "Fornecedor",
      celula: (t) => (
        <>
          <strong>{t.empresa_nome}</strong>
          <p className="text-muted">{t.descricao}</p>
        </>
      ),
    },
    { id: "valor", titulo: "Valor", alinhar: "direita", celula: (t) => <Dinheiro valor={t.saldo} /> },
    { id: "venc", titulo: "Vencimento", celula: (t) => <span className="num">{data(t.vencimento)}</span> },
    {
      id: "estado",
      titulo: "Estado",
      celula: (t) => (
        <div className="flex flex-col items-start gap-1">
          <EtiquetaAprovacao aprovacao={t.aprovacao} />
          {t.aprovacao === "aprovado" && t.aprovado_por_nome && <span className="text-[11px] text-muted">por {t.aprovado_por_nome}</span>}
        </div>
      ),
    },
    {
      id: "cmd",
      titulo: "Comandos",
      alinhar: "direita",
      celula: (t) => (
        <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="outline" onClick={() => setSel(t.id)}>
            Conferir
          </Button>
          {t.aprovacao !== "aprovado" && podeAprovar && (
            <Button size="sm" onClick={() => aprovar.mutate(t.id)} disabled={aprovar.isPending}>
              Aprovar
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader titulo="Aprovações" descricao="Conferência gerencial de contas a pagar e descontos comerciais." />
      <BarraFiltros
        chips={{
          opcoes: [
            { valor: "pendente", rotulo: "Pendentes" },
            { valor: "aprovado", rotulo: "Aprovados" },
            { valor: "todos", rotulo: "Todos" },
          ],
          valor: situacao,
          onChange: (v) => setSituacao(v as Situacao),
        }}
      />
      <Painel titulo="Pagamentos pendentes" semPadding>
        <DataTable
          semCartao
          className="px-2 md:px-4"
          colunas={colunas}
          linhas={lista.data}
          chave={(t) => t.id}
          onLinha={(t) => setSel(t.id)}
          carregando={lista.isPending}
          vazio={{ icone: BadgeCheck, titulo: situacao === "pendente" ? "Nenhum pagamento aguardando aprovação." : "Nada por aqui.", descricao: "Contas a pagar só recebem baixa depois de aprovadas." }}
        />
      </Painel>
      <Limite>
        Alçada por perfil: só quem tem permissão de aprovar (Gestor) registra a aprovação, com autor e data na auditoria.
        {!podeAprovar && " Seu perfil confere, mas não aprova."} Descontos comerciais em aprovação aparecem em Comercial › Propostas.
      </Limite>
      <DetalheTitulo id={sel} onFechar={() => setSel(null)} />
    </>
  );
}
