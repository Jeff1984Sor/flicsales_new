"use client";

/**
 * CamposPersonalizados — renderiza no formulário os campos personalizados ATIVOS de um objeto (catálogo do Núcleo,
 * GET /nucleo/campos?objeto=…) com o controle certo para cada tipo (texto, número, moeda, data, sim/não, lista).
 * O valor fica em `<registro>.campos_custom[slug]`; mande o objeto inteiro no corpo (`campos_custom: valores`) — a
 * API valida tipo, opções e obrigatórios e devolve 400 com a mensagem pronta.
 *
 * Props:
 *  - `objeto: "empresa" | "pessoa" | "oportunidade"`
 *  - `valores: ValoresCampos`                         { slug: valor } (null/ausente = vazio)
 *  - `onChange: (valores: ValoresCampos) => void`     recebe o objeto inteiro já atualizado
 *  - `somenteLeitura?: boolean`                       mostra os valores em texto (detalhe do registro)
 *  - `titulo?: string | null`                         eyebrow acima dos campos (padrão "CAMPOS PERSONALIZADOS"; null esconde)
 *  - `etapaId?: number | null`                        (oportunidade) marca como obrigatório o campo exigido nesta etapa
 * Sem campos ativos para o objeto, não renderiza nada.
 *
 * Também exporta: `useCamposDoObjeto(objeto)` (lista do catálogo) e `formatarValorCampo(campo, valor)`.
 *
 * Ex.: <CamposPersonalizados objeto="empresa" valores={form.campos_custom} onChange={(v) => set("campos_custom", v)} />
 */
import { useQuery } from "@tanstack/react-query";

import { Field, NativeSelect } from "@/components/flic/form";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data as fmtData, moeda } from "@/lib/format";
import type { CampoCustom, ObjetoCampo, ValorCampo, ValoresCampos } from "@/lib/tipos-nucleo";

export function useCamposDoObjeto(objeto: ObjetoCampo) {
  const { podeVer } = useAuth();
  return useQuery({
    queryKey: ["nucleo", "campos", "objeto", objeto],
    queryFn: () => api.get<CampoCustom[]>("/nucleo/campos", { objeto }),
    enabled: podeVer("nucleo.campos"),
    staleTime: 60_000,
    meta: { silencioso: true },
  });
}

export function formatarValorCampo(campo: Pick<CampoCustom, "tipo">, valor: ValorCampo | undefined): string {
  if (valor == null || valor === "") return "—";
  if (campo.tipo === "sim_nao") return valor === true || valor === "true" ? "Sim" : "Não";
  if (campo.tipo === "moeda") return moeda(String(valor));
  if (campo.tipo === "data") return fmtData(String(valor));
  return String(valor);
}

function Controle({ campo, valor, onChange }: { campo: CampoCustom; valor: ValorCampo | undefined; onChange: (v: ValorCampo) => void }) {
  const texto = valor == null ? "" : String(valor);
  switch (campo.tipo) {
    case "lista":
      return (
        <NativeSelect value={texto} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">Selecionar</option>
          {campo.opcoes.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </NativeSelect>
      );
    case "sim_nao":
      return (
        <NativeSelect value={valor === true ? "sim" : valor === false ? "nao" : ""} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "sim")}>
          <option value="">—</option>
          <option value="sim">Sim</option>
          <option value="nao">Não</option>
        </NativeSelect>
      );
    case "data":
      return <Input type="date" className="h-9" value={texto.slice(0, 10)} onChange={(e) => onChange(e.target.value || null)} />;
    case "numero":
      return <Input type="number" className="h-9" value={texto} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} />;
    case "moeda":
      return <Input type="number" step="0.01" inputMode="decimal" className="num h-9" value={texto} onChange={(e) => onChange(e.target.value || null)} />;
    default:
      return <Input className="h-9" value={texto} onChange={(e) => onChange(e.target.value || null)} />;
  }
}

export function CamposPersonalizados({
  objeto,
  valores,
  onChange,
  somenteLeitura,
  titulo = "CAMPOS PERSONALIZADOS",
  etapaId,
}: {
  objeto: ObjetoCampo;
  valores: ValoresCampos;
  onChange?: (valores: ValoresCampos) => void;
  somenteLeitura?: boolean;
  titulo?: string | null;
  etapaId?: number | null;
}) {
  const { data } = useCamposDoObjeto(objeto);
  const campos = (data ?? []).filter((c) => !c.arquivado);
  if (campos.length === 0) return null;

  return (
    <div className="flex flex-col gap-4">
      {titulo && <div className="eyebrow">{titulo}</div>}
      {somenteLeitura ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          {campos.map((c) => (
            <div key={c.id}>
              <dt className="text-xs text-muted">{c.nome}</dt>
              <dd>{formatarValorCampo(c, valores[c.slug])}</dd>
            </div>
          ))}
        </dl>
      ) : (
        campos.map((c) => (
          <Field key={c.id} label={c.nome} obrigatorio={c.obrigatorio || (etapaId != null && c.exigido_na_etapa_id === etapaId)}>
            <Controle campo={c} valor={valores[c.slug]} onChange={(v) => onChange?.({ ...valores, [c.slug]: v })} />
          </Field>
        ))
      )}
    </div>
  );
}
