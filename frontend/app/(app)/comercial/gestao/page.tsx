"use client";

import Link from "next/link";

import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { Button } from "@/components/ui/button";

const CATALOGO: [string, string][] = [
  ["Entrada e relacionamento", "Empresa, pessoa, cargo, e-mail, telefone, origem, canal, segmento, responsável, papéis e histórico. Cadastro progressivo; evitar duplicação."],
  ["Qualificação e discovery", "Necessidade, impacto, urgência, aderência ao ICP, orçamento, decisor, influenciadores, processo de compra, concorrente e critério de sucesso."],
  ["Funil e oportunidade", "Funil, etapa, responsável, equipe, carteira, valor único, valor recorrente, moeda, previsão de fechamento, probabilidade configurada, data de entrada e dias na etapa."],
  ["Proposta e negociação", "Produtos/serviços, quantidade, preço unitário, desconto, valor líquido, validade, versão, escopo, anexos, condição de pagamento, objeções e aprovação de desconto."],
  ["Execução e comunicação", "Tipo: tarefa, e-mail, ligação, WhatsApp ou reunião; assunto, responsável, prazo/início/fim, fuso, participantes, resultado, vínculo, próxima ação e fonte da comunicação."],
  ["Ganho e handoff", "Empresa, valores, condição, parcelas, recorrência, início, vencimentos, referência contratual e responsável financeiro. Gerar rascunhos com origem única; revisar antes de confirmar."],
  ["Perda e retomada", "Motivo estruturado, detalhe, concorrente, data, responsável e data de possível retomada. Manter histórico; não excluir oportunidade."],
  ["Gestão e desenvolvimento", "Metas por período e pessoa, conversão, ciclo, ticket, receita única e recorrente separadas, aging, cobertura do funil, previsões e atividades atrasadas. Comparações com amostra e fórmulas visíveis."],
];

export default function GestaoComercialPage() {
  return (
    <>
      <PageHeader titulo="Gestão comercial" descricao="Visão de CSO · relacionamento, execução, conversão e receita." />
      <section className="mb-[25px] rounded-[10px] border border-electric/20 bg-electric/5 p-[22px]">
        <span className="eyebrow">FLUXO DE PONTA A PONTA</span>
        <p className="mt-2 font-medium">Entrada → qualificação → discovery → proposta → negociação → ganho/perda → handoff → retomada</p>
      </section>
      <Painel titulo="Catálogo de fluxos e campos necessários">
        {CATALOGO.map(([t, d]) => (
          <details key={t} open className="border-b border-line py-3 last:border-0">
            <summary className="cursor-pointer text-sm font-semibold">{t}</summary>
            <p className="mt-2 text-sm leading-relaxed text-muted">{d}</p>
          </details>
        ))}
      </Painel>
      <Painel titulo="O que está disponível nesta versão">
        <p className="text-sm leading-relaxed">
          Funis configuráveis com etapas, probabilidade, limite de dias e critérios; oportunidade com qualificação completa e empresa nascendo dentro do
          registro; próxima ação, ganho com recebíveis em rascunho no Financeiro e perda com motivo, concorrente e data de retomada; atividades e
          comunicações vinculadas com análise por evidências; propostas versionadas com aprovação de desconto; metas com apuração e forecast
          ponderado; desempenho com fórmulas visíveis; dashboards com indicadores por campo personalizado; playbooks e modelos de comunicação;
          histórico compartilhado e auditoria de toda alteração.
        </p>
        <p className="mt-3 text-sm text-muted">
          Envio de mensagens, convites de agenda e assinatura de propostas dependem de conectores autorizados em Integrações. Probabilidades são
          parâmetros configurados, não previsões de IA.
        </p>
      </Painel>
      <Button render={<Link href="/nucleo/automacoes?area=comercial" />}>Configurar automações da área</Button>
    </>
  );
}
