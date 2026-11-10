/**
 * TelaArquitetura — Núcleo › "Arquitetura e escopo" (protótipo `architecture`): página informativa, sem dados.
 */
import { Insight } from "@/components/flic/insight";
import { PageHeader } from "@/components/flic/page-header";
import { GradePaineis, Painel } from "@/components/flic/painel";
import { Etiqueta } from "@/components/flic/etiqueta";

const MODULOS: [string, string][] = [
  ["Comercial", "Hoje · Oportunidades · Atividades · Comunicações · Desempenho · Dashboards"],
  ["Financeiro", "Hoje · A receber · A pagar · Recorrências · Caixa · Dashboards"],
  ["Núcleo", "Cadastros · Campos · Automações · Integrações · Administração"],
];

const DECISOES: [string, string, string][] = [
  ["Manter", "Cadastro único e criação contextual", "Empresa e pessoa são compartilhadas; sem duplicar lead e cliente."],
  ["Manter", "Campos personalizados, dashboards e fluxos", "Mesmo catálogo tipado com validação e dependências."],
  ["Reajustar", "Assistentes em todas as funções", "Uma camada de IA com ferramentas especializadas, contexto e permissões; sem agente independente por tela."],
  ["Reajustar", "Desempenho e previsões", "Indicadores calculados em código; IA interpreta evidências. Previsão estatística exige histórico."],
  ["Reajustar", "Financeiro inicial", "Controle gerencial, baixas parciais, estornos e recorrências; sem escopo fiscal ou bancário inicial."],
  ["Adiar", "Captura automática de todos os canais", "Começar por notas e mensagens fornecidas; conectar cada canal após validar API, autorização e custo."],
  ["Adiar", "ERP fiscal, Open Finance e comissões complexas", "Não são necessários para validar a continuidade da venda ao recebimento."],
];

const CAMADAS: [string, string, boolean][] = [
  [
    "1. Experiência e domínio",
    "Interface única com módulos. APIs de domínio: relacionamentos, oportunidades, atividades, títulos, baixas, recorrências e caixa. Cadastros compartilham identificadores estáveis.",
    true,
  ],
  [
    "2. Dados e transações",
    "Banco relacional com isolamento por organização. Parcelas e baixas são objetos próprios; dinheiro em decimal ou centavos. Histórico, estornos e idempotência na geração de recebíveis.",
    true,
  ],
  [
    "3. Eventos e automações",
    "Outbox transacional e fila para integrações, análise de conteúdo e fluxos. Execuções rastreáveis, retentativas limitadas e prevenção de ciclos. Regras de negócio ficam no domínio.",
    false,
  ],
  [
    "4. IA e conectores",
    "Gateway de IA com ferramentas autorizadas, contexto do registro, fontes e respostas estruturadas. Assistentes especializados por capacidade. Textos importados são dados, nunca instruções para executar ações.",
    false,
  ],
];

const ENTREGAS: [string, string][] = [
  [
    "Primeira entrega utilizável",
    "Cadastro único, funil, atividades, campos personalizados, financeiro básico, dashboards, regras simples e IA contextual sobre conteúdo fornecido. Chat unificado com escopo explícito.",
  ],
  [
    "Integrações progressivas",
    "Google Calendar e Outlook, depois provedores de e-mail e WhatsApp conforme disponibilidade e validação. Cada conexão tem escopos, estado e falhas visíveis.",
  ],
  [
    "Evolução com evidência de uso",
    "Análises históricas, previsões calibradas, cenários, custos e rentabilidade. Prazo e orçamento dependem da equipe, volume, provedores e critérios de aceite.",
  ],
];

const TOM = { Manter: "green", Reajustar: "azul", Adiar: "amber" } as const;

function Detalhe({ titulo, texto, aberto }: { titulo: string; texto: string; aberto?: boolean }) {
  return (
    <details open={aberto} className="group border-b border-line py-3 last:border-0">
      <summary className="cursor-pointer text-sm font-semibold marker:text-primary">{titulo}</summary>
      <p className="mt-2 text-sm leading-relaxed text-muted">{texto}</p>
    </details>
  );
}

export function TelaArquitetura() {
  return (
    <>
      <PageHeader titulo="Arquitetura e escopo" descricao="Parecer de CTO · uma base viável para construir e evoluir." escopoIA="Toda a FlicSales" />
      <Insight
        eyebrow="DECISÃO DE ARQUITETURA"
        titulo="Três módulos de produto. Uma plataforma compartilhada."
        texto="Recomendação inicial: monólito modular, banco relacional e processamento assíncrono. Separar serviços quando escala ou isolamento justificarem."
      />
      <div className="mb-5 grid gap-5 md:grid-cols-3">
        {MODULOS.map(([t, d]) => (
          <Painel key={t} titulo={t} className="mb-0">
            <p className="text-sm text-muted">{d}</p>
          </Painel>
        ))}
      </div>
      <Painel titulo="O que manter, reajustar e adiar">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr>
                {["Decisão", "Estrutura", "Justificativa"].map((h) => (
                  <th key={h} scope="col" className="border-b border-line px-2.5 py-3.5 text-left text-[10px] font-medium tracking-[0.6px] text-muted uppercase">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DECISOES.map(([d, e, j]) => (
                <tr key={e}>
                  <td className="border-b border-line px-2.5 py-[17px]">
                    <Etiqueta tom={TOM[d as keyof typeof TOM]}>{d}</Etiqueta>
                  </td>
                  <td className="border-b border-line px-2.5 py-[17px] font-semibold">{e}</td>
                  <td className="border-b border-line px-2.5 py-[17px] text-muted">{j}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Painel>
      <GradePaineis>
        <Painel titulo="Camadas técnicas propostas">
          {CAMADAS.map(([t, x, a]) => (
            <Detalhe key={t} titulo={t} texto={x} aberto={a} />
          ))}
        </Painel>
        <Painel titulo="Entrega por etapas">
          {ENTREGAS.map(([t, x]) => (
            <Detalhe key={t} titulo={t} texto={x} aberto />
          ))}
        </Painel>
      </GradePaineis>
      <Painel titulo="Critério de aceite do primeiro produto">
        <p className="text-sm leading-relaxed">
          Criar empresa durante uma oportunidade → registrar próxima ação → fechar venda → revisar recebíveis sem duplicação → confirmar título → registrar recebimento parcial →
          conferir saldo e histórico. IA explica as evidências e prepara ações; regras financeiras preservam a integridade dos valores.
        </p>
        <p className="mt-3 text-sm text-muted">
          Autenticação, isolamento por organização, auditoria, persistência, IA e conectores são implementados e testados no produto; o protótipo navegável segue como referência de navegação.
        </p>
      </Painel>
    </>
  );
}
