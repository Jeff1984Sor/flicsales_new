const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const brlCompact = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});
const num = new Intl.NumberFormat("pt-BR");
const dec2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const toNum = (v: string | number | null | undefined) => (v == null || v === "" ? 0 : Number(v));

export const moeda = (v: string | number | null | undefined) => brl.format(toNum(v));
export const moedaCompacta = (v: string | number | null | undefined) => brlCompact.format(toNum(v));
export const numero = (v: string | number | null | undefined) => num.format(toNum(v));
export const decimal = (v: string | number | null | undefined) => dec2.format(toNum(v));
/** Alíquota guardada como fração (0.05) → "5,00%". */
export const aliquota = (v: string | number | null | undefined) => `${dec2.format(toNum(v) * 100)}%`;
export const percentual = (v: number | null | undefined, casas = 1) =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toLocaleString("pt-BR", { maximumFractionDigits: casas })}%`;

const soDigitos = (v: string | null | undefined) => (v ?? "").replace(/\D/g, "");

export function documento(v: string | null | undefined) {
  const d = soDigitos(v);
  if (d.length === 11) return d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
  if (d.length === 14) return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
  return v ?? "—";
}

export function cep(v: string | null | undefined) {
  const d = soDigitos(v);
  return d.length === 8 ? `${d.slice(0, 5)}-${d.slice(5)}` : (v ?? "");
}

function parseData(v: string) {
  // "YYYY-MM-DD" puro é data local, não UTC.
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return new Date(`${v}T00:00:00`);
  // a API grava em UTC; sem fuso explícito, tratamos como UTC (não como hora local)
  if (/T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(v)) return new Date(`${v}Z`);
  return new Date(v);
}

/**
 * Data-de-dia ("AAAA-MM-DD", vencimento, competência…) → "DD/MM/AAAA", formatada DA STRING (nunca `new Date()`,
 * que desloca um dia por fuso). Instantes (com hora) caem no `toLocaleDateString` no fuso de negócio.
 */
export function data(v: string | null | undefined) {
  if (!v) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v.slice(0, 10));
  if (m && v.length === 10) return `${m[3]}/${m[2]}/${m[1]}`;
  return parseData(v).toLocaleDateString("pt-BR", { timeZone: FUSO });
}

/** Competência "AAAA-MM" → "11/2026". */
export function competencia(v: string | null | undefined) {
  if (!v) return "—";
  const m = /^(\d{4})-(\d{2})/.exec(v);
  return m ? `${m[2]}/${m[1]}` : v;
}

/** Fuso de negócio do produto. */
export const FUSO = "America/Sao_Paulo";

/** Hoje no fuso de negócio, como "AAAA-MM-DD" (para comparar com datas-de-dia da API como string). */
export function hojeISO() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

/** Hoje por extenso no estilo do protótipo: "10 novembro 2026". */
export function hojeExtenso() {
  const [a, m, d] = hojeISO().split("-");
  const meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  return `${d} ${meses[Number(m) - 1]} ${a}`;
}

export function dataHora(v: string | null | undefined) {
  if (!v) return "—";
  return parseData(v).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: FUSO });
}

export function relativo(v: string | null | undefined) {
  if (!v) return "nunca";
  const diff = (Date.now() - parseData(v).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat("pt-BR", { numeric: "auto" });
  if (Math.abs(diff) < 60) return "agora";
  if (Math.abs(diff) < 3600) return rtf.format(-Math.round(diff / 60), "minute");
  if (Math.abs(diff) < 86400) return rtf.format(-Math.round(diff / 3600), "hour");
  if (Math.abs(diff) < 2592000) return rtf.format(-Math.round(diff / 86400), "day");
  return data(v);
}

export function duracao(seg: number) {
  if (!seg) return "—";
  if (seg < 60) return `${Math.round(seg)}s`;
  const m = Math.floor(seg / 60);
  const s = Math.round(seg % 60);
  return s ? `${m}min ${s}s` : `${m}min`;
}

export function tamanhoArquivo(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export function iniciais(nome: string) {
  return nome
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}
