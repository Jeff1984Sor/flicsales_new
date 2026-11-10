"use client";

/**
 * AppShell — casca do FlicSales OS, fiel ao protótipo:
 *  - Topo branco 73px: logo `flic`+`sales` `/ OS` · abas Comercial · Financeiro · Núcleo · busca global · ✧ IA unificada · avatar
 *  - Lateral escura 232px: `WORKSPACE / <MÓDULO>`, grupos e itens (ativo azul com marcador turquesa), rodapé com lema,
 *    "● Ambiente de demonstração" (fora de prod) e "↗ Arquitetura e escopo"
 *  - Breadcrumb `Workspace / Módulo / Tela` + data de hoje
 *  - Atalhos: Alt+N → evento `flic:novo` (cada tela decide) · `/` → busca · Esc → fecha o drawer (no próprio Drawer)
 *  - A aba de módulo lembra a última tela visitada naquele módulo (localStorage)
 *  - Bloqueio leve por permissão: rota com `recurso` sem "<recurso>.ver" mostra <SemAcesso/> (o servidor já recusa os dados)
 */
import { CircleUserRound, KeyRound, LogOut, Monitor, Moon, Settings, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState, useSyncExternalStore } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";
import { EH_HML, EH_PROD } from "@/lib/env";
import { hojeExtenso } from "@/lib/format";
import { cn } from "@/lib/utils";

import { AssistenteDrawer } from "./assistente-drawer";
import { FlicLogo } from "./brand";
import { CommandPalette } from "./command-palette";
import { abrirAssistente, abrirPaleta, digitando, dispararNovo } from "./eventos";
import { MODULOS, ativo, gruposVisiveis, itemDaRota, moduloDaRota, moduloPorId, type Modulo, type ModuloId, type NavItem } from "./nav";
import { SemAcesso } from "./sem-acesso";
import { TrocarSenhaDialog } from "./trocar-senha-dialog";
import { UserAvatar } from "./user-avatar";

const CHAVE_ULTIMA = (m: ModuloId) => `flic:ultima-tela:${m}`;

function lerUltima(m: ModuloId): string | null {
  try {
    return localStorage.getItem(CHAVE_ULTIMA(m));
  } catch {
    return null;
  }
}

const nada = () => () => {};

/** Data de hoje (fuso de negócio) — só no cliente, para não divergir da renderização do servidor. */
function useHoje() {
  return useSyncExternalStore(nada, hojeExtenso, () => "");
}

export function FaixaAmbiente() {
  if (!EH_HML) return null;
  return (
    <div className="fixed inset-x-0 top-0 z-[60] flex h-[22px] items-center justify-center bg-danger px-2 text-[11px] font-bold tracking-wider text-white no-print">
      <span className="truncate">AMBIENTE DE HOMOLOGAÇÃO — dados de teste</span>
    </div>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const opcoes = [
    { v: "light", i: Sun, l: "Claro" },
    { v: "dark", i: Moon, l: "Escuro" },
    { v: "system", i: Monitor, l: "Automático" },
  ];
  return (
    <div className="flex items-center gap-0.5 rounded-[7px] bg-subtle p-0.5">
      {opcoes.map((o) => (
        <button
          key={o.v}
          type="button"
          onClick={() => setTheme(o.v)}
          className={cn("grid size-7 place-items-center rounded-[6px] text-muted transition", theme === o.v && "bg-surface text-ink shadow-sm")}
          aria-label={`Tema ${o.l}`}
          aria-pressed={theme === o.v}
          title={o.l}
        >
          <o.i className="size-3.5" />
        </button>
      ))}
    </div>
  );
}

function AbasModulo({ modulos, atual }: { modulos: Modulo[]; atual: ModuloId }) {
  const router = useRouter();
  return (
    <nav aria-label="Módulos" className="order-3 flex w-full gap-2 md:order-none md:w-auto">
      {modulos.map((m) => (
        <button
          key={m.id}
          type="button"
          aria-current={m.id === atual ? "page" : undefined}
          onClick={() => router.push(lerUltima(m.id) ?? m.inicio)}
          className={cn(
            "rounded-[7px] px-3.5 py-2.5 transition",
            m.id === atual ? "bg-tint font-bold text-primary" : "text-muted hover:text-ink",
          )}
        >
          {m.nome}
        </button>
      ))}
    </nav>
  );
}

function BuscaGlobal() {
  const [q, setQ] = useState("");
  return (
    <input
      type="search"
      data-busca-global
      value={q}
      onChange={(e) => setQ(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          abrirPaleta(q.trim());
          setQ("");
          e.currentTarget.blur();
        }
        if (e.key === "Escape") e.currentTarget.blur();
      }}
      placeholder="Buscar empresas, negócios…"
      aria-label="Busca global"
      className="ml-auto hidden w-full max-w-[180px] rounded-[7px] border border-line bg-subtle p-[11px] text-ink placeholder:text-muted md:block min-[1100px]:max-w-[290px]"
    />
  );
}

function MenuUsuario({ onTrocarSenha }: { onTrocarSenha: () => void }) {
  const { usuario, sair, podeVer } = useAuth();
  const router = useRouter();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            aria-label="Menu do usuário"
            className="ml-auto shrink-0 rounded-full md:ml-0"
          />
        }
      >
        {/* foto autenticada (fetch → blob) ou iniciais no círculo azul-claro do protótipo */}
        <UserAvatar
          nome={usuario?.nome ?? "?"}
          fotoUrl={usuario?.foto_url}
          className="size-[41px]"
          textoClassName="bg-electric/10! text-ink! text-xs"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            <span className="block truncate text-sm font-medium text-ink">{usuario?.nome}</span>
            <span className="block truncate text-xs font-normal">{usuario?.email}</span>
            <span className="mt-0.5 block truncate text-[11px] font-normal">{usuario?.perfil_acesso_nome ?? "Sem perfil"}</span>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push("/minha-conta")}>
          <CircleUserRound /> Minha conta
        </DropdownMenuItem>
        {podeVer("configuracoes") && (
          <DropdownMenuItem onClick={() => router.push("/configuracoes")}>
            <Settings /> Configurações
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={onTrocarSenha}>
          <KeyRound /> Trocar senha
        </DropdownMenuItem>
        <div className="flex items-center justify-between px-2 py-1.5">
          <span className="text-sm">Tema</span>
          <ThemeToggle />
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => void sair()} variant="destructive">
          <LogOut /> Sair
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ItemLateral({ item }: { item: NavItem }) {
  const pathname = usePathname();
  const on = ativo(pathname, item);
  const Icone = item.icone;
  const classe = cn(
    "flex w-full shrink-0 items-center gap-0 rounded-[7px] px-2.5 py-2.5 text-left text-xs whitespace-nowrap transition-colors md:my-0.5 md:px-3.5 md:py-[9px]",
    on ? "bg-primary text-white shadow-[inset_3px_0_var(--accent)]" : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-white",
    item.planejado && "cursor-not-allowed opacity-60 hover:bg-transparent",
  );
  const conteudo = (
    <>
      <Icone className={cn("mr-2.5 hidden size-[15px] shrink-0 md:inline", on ? "text-accent" : "text-sidebar-foreground")} aria-hidden />
      <span className="truncate">{item.label}</span>
      {item.planejado && <span className="ml-auto rounded bg-white/10 px-1.5 py-0.5 text-[9px] uppercase">em breve</span>}
    </>
  );
  if (item.planejado) return <span className={classe}>{conteudo}</span>;
  return (
    <Link href={item.href} className={classe} aria-current={on ? "page" : undefined}>
      {conteudo}
    </Link>
  );
}

function Lateral({ modulo }: { modulo: Modulo }) {
  const { podeVer } = useAuth();
  const grupos = gruposVisiveis(modulo, podeVer);
  return (
    <aside className="z-20 flex flex-col bg-sidebar p-2.5 text-white md:sticky md:top-[calc(var(--tb)+var(--faixa))] md:h-[calc(100dvh-var(--tb)-var(--faixa))] md:overflow-y-auto md:px-4 md:py-7 no-print">
      <small className="hidden px-3.5 text-[10px] tracking-[1.6px] text-sidebar-foreground md:block">WORKSPACE / {modulo.nome.toUpperCase()}</small>
      <nav aria-label={`Menu ${modulo.nome}`} className="flex gap-1 overflow-x-auto md:mt-[17px] md:block md:overflow-visible">
        {grupos.map((g) => (
          <div key={g.titulo} className="contents md:block">
            <span className="mx-3.5 mt-[23px] mb-2 hidden text-[9px] tracking-[1.6px] text-sidebar-foreground uppercase first:mt-0 md:block">{g.titulo}</span>
            {g.itens.map((i) => (
              <ItemLateral key={i.href} item={i} />
            ))}
          </div>
        ))}
      </nav>
      <div className="mt-auto hidden px-3.5 pt-[30px] text-xs leading-[1.7] text-sidebar-foreground md:block">
        Um contexto. Próxima ação.
        {!EH_PROD && (
          <>
            <br />
            <span className="text-accent">●</span> Ambiente de demonstração
          </>
        )}
        <br />
        <Link href="/nucleo/arquitetura" className="mt-1 inline-block text-sidebar-foreground hover:text-white">
          ↗ Arquitetura e escopo
        </Link>
      </div>
    </aside>
  );
}

function Migalhas({ modulo, tela }: { modulo: Modulo; tela: string | undefined }) {
  const hoje = useHoje();
  return (
    <div className="mb-5 flex items-center gap-3 text-xs text-muted">
      <nav aria-label="Você está em" className="min-w-0 truncate">
        Workspace <span className="mx-1.5">/</span> {modulo.nome}
        {tela && (
          <>
            <span className="mx-1.5">/</span> <span>{tela}</span>
          </>
        )}
      </nav>
      <span className="ml-auto shrink-0">{hoje}</span>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { podeVer } = useAuth();
  const [trocarSenha, setTrocarSenha] = useState(false);
  const modulosVisiveis = MODULOS.filter((m) => gruposVisiveis(m, podeVer).length > 0);
  const moduloId = moduloDaRota(pathname);
  const modulo = moduloPorId(moduloId);
  const rota = itemDaRota(pathname);
  const bloqueada = !!rota?.recurso && !podeVer(rota.recurso);

  // a aba de módulo lembra a última tela de cada módulo
  useEffect(() => {
    try {
      if (rota && rota.modulo === moduloId) localStorage.setItem(CHAVE_ULTIMA(moduloId), pathname);
    } catch {
      /* preferência visual */
    }
  }, [pathname, moduloId, rota]);

  // atalhos globais do protótipo
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && !e.ctrlKey && !e.metaKey && e.code === "KeyN") {
        e.preventDefault();
        dispararNovo();
        return;
      }
      if (digitando(e.target)) return;
      if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        const campo = document.querySelector<HTMLInputElement>("input[data-busca-global]");
        if (campo && campo.offsetParent !== null) campo.focus();
        else abrirPaleta();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <FaixaAmbiente />
      <header className="sticky top-(--faixa) z-30 flex h-auto flex-wrap items-center gap-2.5 border-b border-line bg-surface p-3 md:h-(--tb) md:flex-nowrap md:gap-[30px] md:px-7 md:py-0 no-print">
        <Link href={lerUltima(moduloId) ?? modulo.inicio} className="shrink-0 md:w-[185px]" aria-label="FlicSales OS — início do módulo">
          <FlicLogo className="text-[22px] md:text-[25px]" />
        </Link>
        <AbasModulo modulos={modulosVisiveis} atual={moduloId} />
        <BuscaGlobal />
        <button
          type="button"
          onClick={() => abrirAssistente("Toda a FlicSales")}
          className="shrink-0 rounded-[7px] border border-line bg-surface px-3.5 py-2.5 text-ink transition hover:border-primary"
        >
          <span className="text-accent">✧</span> IA unificada
        </button>
        <MenuUsuario onTrocarSenha={() => setTrocarSenha(true)} />
      </header>

      <div className="grid min-h-[calc(100dvh-var(--tb)-var(--faixa))] grid-cols-1 md:grid-cols-[232px_1fr]">
        <Lateral modulo={modulo} />
        <main id="conteudo" className="mx-auto w-full max-w-[1600px] px-3.5 py-5 md:px-[25px] md:py-[25px] min-[1100px]:px-9 min-[1100px]:py-[30px]">
          <Migalhas modulo={modulo} tela={rota?.label} />
          {bloqueada ? <SemAcesso /> : children}
        </main>
      </div>

      <CommandPalette />
      <AssistenteDrawer />
      <TrocarSenhaDialog open={trocarSenha} onOpenChange={setTrocarSenha} />
    </>
  );
}
