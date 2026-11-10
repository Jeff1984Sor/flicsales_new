"use client";

import { Check, Trash2 } from "lucide-react";

import { Field } from "@/components/flic/form";
import { SenhaInput } from "@/components/flic/senha-input";
import { Pill } from "@/components/flic/status-badge";
import type { Segredo } from "@/lib/types";

/**
 * Campo de credencial SOMENTE ESCRITA: mostra "configurado" + os últimos caracteres, nunca o valor.
 * Em branco = manter o que já está salvo; digitar = trocar; "remover" apaga.
 */
export function SegredoCampo({
  label,
  atual,
  valor,
  onChange,
  remover,
  onRemover,
  dica,
  id,
}: {
  label: string;
  atual: Segredo;
  valor: string;
  onChange: (v: string) => void;
  remover: boolean;
  onRemover: (v: boolean) => void;
  dica?: string;
  id: string;
}) {
  return (
    <Field
      label={label}
      htmlFor={id}
      dica={
        remover
          ? "Será removido ao salvar."
          : (dica ?? (atual.definido ? "Deixe em branco para manter o valor salvo." : "Fica cifrado no banco e não pode ser lido depois."))
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        {atual.definido && !remover ? (
          <Pill tom="success" className="normal-case">
            <Check className="size-3" /> configurado{atual.final ? ` · termina em ${atual.final}` : ""}
          </Pill>
        ) : (
          <Pill tom={remover ? "danger" : "neutral"} className="normal-case">
            {remover ? "remover ao salvar" : "não configurado"}
          </Pill>
        )}
        {atual.definido && (
          <button
            type="button"
            onClick={() => onRemover(!remover)}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-danger-ink hover:underline"
          >
            <Trash2 className="size-3" /> {remover ? "desfazer" : "remover"}
          </button>
        )}
      </div>
      <SenhaInput id={id} value={valor} onChange={onChange} autoComplete="new-password" disabled={remover} />
    </Field>
  );
}
