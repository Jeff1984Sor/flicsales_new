"use client";

/**
 * Núcleo › Administração › Plano e consumo: uso do mês da organização, contado pelo backend
 * (usuários ativos, perguntas à IA registradas, automações ativas e execuções do motor).
 */
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Fonte } from "@/components/flic/fonte";
import { KpiCard, Metricas } from "@/components/flic/kpi-card";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { SemAcesso } from "@/components/flic/sem-acesso";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { competencia } from "@/lib/format";
import type { ConsumoOrganizacao } from "@/lib/tipos-orquestracao";

export default function PlanoConsumoPage() {
  const { podeVer } = useAuth();
  const liberado = podeVer("nucleo.administracao");
  const consumo = useQuery({
    queryKey: ["orquestracao", "consumo"],
    queryFn: () => api.get<ConsumoOrganizacao>("/orquestracao/consumo"),
    enabled: liberado,
  });

  if (!liberado) return <SemAcesso />;
  const d = consumo.data;
  const carregando = consumo.isLoading;

  return (
    <>
      <PageHeader
        titulo="Plano e consumo"
        descricao="Limites de uso, recursos disponíveis e consumo de IA."
        semIA
        acao={
          <Button variant="outline" render={<Link href="/nucleo/administracao" />}>
            Voltar à Administração
          </Button>
        }
      />
      <Metricas>
        <KpiCard rotulo="Usuários ativos" valor={d?.usuarios_ativos ?? 0} carregando={carregando} detalhe="Com acesso liberado" />
        <KpiCard
          rotulo="Perguntas à IA no mês"
          valor={d?.perguntas_ia_mes ?? 0}
          carregando={carregando}
          detalhe={d ? `${d.perguntas_ia_com_provedor_mes} respondidas pelo provedor de IA` : undefined}
          formula="Mensagens registradas no assistente desde o dia 1º do mês"
        />
        <KpiCard rotulo="Automações ativas" valor={d?.automacoes_ativas ?? 0} carregando={carregando} detalhe="Avaliadas pelo motor" />
        <KpiCard
          rotulo="Execuções no mês"
          valor={d?.execucoes_mes ?? 0}
          carregando={carregando}
          detalhe="Testes sem execução não contam"
        />
      </Metricas>
      <Painel titulo="Como ler estes números">
        <p className="text-sm leading-relaxed text-muted">
          Contagem do mês {d ? competencia(d.competencia) : "atual"}, no fuso de São Paulo. Perguntas respondidas por regras
          (IA desligada) entram no total, mas não consomem o provedor de IA.
        </p>
        <Fonte>Fonte: assistente, automações e usuários desta organização. Limites contratuais do plano ainda não são cobrados aqui.</Fonte>
      </Painel>
    </>
  );
}
