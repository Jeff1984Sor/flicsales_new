"use client";

/**
 * Paleta de comandos (busca global). Abre com Enter na busca do topo (já com o termo), Ctrl/⌘+K, ou `abrirPaleta()`.
 * Por ora navega pelas telas que o perfil enxerga; cada módulo pode acrescentar resultados de registros aqui
 * (ex.: empresas, oportunidades) chamando a própria rota de busca — sempre pelo BFF.
 */
import { CircleUserRound, Moon, Sparkles, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

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
import { useAuth } from "@/lib/auth";

import { EVENTO_PALETA, abrirAssistente } from "./eventos";
import { MODULOS, TELAS_EXTRAS, gruposVisiveis } from "./nav";

export { abrirPaleta } from "./eventos";

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

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Busca global" description="Vá para qualquer tela da FlicSales">
      <Command>
        <CommandInput placeholder="Buscar empresas, negócios… ou o nome de uma tela" value={q} onValueChange={setQ} />
        <CommandList className="max-h-[420px]">
          <CommandEmpty>Nada encontrado nas telas. A busca de registros chega com cada módulo.</CommandEmpty>
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
