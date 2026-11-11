"use client";

import { ArrowLeft, Eye, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { TELAS_EXTRAS } from "@/components/flic/nav";
import { PageHeader } from "@/components/flic/page-header";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

// abas: Usuários · Perfis de acesso · E-mail (Identidade abre pelo card da Administração; a IA mora no módulo Assistente)
const ABAS = TELAS_EXTRAS.filter((i) => i.grupo === "Configurações" && i.href !== "/configuracoes");
// telas de configuração fora das abas: cabeçalho próprio com "← Administração"
const AVULSAS = TELAS_EXTRAS.filter((i) => i.grupo === "Administração" && i.href.startsWith("/configuracoes/"));
const DESCRICAO_AVULSA: Record<string, string> = {
  "/configuracoes/identidade": "Nome, logo, cores e assinatura padrão de e-mail da organização.",
};
// telas que tratam a edição item a item (listas com filtros e diálogos); nas demais o formulário inteiro fica só leitura
const EDICAO_PROPRIA = ["/configuracoes/usuarios", "/configuracoes/perfis"];

export default function ConfiguracoesLayout({ children }: { children: React.ReactNode }) {
  const { pode, podeVer } = useAuth();
  const abas = ABAS.filter((a) => !a.recurso || podeVer(a.recurso));
  const pathname = usePathname();
  const router = useRouter();
  // /configuracoes vai para a primeira aba que o perfil enxerga
  const primeira = abas[0]?.href;
  useEffect(() => {
    if (pathname === "/configuracoes" && primeira) router.replace(primeira);
  }, [pathname, primeira, router]);
  const avulsa = AVULSAS.find((a) => pathname.startsWith(a.href));
  const atual = avulsa ?? abas.find((a) => pathname.startsWith(a.href));
  const soLeitura = !!atual?.recurso && !EDICAO_PROPRIA.includes(atual.href) && !pode(`${atual.recurso}.editar`);
  // sem nenhuma aba, o bloqueio da página (AppShell) já mostra "Sem acesso"
  return (
    <div>
      {podeVer("nucleo.administracao") && (
        <Link href="/nucleo/administracao" className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-primary">
          <ArrowLeft className="size-4" />
          Administração
        </Link>
      )}
      {avulsa ? (
        <>
          <PageHeader titulo={avulsa.label} descricao={DESCRICAO_AVULSA[avulsa.href]} icone={avulsa.icone} semIA />
        </>
      ) : (
        <>
          <PageHeader titulo="Configurações" descricao="Usuários, perfis de acesso e e-mail de envio." icone={Settings} semIA />
          <nav className="-mx-1 mb-6 flex gap-1 overflow-x-auto border-b px-1">
            {abas.map((a) => {
              const on = pathname.startsWith(a.href);
              return (
                <Link
                  key={a.href}
                  href={a.href}
                  className={cn(
                    "relative flex shrink-0 items-center gap-2 px-3 pt-1 pb-3 text-sm font-medium transition-colors",
                    on ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <a.icone className={cn("size-4", on && "text-info-ink")} />
                  {a.label}
                  {on && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-primary" />}
                </Link>
              );
            })}
          </nav>
        </>
      )}
      {soLeitura ? (
        <>
          <p className="mb-4 flex items-center gap-2 rounded-xl border border-info/30 bg-info/8 px-3.5 py-2.5 text-sm text-info-ink">
            <Eye className="size-4 shrink-0" />
            Seu perfil de acesso permite consultar esta configuração, mas não alterá-la.
          </p>
          <fieldset disabled className="min-w-0">
            {children}
          </fieldset>
        </>
      ) : (
        children
      )}
    </div>
  );
}
