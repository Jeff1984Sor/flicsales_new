/**
 * Utilitários das consultas públicas e do enriquecimento (sem JSX):
 *  - `mascaraCep("01310100")`         → "01310-100" (aceita digitação parcial)
 *  - `mascaraDocumento("12345678000190")` → CPF (até 11 dígitos) ou CNPJ (12–14 dígitos), parcial
 *  - `rotaAusente(erro)`               true quando a rota ainda não existe no servidor (404 genérico do FastAPI)
 *  - `mensagemConsulta(erro, alvo)`    texto curto para erro inline de CEP/CNPJ
 *  - `mesclarSugestoes(form, valores)` aplica valores sugeridos (inclui "campos_custom.<slug>") num formulário plano
 *  - `dadosParaIA(form)`               achata o formulário (campos_custom vira "campos_custom.<slug>")
 */
import { ApiError } from "@/lib/api";
import type { DadosEnriquecer, ValorEnriquecer } from "@/lib/tipos-ia";
import type { ValoresCampos } from "@/lib/tipos-nucleo";

const dig = (v: string) => v.replace(/\D/g, "");

export function mascaraCep(v: string) {
  const d = dig(v).slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
}

export function mascaraDocumento(v: string) {
  const d = dig(v).slice(0, 14);
  if (d.length <= 11) {
    return d
      .replace(/^(\d{3})(\d)/, "$1.$2")
      .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
  }
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d{1,2})$/, "$1-$2");
}

/** A rota ainda não foi publicada no servidor (404 sem mensagem de negócio). */
export function rotaAusente(e: unknown) {
  if (!(e instanceof ApiError) || e.status !== 404) return false;
  const b = e.body;
  const detail = b && typeof b === "object" && "detail" in b ? (b as { detail: unknown }).detail : null;
  return detail == null || detail === "Not Found";
}

export function mensagemConsulta(e: unknown, alvo: "CEP" | "CNPJ") {
  if (rotaAusente(e)) return `Consulta de ${alvo} ainda indisponível. Preencha à mão.`;
  if (e instanceof ApiError) {
    if (e.status === 404) return `${alvo} não encontrado.`;
    if (e.status === 400) return e.message || `${alvo} inválido.`;
    return e.message;
  }
  return `Não foi possível consultar o ${alvo}.`;
}

/** Achata o formulário para o pedido de enriquecimento: só texto, número, sim/não e vazio. */
export function dadosParaIA(form: object): DadosEnriquecer {
  const out: DadosEnriquecer = {};
  for (const [k, v] of Object.entries(form)) {
    if (k === "campos_custom" && v && typeof v === "object") {
      for (const [slug, cv] of Object.entries(v as ValoresCampos)) out[`campos_custom.${slug}`] = cv;
    } else if (v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
      out[k] = typeof v === "string" && v.trim() === "" ? null : v;
    }
  }
  return out;
}

/** Aplica sugestões ao formulário respeitando o tipo de cada campo; ignora campos que a tela não tem. */
export function mesclarSugestoes<F extends object>(form: F, valores: Record<string, ValorEnriquecer>): F {
  const out: Record<string, unknown> = { ...(form as Record<string, unknown>) };
  for (const [k, v] of Object.entries(valores)) {
    if (k.startsWith("campos_custom.")) {
      if (!("campos_custom" in out)) continue;
      out.campos_custom = { ...(out.campos_custom as ValoresCampos), [k.slice("campos_custom.".length)]: v };
      continue;
    }
    if (!(k in out)) continue;
    const atual = out[k];
    if (typeof atual === "string") out[k] = v == null ? "" : String(v);
    else if (typeof atual === "boolean") out[k] = v === true || v === "true" || v === "sim" || v === "Sim";
    else if (atual === null || typeof atual === "number") {
      if (typeof v === "number" || v === null) out[k] = v;
      else if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) out[k] = Number(v);
    }
  }
  return out as F;
}
