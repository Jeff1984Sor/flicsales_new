/**
 * Menu do FlicSales OS: 3 módulos (abas do topo) → grupos → itens (lateral escura).
 * Ordem e rótulos EXATAMENTE como no protótipo (tabela "O produto em uma tela" do CLAUDE.md).
 *
 * Cada item:
 *  - `label`     rótulo do menu
 *  - `href`      rota (App Router, em app/(app)/…)
 *  - `icone`     ícone lucide
 *  - `recurso`   recurso de permissão do backend (ex.: "comercial.oportunidades"). O item aparece se o perfil tiver
 *                `<recurso>.ver` (administrador vê tudo). O servidor confere de novo em cada chamada.
 *  - `planejado` aparece no menu com selo "em breve" e não é clicável
 *  - `exato`     ativo só na rota exata (para "Hoje", que é a raiz do módulo)
 *
 * Regra de convivência: cada módulo altera SÓ as linhas do seu módulo.
 */
import {
  ArrowLeftRight,
  BadgeCheck,
  BookOpenCheck,
  Boxes,
  Building2,
  CalendarCheck,
  ChartColumn,
  ChartNoAxesCombined,
  CircleDollarSign,
  ClipboardList,
  Compass,
  Contact,
  Database,
  FileText,
  FolderTree,
  Gauge,
  HandCoins,
  History,
  Kanban,
  Landmark,
  LayoutGrid,
  ListChecks,
  Mail,
  MessagesSquare,
  Network,
  Palette,
  Plug,
  ReceiptText,
  Repeat,
  RotateCcw,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Target,
  Truck,
  Users,
  Wallet,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export type ModuloId = "comercial" | "financeiro" | "nucleo";

export interface NavItem {
  label: string;
  href: string;
  icone: LucideIcon;
  /** Recurso de permissão (o perfil precisa de "<recurso>.ver"). Sem recurso: basta estar logado. */
  recurso?: string;
  /** Área planejada: aparece no menu com "em breve", sem link. */
  planejado?: boolean;
  /** Ativo só na rota exata. */
  exato?: boolean;
}

export interface NavGrupo {
  titulo: string;
  itens: NavItem[];
}

export interface Modulo {
  id: ModuloId;
  nome: string;
  /** Rota inicial do módulo (primeiro item). */
  inicio: string;
  grupos: NavGrupo[];
}

export const MODULOS: Modulo[] = [
  // ------------------------------------------------------------------ COMERCIAL
  {
    id: "comercial",
    nome: "Comercial",
    inicio: "/comercial",
    grupos: [
      {
        titulo: "Trabalho",
        itens: [
          { label: "Hoje", href: "/comercial", icone: Sun, recurso: "comercial.oportunidades", exato: true },
          { label: "Oportunidades", href: "/comercial/oportunidades", icone: Kanban, recurso: "comercial.oportunidades" },
          { label: "Atividades", href: "/comercial/atividades", icone: CalendarCheck, recurso: "comercial.atividades" },
          { label: "Comunicações", href: "/comercial/comunicacoes", icone: MessagesSquare, recurso: "comercial.comunicacoes" },
        ],
      },
      {
        titulo: "Gestão",
        itens: [
          { label: "Propostas", href: "/comercial/propostas", icone: FileText, recurso: "comercial.propostas" },
          { label: "Metas e forecast", href: "/comercial/metas", icone: Target, recurso: "comercial.metas" },
          { label: "Desempenho", href: "/comercial/desempenho", icone: Gauge, recurso: "comercial.desempenho" },
          { label: "Dashboards", href: "/comercial/dashboards", icone: ChartColumn, recurso: "comercial.desempenho" },
        ],
      },
      {
        titulo: "Cadastros e recursos",
        itens: [
          { label: "Empresas e clientes", href: "/comercial/empresas", icone: Building2, recurso: "nucleo.cadastros" },
          { label: "Pessoas e contatos", href: "/comercial/pessoas", icone: Contact, recurso: "nucleo.cadastros" },
          { label: "Produtos e serviços", href: "/comercial/produtos", icone: Boxes, recurso: "nucleo.cadastros" },
          { label: "Playbooks", href: "/comercial/playbooks", icone: BookOpenCheck, recurso: "comercial.recursos" },
          { label: "Modelos de comunicação", href: "/comercial/modelos", icone: Mail, recurso: "comercial.recursos" },
          { label: "Gestão comercial", href: "/comercial/gestao", icone: Compass, recurso: "comercial.recursos" },
          { label: "Assistente", href: "/comercial/assistente", icone: Sparkles, recurso: "orquestracao.ia" },
        ],
      },
    ],
  },
  // ------------------------------------------------------------------ FINANCEIRO
  {
    id: "financeiro",
    nome: "Financeiro",
    inicio: "/financeiro",
    grupos: [
      {
        titulo: "Operação",
        itens: [
          { label: "Hoje", href: "/financeiro", icone: Sun, recurso: "financeiro.titulos", exato: true },
          { label: "A receber", href: "/financeiro/receber", icone: ReceiptText, recurso: "financeiro.titulos" },
          { label: "A pagar", href: "/financeiro/pagar", icone: HandCoins, recurso: "financeiro.aprovacoes" },
          { label: "Cobranças e acordos", href: "/financeiro/cobrancas", icone: ClipboardList, recurso: "financeiro.cobrancas" },
          { label: "Recorrências", href: "/financeiro/recorrencias", icone: Repeat, recurso: "financeiro.recorrencias" },
          { label: "Caixa", href: "/financeiro/caixa", icone: Wallet, recurso: "financeiro.caixa" },
        ],
      },
      {
        titulo: "Controle",
        itens: [
          { label: "Aprovações", href: "/financeiro/aprovacoes", icone: BadgeCheck, recurso: "financeiro.aprovacoes" },
          { label: "Baixas e estornos", href: "/financeiro/baixas", icone: RotateCcw, recurso: "financeiro.baixas" },
          { label: "Transferências", href: "/financeiro/transferencias", icone: ArrowLeftRight, recurso: "financeiro.caixa" },
          { label: "Dashboards", href: "/financeiro/dashboards", icone: ChartNoAxesCombined, recurso: "financeiro.caixa" },
        ],
      },
      {
        titulo: "Cadastros e recursos",
        itens: [
          { label: "Empresas e clientes", href: "/financeiro/empresas", icone: Building2, recurso: "nucleo.cadastros" },
          { label: "Fornecedores", href: "/financeiro/fornecedores", icone: Truck, recurso: "financeiro.cadastros" },
          { label: "Categorias", href: "/financeiro/categorias", icone: FolderTree, recurso: "financeiro.cadastros" },
          { label: "Centros de custo", href: "/financeiro/centros-custo", icone: LayoutGrid, recurso: "financeiro.cadastros" },
          { label: "Contas financeiras", href: "/financeiro/contas", icone: Landmark, recurso: "financeiro.cadastros" },
          { label: "Gestão financeira", href: "/financeiro/gestao", icone: CircleDollarSign, recurso: "financeiro.cadastros" },
          { label: "Assistente", href: "/financeiro/assistente", icone: Sparkles, recurso: "orquestracao.ia" },
        ],
      },
    ],
  },
  // ------------------------------------------------------------------ NÚCLEO
  {
    id: "nucleo",
    nome: "Núcleo",
    inicio: "/nucleo/cadastros",
    grupos: [
      {
        titulo: "Plataforma",
        itens: [
          { label: "Cadastros mestres", href: "/nucleo/cadastros", icone: Database, recurso: "nucleo.cadastros" },
          { label: "Campos personalizados", href: "/nucleo/campos", icone: SlidersHorizontal, recurso: "nucleo.campos" },
          { label: "Automações", href: "/nucleo/automacoes", icone: Workflow, recurso: "orquestracao.automacoes" },
          { label: "Integrações", href: "/nucleo/integracoes", icone: Plug, recurso: "orquestracao.integracoes" },
          { label: "Administração", href: "/nucleo/administracao", icone: Settings2, recurso: "nucleo.administracao" },
          { label: "Histórico de ações", href: "/nucleo/historico", icone: History, recurso: "auditoria" },
          { label: "Assistente", href: "/nucleo/assistente", icone: Sparkles, recurso: "orquestracao.ia" },
        ],
      },
    ],
  },
];

/**
 * Telas fora do menu lateral, mas que pertencem a um módulo (breadcrumb, bloqueio por permissão e paleta de comandos).
 * Configurações do core abrem pelo menu do avatar e pela Administração do Núcleo.
 */
export const TELAS_EXTRAS: (NavItem & { modulo: ModuloId; grupo: string })[] = [
  { label: "Arquitetura e escopo", href: "/nucleo/arquitetura", icone: Network, modulo: "nucleo", grupo: "Plataforma" },
  { label: "Usuários", href: "/configuracoes/usuarios", icone: Users, recurso: "nucleo.administracao", modulo: "nucleo", grupo: "Configurações" },
  { label: "Perfis de acesso", href: "/configuracoes/perfis", icone: ShieldCheck, recurso: "nucleo.administracao", modulo: "nucleo", grupo: "Configurações" },
  { label: "Identidade", href: "/configuracoes/identidade", icone: Palette, recurso: "configuracoes", modulo: "nucleo", grupo: "Configurações" },
  { label: "Inteligência Artificial", href: "/configuracoes/ia", icone: Sparkles, recurso: "configuracoes", modulo: "nucleo", grupo: "Configurações" },
  { label: "E-mail", href: "/configuracoes/email", icone: Mail, recurso: "configuracoes", modulo: "nucleo", grupo: "Configurações" },
  { label: "Configurações", href: "/configuracoes", icone: Settings2, recurso: "configuracoes", modulo: "nucleo", grupo: "Configurações", exato: true },
  { label: "Minha conta", href: "/minha-conta", icone: ListChecks, modulo: "nucleo", grupo: "Conta" },
];

export function moduloPorId(id: ModuloId): Modulo {
  return MODULOS.find((m) => m.id === id) ?? MODULOS[0];
}

/** Módulo dono de uma rota (Configurações e Minha conta ficam no Núcleo). */
export function moduloDaRota(pathname: string): ModuloId {
  if (pathname === "/financeiro" || pathname.startsWith("/financeiro/")) return "financeiro";
  if (/^\/(nucleo|configuracoes|minha-conta)(\/|$)/.test(pathname)) return "nucleo";
  return "comercial";
}

export function ativo(pathname: string, item: NavItem) {
  if (item.planejado) return false;
  return item.exato ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
}

/** Item (do menu ou extra) que cobre o endereço — o mais específico. */
export function itemDaRota(pathname: string): (NavItem & { modulo: ModuloId; grupo: string }) | undefined {
  let melhor: (NavItem & { modulo: ModuloId; grupo: string }) | undefined;
  const candidatos = [
    ...MODULOS.flatMap((m) => m.grupos.flatMap((g) => g.itens.map((i) => ({ ...i, modulo: m.id, grupo: g.titulo })))),
    ...TELAS_EXTRAS,
  ];
  for (const i of candidatos) {
    if (i.planejado) continue;
    const cobre = i.exato ? pathname === i.href : pathname === i.href || pathname.startsWith(`${i.href}/`);
    if (cobre && (!melhor || i.href.length > melhor.href.length)) melhor = i;
  }
  return melhor;
}

/** Grupos do módulo que o perfil enxerga (`podeVer` = permissão "<recurso>.ver"). */
export function gruposVisiveis(modulo: Modulo, podeVer: (recurso: string) => boolean): NavGrupo[] {
  return modulo.grupos
    .map((g) => ({ ...g, itens: g.itens.filter((i) => !i.recurso || podeVer(i.recurso)) }))
    .filter((g) => g.itens.length > 0);
}
