/**
 * Dinheiro — valor em R$ na fonte mono (JetBrains Mono). Aceita number ou string decimal da API ("1234.50").
 * Props:
 *  - `valor: number | string | null | undefined`  (null/vazio → "—")
 *  - `sinal?: boolean`                             mostra "+" em positivos (movimentos)
 *  - `compacto?: boolean`                          "R$ 24 mil"
 * Ex.: <Dinheiro valor={titulo.saldo} />
 * Fora de JSX, use `moeda()` de lib/format.ts.
 */
import { moeda, moedaCompacta } from "@/lib/format";
import { cn } from "@/lib/utils";

export function Dinheiro({
  valor,
  sinal,
  compacto,
  className,
}: {
  valor: number | string | null | undefined;
  sinal?: boolean;
  compacto?: boolean;
  className?: string;
}) {
  if (valor == null || valor === "") return <span className={cn("num text-muted", className)}>—</span>;
  const n = Number(valor);
  const texto = compacto ? moedaCompacta(n) : moeda(n);
  return <span className={cn("num whitespace-nowrap", className)}>{sinal && n > 0 ? `+${texto}` : texto}</span>;
}
