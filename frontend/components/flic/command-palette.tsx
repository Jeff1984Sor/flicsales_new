"use client";

/**
 * Paleta de comandos (busca global). Abre com Enter na busca do topo (já com o termo), Ctrl/⌘+K, ou `abrirPaleta()`.
 * Registros: com 2+ letras chama `GET /nucleo/busca?q=` (empresas, pessoas, oportunidades e títulos; máx. 5 por tipo;
 * o servidor só devolve os grupos que o perfil pode ver). Depois vêm as telas que o perfil enxerga e os atalhos.
 */
import { useQuery } from "@tanstack/react-query";
import { Building2, CircleUserRound, Contact, Handshake, Loader2, Moon, Receipt, Sparkles, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useDeferredValue, useEffect, useState } from "react";

import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { BuscaGlobal, GrupoBusca } from "@/lib/tipos-nucleo";

import { EVENTO_PALETA, abrirAssistente } from "./eventos";
import { MODULOS, TELAS_EXTRAS, gruposVisiveis } from "./nav";

export { abrirPaleta } from "./eventos";

const ICONE_GRUPO: Record<GrupoBusca["tipo"], React.ComponentType> = {
  empresas: Building2,
  pessoas: Contact,
  oportunidades: Handshake,
  titulos: Receipt,
};

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const router = useRouter();
  const { podeVer } = useAuth();
  const { setTheme, resolvedTheme } = useTheme();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const onAbrir = (e: Event) => {
      setQ((e as CustomEvent<string>).detail ?? "");
      setOpen(true);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener(EVENTO_PALETA, onAbrir);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(EVENTO_PALETA, onAbrir);
    };
  }, []);

  const ir = (href: string) => {
    setOpen(false);
    setQ("");
    router.push(href);
  };

  const extras = TELAS_EXTRAS.filter((t) => !t.recurso || podeVer(t.recurso));
  const termo = useDeferredValue(q.trim());
  const busca = useQuery({
    queryKey: ["nucleo", "busca", termo],
    queryFn: () => api.get<BuscaGlobal>("/nucleo/busca", { q: termo }),
    enabled: open && termo.length >= 2,
    staleTime: 15_000,
    meta: { silencioso: true },
  });
  const grupos = termo.length >= 2 ? (busca.data?.grupos ?? []) : [];

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Busca global" description="Vá para qualquer tela da FlicSales">
      <Command>
        <CommandInput placeholder="Buscar empresas, pessoas, oportunidades, títulos… ou o nome de uma tela" value={q} onValueChange={setQ} />
        <CommandList className="max-h-[420px]">
          <CommandEmpty>{busca.isFetching ? "Buscando registros…" : "Nada encontrado em registros nem telas."}</CommandEmpty>
          {busca.isFetching && grupos.length === 0 && (
            <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted">
              <Loader2 className="size-3.5 animate-spin" /> Buscando registros…
            </div>
          )}
          {grupos.map((g) => {
            const Icone = ICONE_GRUPO[g.tipo];
            return (
              <CommandGroup key={g.tipo} heading={g.rotulo}>
                {g.itens.map((i) => (
                  // o termo entra no `value` para o filtro da paleta não esconder o que o servidor já encontrou
                  <CommandItem key={`${g.tipo}-${i.id}`} value={`${termo} ${g.tipo} ${i.id} ${i.titulo}`} onSelect={() => ir(i.href)}>
                    <Icone />
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate">{i.titulo}</span>
                      {i.subtitulo && <span className="truncate text-[11px] text-muted">{i.subtitulo}</span>}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            );
          })}
          {MODULOS.map((m) =>
            gruposVisiveis(m, podeVer).map((g) => (
              <CommandGroup key={`${m.id}-${g.titulo}`} heading={`${m.nome} · ${g.titulo}`}>
                {g.itens
                  .filter((i) => !i.planejado)
                  .map((i) => (
                    <CommandItem key={i.href} value={`${m.nome} ${g.titulo} ${i.label}`} onSelect={() => ir(i.href)}>
                      <i.icone />
                      {i.label}
                    </CommandItem>
                  ))}
              </CommandGroup>
            )),
          )}
          {extras.length > 0 && (
            <CommandGroup heading="Núcleo · Configurações e conta">
              {extras.map((i) => (
                <CommandItem key={i.href} value={`núcleo ${i.grupo} ${i.label}`} onSelect={() => ir(i.href)}>
                  <i.icone />
                  {i.label}
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          <CommandSeparator />
          <CommandGroup heading="Atalhos">
            <CommandItem
              value="ia unificada assistente perguntar"
              onSelect={() => {
                setOpen(false);
                abrirAssistente("Toda a FlicSales");
              }}
            >
              <Sparkles />
              IA unificada
            </CommandItem>
            <CommandItem value="minha conta perfil foto senha" onSelect={() => ir("/minha-conta")}>
              <CircleUserRound />
              Minha conta
            </CommandItem>
            <CommandItem
              value="alternar tema escuro claro"
              onSelect={() => {
                setTheme(resolvedTheme === "dark" ? "light" : "dark");
                setOpen(false);
              }}
            >
              {resolvedTheme === "dark" ? <Sun /> : <Moon />}
              Alternar tema claro/escuro
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
