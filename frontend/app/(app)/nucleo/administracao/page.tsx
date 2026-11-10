"use client";

/**
 * Núcleo › Administração (protótipo `admin()`): cartões de governança. Os que já existem no core levam às telas de
 * Configurações, ao Histórico de ações, aos Cadastros mestres (Qualidade dos dados) e ao Plano e consumo.
 */
import { ChevronRight, Database, FolderTree, Gauge, History, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";
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
  { titulo: "Usuários e perfis", texto: "Quem entra, com qual perfil e escopo de registros.", icone: ShieldCheck, href: "/configuracoes/usuarios", recurso: "configuracoes" },
  { titulo: "Configuração da IA", texto: "Provedor, modelo e chave cifrada. Sem IA, o produto segue útil.", icone: Sparkles, href: "/configuracoes/ia", recurso: "configuracoes" },
  { titulo: "Categorias e contas", texto: "Plano de categorias, centros de custo e contas financeiras.", icone: FolderTree, href: "/financeiro/categorias", recurso: "financeiro.cadastros" },
  { titulo: "Auditoria", texto: "Histórico de ações: autor, data, antes e depois.", icone: History, href: "/nucleo/historico", recurso: "auditoria" },
  { titulo: "Qualidade dos dados", texto: "Duplicidades e mesclagem revisada, preservando vínculos.", icone: Database, href: "/nucleo/cadastros", recurso: "nucleo.cadastros" },
  { titulo: "Plano e consumo", texto: "Uso de IA e limites da organização.", icone: Gauge, href: "/nucleo/administracao/consumo", recurso: "nucleo.administracao" },
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
