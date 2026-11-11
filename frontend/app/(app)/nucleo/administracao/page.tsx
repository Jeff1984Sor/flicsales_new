"use client";

/**
 * Núcleo › Administração (protótipo `admin()`): cartões de governança, nesta ordem: Usuários e perfis · Identidade ·
 * Categorias e contas · Qualidade dos dados · Governança de ajustes. Configuração da IA e Plano e consumo moram no
 * módulo Assistente; a Auditoria fica no menu lateral do Núcleo.
 */
import { ChevronRight, Database, FolderTree, ListTree, Palette, ShieldCheck, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { Etiqueta } from "@/components/flic/etiqueta";
import { PageHeader } from "@/components/flic/page-header";
import { useAuth } from "@/lib/auth";

interface Cartao {
  titulo: string;
  texto: string;
  icone: LucideIcon;
  href?: string;
  recurso?: string;
}

const CARTOES: Cartao[] = [
  { titulo: "Usuários e perfis", texto: "Quem entra, com qual perfil e escopo de registros. E-mail de envio.", icone: ShieldCheck, href: "/configuracoes/usuarios", recurso: "nucleo.administracao" },
  { titulo: "Identidade", texto: "Nome, logo, cores e assinatura padrão de e-mail.", icone: Palette, href: "/configuracoes/identidade", recurso: "configuracoes" },
  { titulo: "Categorias e contas", texto: "Plano de categorias, centros de custo e contas financeiras.", icone: FolderTree, href: "/financeiro/categorias", recurso: "financeiro.cadastros" },
  { titulo: "Qualidade dos dados", texto: "Duplicidades e mesclagem revisada, preservando vínculos.", icone: Database, href: "/nucleo/cadastros", recurso: "nucleo.cadastros" },
  {
    titulo: "Governança de ajustes",
    texto: "Segmentos, portes, motivos de perda, produtos e serviços e modelos de e-mail.",
    icone: ListTree,
    href: "/nucleo/governanca",
    recurso: "nucleo.administracao",
  },
];

export default function AdministracaoPage() {
  const { podeVer } = useAuth();
  return (
    <>
      <PageHeader titulo="Administração" descricao="Governança compartilhada, sem um console para cada função." />
      <div className="grid gap-[18px] md:grid-cols-2 min-[1100px]:grid-cols-3">
        {CARTOES.map((c) => {
          const liberado = !!c.href && (!c.recurso || podeVer(c.recurso));
          const corpo = (
            <>
              <div className="mb-3 flex items-center justify-between">
                <span className="grid size-9 place-items-center rounded-[8px] bg-tint text-primary">
                  <c.icone className="size-4" />
                </span>
                {liberado ? <ChevronRight className="size-4 text-muted" /> : <Etiqueta>{c.href ? "Sem acesso" : "Em breve"}</Etiqueta>}
              </div>
              <h2 className="text-[17px] font-bold">{c.titulo}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{c.texto}</p>
            </>
          );
          return liberado ? (
            <Link key={c.titulo} href={c.href!} className="card-surface card-hover block p-6">
              {corpo}
            </Link>
          ) : (
            <div key={c.titulo} className="card-surface p-6 opacity-80">
              {corpo}
            </div>
          );
        })}
      </div>
    </>
  );
}
