/**
 * Fonte — bloco `.source` do protótipo: evidência, fonte e limite ("o que não se sabe") de uma leitura ou resposta da IA.
 * Borda esquerda turquesa, texto 11px cinza.
 *
 * Props:
 *  - `evidencia?: string | string[]`  o que sustenta a leitura
 *  - `fonte?: string | string[]`      de onde veio (registro, nota, data)
 *  - `limite?: string | string[]`     o que não se sabe / o que a leitura não cobre
 *  - `children?`                      texto livre (substitui ou complementa as linhas acima)
 *
 * Ex.: <Fonte evidencia="Oportunidade Aurora + notas de 06/11" limite="Não existe compromisso confirmado de fechamento." />
 */
import { cn } from "@/lib/utils";

const lista = (v?: string | string[]) => (v == null ? [] : Array.isArray(v) ? v : [v]).filter(Boolean);

export function Fonte({
  evidencia,
  fonte,
  limite,
  children,
  className,
}: {
  evidencia?: string | string[];
  fonte?: string | string[];
  limite?: string | string[];
  children?: React.ReactNode;
  className?: string;
}) {
  const linhas: [string, string[]][] = [
    ["Evidência", lista(evidencia)],
    ["Fonte", lista(fonte)],
    ["Limite", lista(limite)],
  ];
  const temLinhas = linhas.some(([, v]) => v.length > 0);
  if (!temLinhas && !children) return null;
  return (
    <div className={cn("my-[17px] border-l-2 border-accent pl-3 text-[11px] leading-relaxed text-muted", className)}>
      {linhas.map(([rotulo, v]) => v.map((t, i) => <p key={`${rotulo}-${i}`}>{`${rotulo}: ${t}`}</p>))}
      {children}
    </div>
  );
}
