"use client";

/** Financeiro › Hoje (protótipo `home` no modo Financeiro + `quickActions`). Alt+N = novo título a receber. */
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DetalheTitulo } from "@/components/financeiro/detalhe-titulo";
import { CHAVE, Limite } from "@/components/financeiro/comum";
import { FormCobranca } from "@/components/financeiro/form-cobranca";
import { FormTitulo } from "@/components/financeiro/form-titulo";
import { FormTransferencia } from "@/components/financeiro/form-transferencia";
import { AcessoRapido } from "@/components/flic/acesso-rapido";
import { Dinheiro } from "@/components/flic/dinheiro";
import { EmptyState } from "@/components/flic/empty-state";
import { Etiqueta } from "@/components/flic/etiqueta";
import { abrirAssistente, useAtalhoNovo } from "@/components/flic/eventos";
import { Fonte } from "@/components/flic/fonte";
import { Insight } from "@/components/flic/insight";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { PageHeader } from "@/components/flic/page-header";
import { GradePaineis, Painel } from "@/components/flic/painel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, numero } from "@/lib/format";
import type { Direcao, HojeFinanceiro } from "@/lib/tipos-financeiro";

export default function FinanceiroHojePage() {
  const router = useRouter();
  const { podeVer, pode } = useAuth();
  const [novoTitulo, setNovoTitulo] = useState<Direcao | null>(null);
  const [cobranca, setCobranca] = useState<{ tituloId: number | null } | null>(null);
  const [transferir, setTransferir] = useState(false);
  const [sel, setSel] = useState<number | null>(null);
  useAtalhoNovo(() => setNovoTitulo("receber"));

  const { data: h, isPending } = useQuery({ queryKey: [CHAVE, "hoje"], queryFn: () => api.get<HojeFinanceiro>("/financeiro/hoje") });

  const rapido = [
    { rotulo: "+ A receber", onClick: () => setNovoTitulo("receber") },
    { rotulo: "+ A pagar", onClick: () => setNovoTitulo("pagar") },
    { rotulo: "+ Registrar baixa", onClick: () => router.push("/financeiro/receber") },
    ...(pode("financeiro.cobrancas.editar") ? [{ rotulo: "+ Cobrança", onClick: () => setCobranca({ tituloId: null }) }] : []),
    ...(pode("financeiro.caixa.editar") ? [{ rotulo: "+ Transferência", onClick: () => setTransferir(true) }] : []),
  ];
  const comandos: [string, string, string][] = [
    ["Conferir aprovações", "/financeiro/aprovacoes", "financeiro.aprovacoes"],
    ["Ver caixa", "/financeiro/caixa", "financeiro.caixa"],
    ["Baixas e estornos", "/financeiro/baixas", "financeiro.baixas"],
    ["Cobranças e acordos", "/financeiro/cobrancas", "financeiro.cobrancas"],
    ["Configurar automações", "/nucleo/automacoes?area=financeiro", "orquestracao.automacoes"],
  ];

  const leitura = h?.leitura;
  return (
    <>
      <PageHeader titulo="Sua operação financeira, em um só lugar." descricao="Priorize cobranças, aprovações e próximos vencimentos." />
      <AcessoRapido itens={rapido} />

      {isPending || !leitura ? (
        <Skeleton className="mb-[25px] h-28 w-full rounded-[10px]" />
      ) : (
        <Insight
          titulo={leitura.titulo}
          texto={`${leitura.analise} Próxima ação: ${leitura.proxima_acao}`}
          iaDesligada={!h.ia_ligada}
          acao={{
            rotulo: "Entender e agir",
            onClick: () => {
              const ev = leitura.evidencias[0]?.registro;
              if (ev?.tipo === "titulo") setSel(ev.id);
              else abrirAssistente("Este módulo");
            },
          }}
        >
          <Fonte evidencia={leitura.evidencias.slice(0, 3).map((e) => e.texto)} fonte={leitura.evidencias[0]?.fonte} limite={leitura.limites} />
        </Insight>
      )}

      <Metricas>
        {/* o servidor só manda saldo/aprovações/recorrências a quem tem permissão (null = esconde o KPI) */}
        {(isPending || h?.saldo_gerencial) && (
          <KpiCard
            rotulo="Saldo gerencial"
            valor={<Dinheiro valor={h?.saldo_gerencial?.valor} />}
            detalhe={h?.saldo_gerencial?.detalhe}
            formula={h?.saldo_gerencial?.formula}
            carregando={isPending}
          />
        )}
        <KpiCard
          rotulo="Recebíveis vencidos"
          valor={<Dinheiro valor={h?.recebiveis_vencidos.valor} />}
          detalhe={h?.recebiveis_vencidos.detalhe}
          formula={h?.recebiveis_vencidos.formula}
          tom={h && h.recebiveis_vencidos_qtd > 0 ? "atencao" : "padrao"}
          carregando={isPending}
        />
        {(isPending || h?.aprovacoes_pendentes != null) && (
          <KpiCard rotulo="Aprovações pendentes" valor={numero(h?.aprovacoes_pendentes)} detalhe="Contas a pagar" carregando={isPending} />
        )}
        {(isPending || h?.recorrencias_ativas != null) && (
          <KpiCard rotulo="Recorrências ativas" valor={numero(h?.recorrencias_ativas)} detalhe="Geração por competência" carregando={isPending} />
        )}
      </Metricas>

      <GradePaineis>
        <Painel titulo="Fila de cobrança" acao={h && h.fila_cobranca.length > 0 ? <Etiqueta tom="amber">{h.fila_cobranca.length} vencido(s)</Etiqueta> : undefined}>
          {isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : !h?.fila_cobranca.length ? (
            <EmptyState icone={CheckCircle2} titulo="Sem títulos vencidos." descricao="Nenhum recebível confirmado passou do vencimento." className="py-8" />
          ) : (
            <ul className="divide-y divide-line">
              {h.fila_cobranca.map((f) => (
                <li key={f.titulo_id} className="flex items-center gap-3 py-3">
                  <span className="size-2 shrink-0 rounded-full bg-amber" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <strong className="block truncate">{f.empresa_nome}</strong>
                    <p className="text-xs text-muted">
                      {f.descricao} · <Dinheiro valor={f.saldo} /> · {data(f.vencimento)} · {f.dias_atraso} dia(s)
                      {f.em_contestacao && " · em contestação"}
                    </p>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => setSel(f.titulo_id)}>
                    Abrir
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Painel>
        <Painel titulo="Comandos da gestão financeira">
          <div className="flex flex-wrap gap-2">
            {comandos
              .filter(([, , recurso]) => podeVer(recurso))
              .map(([rotulo, href]) => (
                <Button key={href} variant="outline" onClick={() => router.push(href)}>
                  {rotulo}
                </Button>
              ))}
          </div>
          {h?.limites.map((l) => (
            <Limite key={l} className="mt-5">
              {l}
            </Limite>
          ))}
        </Painel>
      </GradePaineis>

      <DetalheTitulo id={sel} onFechar={() => setSel(null)} />
      <FormTitulo aberto={novoTitulo != null} onFechar={() => setNovoTitulo(null)} direcao={novoTitulo ?? "receber"} onSalvo={(t) => setSel(t.id)} />
      <FormCobranca aberto={cobranca != null} onFechar={() => setCobranca(null)} tituloId={cobranca?.tituloId} />
      <FormTransferencia aberto={transferir} onFechar={() => setTransferir(false)} />
    </>
  );
}
