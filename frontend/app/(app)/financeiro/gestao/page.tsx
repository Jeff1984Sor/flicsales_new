"use client";

/** Financeiro › Gestão financeira (protótipo `management(true)` + `financeSpecs`): página de referência. */
import Link from "next/link";

import { Insight } from "@/components/flic/insight";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { Button } from "@/components/ui/button";

const FLUXOS: [string, string][] = [
  ["Recebíveis", "Cliente, documento de origem, descrição, valor original, moeda, emissão, competência, vencimento, parcela, categoria, centro de custo, conta prevista, responsável e status."],
  ["Contas a pagar", "Fornecedor, documento/anexo, emissão, competência, vencimento, valor, categoria, centro de custo, conta, forma de pagamento, aprovador, aprovação e status."],
  ["Baixas parciais e totais", "Título, valor efetivo, data, conta, forma, desconto, juros/multa autorizados, comprovante, autor e histórico. Calcular saldo em aberto; valores positivos e limites validados."],
  ["Estornos e ajustes", "Baixa de origem, motivo, autor, data e movimento reverso. Preservar trilha; nunca apagar liquidação para corrigir saldo."],
  ["Recorrências e renovações", "Cliente/fornecedor, valor, frequência, início, fim, próxima competência, dia do vencimento, índice/reajuste se contratado, cancelamento e limite de geração. Sem duplicar competência."],
  ["Cobrança e acordos", "Saldo, faixa de atraso, último contato, canal autorizado, disputa/contestação, promessa de pagamento, data prometida, responsável e acordo vinculado. Pausar cobrança em situações configuradas."],
  ["Caixa e transferências", "Conta, saldo inicial, data-base, entradas/saídas confirmadas, transferências entre contas e projeção por títulos abertos. Transferências não compõem receita ou despesa."],
  ["Controle e resultados", "A receber/pagar por período, inadimplência, aging, liquidações, fluxo previsto/realizado, centros de custo e projeção de caixa. DRE gerencial e margem exigem classificação e custos confiáveis."],
];

export default function FinanceiroGestaoPage() {
  return (
    <>
      <PageHeader titulo="Gestão financeira" descricao="Visão de CFO · fluxos, dados, controles e indicadores." />
      <Insight eyebrow="FLUXO DE PONTA A PONTA" titulo="Origem → aprovação → título → cobrança/pagamento → baixa → caixa → análise" />
      <Painel titulo="Catálogo de fluxos e campos necessários">
        <div className="divide-y divide-line">
          {FLUXOS.map(([t, d]) => (
            <details key={t} open className="py-3">
              <summary className="cursor-pointer font-semibold">{t}</summary>
              <p className="mt-1.5 leading-relaxed text-muted">{d}</p>
            </details>
          ))}
        </div>
      </Painel>
      <Painel titulo="O que está disponível nesta versão">
        <p>
          Recebível vindo da venda (em rascunho, sem duplicar), confirmação do rascunho, baixa parcial/total, estorno com motivo, aprovação de contas a pagar
          por alçada, transferências, recorrências por competência, cobranças e acordos, caixa, aging e auditoria persistente de cada mudança.
        </p>
        <p className="mt-3 text-xs leading-relaxed text-muted">
          Juros, multa e desconto na baixa, reajuste de recorrência, DRE gerencial, conciliação bancária, emissão fiscal e execução bancária ainda não fazem
          parte do produto. Baixas são gerenciais. Nenhuma operação bancária é executada.
        </p>
      </Painel>
      <Button render={<Link href="/nucleo/automacoes?area=financeiro" />}>Configurar automações da área</Button>
    </>
  );
}
