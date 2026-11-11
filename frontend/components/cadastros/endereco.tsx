"use client";

/**
 * BlocoEndereco — endereço estruturado de empresa e pessoa. CEP com máscara 00000-000; ao completar 8 dígitos busca o
 * CEP no servidor (`GET /bff/nucleo/consultas/cep/{cep}`), preenche logradouro, bairro, cidade e UF e leva o foco para
 * "Número". Erro aparece embaixo do CEP, sem toast.
 *
 * Props:
 *  - `valor: ValorEndereco`                               os 7 campos como texto ("" = vazio)
 *  - `onChange: (parcial: Partial<ValorEndereco>) => void` só o que mudou (o pai mescla no formulário)
 *  - `disabled?: boolean`                                 somente leitura (sem permissão ou endereço da empresa)
 *  - `dica?: ReactNode`                                   linha cinza abaixo do bloco
 *  - `obrigatorio?: (campo) => boolean`                   marca "*" (campos padrões de "Campos de dados")
 *
 * Utilitários: `ENDERECO_VAZIO`, `enderecoDe(registro)` (null → "").
 */
import { Loader2 } from "lucide-react";
import { useRef, useState } from "react";

import { Field } from "@/components/flic/form";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { CampoEndereco, ConsultaCep, Endereco } from "@/lib/tipos-nucleo";

import { mascaraCep, mensagemConsulta } from "./consultas";

export type ValorEndereco = Record<CampoEndereco, string>;

export const ENDERECO_VAZIO: ValorEndereco = { cep: "", logradouro: "", numero: "", complemento: "", bairro: "", cidade: "", uf: "" };

export function enderecoDe(e: Endereco | null | undefined): ValorEndereco {
  return {
    cep: e?.cep ?? "",
    logradouro: e?.logradouro ?? "",
    numero: e?.numero ?? "",
    complemento: e?.complemento ?? "",
    bairro: e?.bairro ?? "",
    cidade: e?.cidade ?? "",
    uf: e?.uf ?? "",
  };
}

export function BlocoEndereco({
  valor,
  onChange,
  disabled,
  dica,
  obrigatorio,
}: {
  valor: ValorEndereco;
  onChange: (parcial: Partial<ValorEndereco>) => void;
  disabled?: boolean;
  dica?: React.ReactNode;
  obrigatorio?: (campo: CampoEndereco) => boolean;
}) {
  const obr = (c: CampoEndereco) => !disabled && !!obrigatorio?.(c);
  const [buscando, setBuscando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const ultimo = useRef("");
  const numero = useRef<HTMLInputElement>(null);

  async function buscar(digitos: string) {
    ultimo.current = digitos;
    setBuscando(true);
    setErro(null);
    try {
      const r = await api.get<ConsultaCep>(`/nucleo/consultas/cep/${digitos}`);
      if (ultimo.current !== digitos) return; // digitou outro CEP enquanto buscava
      onChange({
        cep: r.cep || mascaraCep(digitos),
        logradouro: r.logradouro ?? "",
        bairro: r.bairro ?? "",
        cidade: r.cidade ?? "",
        uf: (r.uf ?? "").toUpperCase(),
      });
      numero.current?.focus();
    } catch (e) {
      if (ultimo.current === digitos) setErro(mensagemConsulta(e, "CEP"));
    } finally {
      if (ultimo.current === digitos) setBuscando(false);
    }
  }

  const texto = (k: Exclude<CampoEndereco, "cep" | "uf">) => ({
    value: valor[k],
    disabled,
    className: "h-9",
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => onChange({ [k]: e.target.value }),
  });

  return (
    <fieldset className="flex flex-col gap-4" disabled={disabled}>
      <legend className="eyebrow mb-3">ENDEREÇO</legend>
      <div className="grid gap-4 sm:grid-cols-[150px_1fr]">
        <Field label="CEP" obrigatorio={obr("cep")} erro={erro ?? undefined}>
          <div className="relative">
            <Input
              className="num h-9"
              inputMode="numeric"
              placeholder="00000-000"
              autoComplete="postal-code"
              value={valor.cep}
              disabled={disabled}
              aria-invalid={!!erro}
              onChange={(e) => {
                const cep = mascaraCep(e.target.value);
                onChange({ cep });
                const d = cep.replace(/\D/g, "");
                if (d.length === 8 && d !== ultimo.current) void buscar(d);
                else if (d.length < 8) {
                  ultimo.current = "";
                  setErro(null);
                  setBuscando(false);
                }
              }}
            />
            {buscando && <Loader2 className="absolute top-1/2 right-2.5 size-4 -translate-y-1/2 animate-spin text-muted" aria-label="Buscando CEP" />}
          </div>
        </Field>
        <Field label="Logradouro" obrigatorio={obr("logradouro")}>
          <Input {...texto("logradouro")} autoComplete="address-line1" />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-[150px_1fr]">
        <Field label="Número" obrigatorio={obr("numero")}>
          <Input {...texto("numero")} ref={numero} />
        </Field>
        <Field label="Complemento" obrigatorio={obr("complemento")}>
          <Input {...texto("complemento")} autoComplete="address-line2" />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-[1fr_1fr_80px]">
        <Field label="Bairro" obrigatorio={obr("bairro")}>
          <Input {...texto("bairro")} />
        </Field>
        <Field label="Cidade" obrigatorio={obr("cidade")}>
          <Input {...texto("cidade")} autoComplete="address-level2" />
        </Field>
        <Field label="UF" obrigatorio={obr("uf")}>
          <Input
            className="h-9 uppercase"
            maxLength={2}
            value={valor.uf}
            disabled={disabled}
            autoComplete="address-level1"
            onChange={(e) => onChange({ uf: e.target.value.replace(/[^a-zA-Z]/g, "").toUpperCase().slice(0, 2) })}
          />
        </Field>
      </div>
      {dica && <p className="-mt-2 text-xs text-muted">{dica}</p>}
    </fieldset>
  );
}
