"use client";

/** Financeiro › Aprovações (protótipo `approvals/approvePayable`): contas a pagar pendentes; Conferir e Aprovar (alçada). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import type { Proposta } from "@/lib/tipos-comercial";
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
      <DescontosEmAprovacao />
      <Limite>
        Alçada por perfil: só quem tem permissão de aprovar (Gestor) registra a aprovação, com autor e data na auditoria.
        {!podeAprovar && " Seu perfil confere, mas não aprova."}
      </Limite>
      <DetalheTitulo id={sel} onFechar={() => setSel(null)} />
    </>
  );
}

/** Propostas com desconto aguardando aprovação interna (alçada do Financeiro) antes do envio ao cliente. */
function DescontosEmAprovacao() {
  const { pode } = useAuth();
  const qc = useQueryClient();
  const podeVer = pode("comercial.propostas.ver");
  // aprovar = PATCH de status na proposta: o servidor exige a alçada do Financeiro e a edição de propostas
  const podeAprovar = pode("financeiro.aprovacoes.editar") && pode("comercial.propostas.editar");
  const lista = useQuery({
    queryKey: ["comercial", "propostas", "em_aprovacao"],
    queryFn: () => api.get<Proposta[]>("/comercial/propostas", { status: "em_aprovacao" }),
    enabled: podeVer,
  });
  const aprovar = useMutation({
    mutationFn: (p: Proposta) => api.patch<Proposta>(`/comercial/propostas/${p.id}`, { status: "aprovada_internamente" }),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["comercial"] });
      notificar.sucesso(`Desconto aprovado: ${p.titulo} v${p.versao}`);
    },
  });

  const colunas: Coluna<Proposta>[] = [
    {
      id: "proposta",
      titulo: "Proposta",
      celula: (p) => (
        <>
          <strong>{`${p.titulo} v${p.versao}`}</strong>
          <p className="text-muted">{[p.empresa_nome, p.oportunidade_titulo].filter(Boolean).join(" · ")}</p>
        </>
      ),
    },
    {
      id: "desconto",
      titulo: "Desconto",
      alinhar: "direita",
      celula: (p) => <span className="num">{`${Number(p.desconto_pct).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`}</span>,
    },
    { id: "justificativa", titulo: "Justificativa", celula: (p) => p.justificativa_desconto ?? "—" },
    { id: "total", titulo: "Total", alinhar: "direita", celula: (p) => <Dinheiro valor={p.total} /> },
    {
      id: "cmd",
      titulo: "Comandos",
      alinhar: "direita",
      celula: (p) =>
        podeAprovar ? (
          <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
            <Button size="sm" onClick={() => aprovar.mutate(p)} disabled={aprovar.isPending}>
              Aprovar
            </Button>
          </div>
        ) : (
          <span className="text-xs text-muted">Somente conferência</span>
        ),
    },
  ];

  return (
    <Painel titulo="Descontos de propostas em aprovação" semPadding className="mt-5">
      {podeVer ? (
        <DataTable
          semCartao
          className="px-2 md:px-4"
          colunas={colunas}
          linhas={lista.data}
          chave={(p) => p.id}
          carregando={lista.isPending}
          vazio={{ icone: BadgeCheck, titulo: "Nenhum desconto aguardando aprovação.", descricao: "Proposta com desconto só é enviada depois da aprovação interna." }}
        />
      ) : (
        <p className="px-6 py-4 text-sm text-muted">Seu perfil não acessa as propostas comerciais. Peça ao gestor para liberar a leitura de propostas.</p>
      )}
    </Painel>
  );
}
