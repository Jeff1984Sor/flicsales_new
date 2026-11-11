"use client";

/**
 * RespostaIA — corpo da resposta no formato único (protótipo `aiText`): título, análise, "Próxima ação sugerida",
 * bloco fonte/evidência/limite, ações sugeridas e o aviso de IA desligada (leitura por regras) com link para
 * Assistente › Configurações de IA. Usado no drawer do assistente e na tela Assistente.
 */
import Link from "next/link";

import { Fonte } from "@/components/flic/fonte";
import type { RespostaIA } from "@/lib/types";

import { AcaoSugerida } from "./acao-sugerida";

export function AvisoIADesligada({ className }: { className?: string }) {
  return (
    <p className={className ?? "text-xs text-muted"}>
      IA desligada: leitura calculada pelas regras do produto.{" "}
      <Link href="/assistente/configuracoes" className="font-medium text-primary underline-offset-2 hover:underline">
        Configurar em Assistente › Configurações de IA
      </Link>
    </p>
  );
}

export function CorpoRespostaIA({ r }: { r: RespostaIA }) {
  const evidencias = r.evidencias.map((e) => e.trecho);
  const fontes = [...new Set(r.evidencias.map((e) => e.fonte))];
  return (
    <>
      <h3 className="mb-2.5 text-sm font-bold">{r.titulo || "Leitura do contexto"}</h3>
      <p className="mb-3 leading-relaxed whitespace-pre-line">{r.analise}</p>
      {r.proxima_acao && (
        <>
          <h3 className="mb-2.5 text-sm font-bold">Próxima ação sugerida</h3>
          <p className="mb-3 leading-relaxed">{r.proxima_acao}</p>
        </>
      )}
      <Fonte evidencia={evidencias} fonte={fontes} limite={r.limites} />
      {r.origem === "regras" && r.ia_ligada === false && <AvisoIADesligada className="mb-2 text-xs text-muted" />}
      {r.acoes_sugeridas.length > 0 && (
        <div className="mt-2 flex flex-wrap items-start gap-2">
          {r.acoes_sugeridas.map((a, i) => (
            <AcaoSugerida key={`${a.tipo}-${i}`} acao={a} />
          ))}
        </div>
      )}
    </>
  );
}
