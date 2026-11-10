/**
 * Exportar CSV no cliente (regra do produto): separador `;`, BOM UTF-8 (Excel abre com acento certo) e
 * neutralização de injeção de fórmula — célula que começa com `= + - @` (ou TAB/CR) ganha um apóstrofo na frente.
 */

export interface ColunaCsv<T> {
  titulo: string;
  valor: (linha: T) => string | number | boolean | null | undefined;
}

/** Neutraliza fórmula e escapa aspas/separador/quebra de linha. */
export function celulaCsv(v: string | number | boolean | null | undefined): string {
  if (v == null) return "";
  // número de verdade (inclusive negativo) não é fórmula: só troca o ponto pela vírgula decimal
  if (typeof v === "number") return Number.isFinite(v) ? String(v).replace(".", ",") : "";
  let s = typeof v === "boolean" ? (v ? "Sim" : "Não") : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  if (/[";\n\r]/.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function gerarCsv<T>(colunas: ColunaCsv<T>[], linhas: T[]): string {
  const cab = colunas.map((c) => celulaCsv(c.titulo)).join(";");
  const corpo = linhas.map((l) => colunas.map((c) => celulaCsv(c.valor(l))).join(";"));
  return "﻿" + [cab, ...corpo].join("\r\n");
}

/** Gera e baixa o arquivo (nome sem extensão vira `<nome>.csv`). */
export function baixarCsv<T>(nome: string, colunas: ColunaCsv<T>[], linhas: T[]) {
  const blob = new Blob([gerarCsv(colunas, linhas)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome.endsWith(".csv") ? nome : `${nome}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
