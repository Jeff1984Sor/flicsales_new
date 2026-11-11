"use client";

/**
 * CampoCnpj — "CNPJ / CPF" com máscara e "Buscar CNPJ" (`GET /bff/nucleo/consultas/cnpj/{cnpj}`). Em cadastro novo
 * também busca sozinho ao completar 14 dígitos válidos. Quem usa decide o que preencher (só campos vazios) e devolve
 * os rótulos preenchidos; o campo mostra "N campos preenchidos pelo CNPJ". Se o CNPJ já pertence a outra empresa,
 * avisa e oferece abrir o cadastro existente em vez de duplicar.
 *
 * Props:
 *  - `valor: string`  `onChange: (v: string) => void`
 *  - `onResultado: (r: ConsultaCnpj) => string[]`        aplica no formulário; devolve os rótulos preenchidos
 *  - `automatico?: boolean`                               busca ao completar 14 dígitos (use em cadastro novo)
 *  - `registroId?: number | null`                         id do próprio registro (não se avisa duplicidade dele mesmo)
 *  - `onAbrirExistente?: (id: number) => void`            ação do aviso de duplicidade
 *  - `rotuloExistente?: string`                           padrão "Abrir cadastro existente"
 *  - `erroExterno?: string | null`                       erro vindo do salvar (ex.: "CNPJ ou CPF inválido.", duplicado)
 *  - `rotulo?: string`  `disabled?: boolean`  `autoFocus?: boolean`
 * Com 14 dígitos e dígito verificador errado o campo avisa na hora ("CNPJ inválido: confira os dígitos.").
 * Utilitários: `erroDocumentoLocal(v)` (mesma checagem, para bloquear o envio) e `erroDeDocumento(e)` (erro 400 do
 * salvar que fala do documento → mensagem para o campo; outros erros → null).
 */
import { Loader2, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Field } from "@/components/flic/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import type { ConsultaCnpj } from "@/lib/tipos-nucleo";
import { cnpjValido } from "@/lib/validacao";

import { mascaraDocumento, mensagemConsulta } from "./consultas";

interface Aviso {
  preenchidos: string[];
  fonte: string;
  situacao: string | null;
}

export function CampoCnpj({
  valor,
  onChange,
  onResultado,
  automatico,
  registroId = null,
  onAbrirExistente,
  rotuloExistente = "Abrir cadastro existente",
  rotulo = "CNPJ / CPF",
  disabled,
  autoFocus,
  erroExterno,
}: {
  valor: string;
  onChange: (v: string) => void;
  onResultado: (r: ConsultaCnpj) => string[];
  automatico?: boolean;
  registroId?: number | null;
  onAbrirExistente?: (id: number) => void;
  rotuloExistente?: string;
  rotulo?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  erroExterno?: string | null;
}) {
  const [buscando, setBuscando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<Aviso | null>(null);
  const [existente, setExistente] = useState<{ id: number; nome: string } | null>(null);
  const ultimo = useRef("");
  // a resposta chega depois: aplica com a versão mais recente do formulário de quem usa
  const aplicar = useRef(onResultado);
  useEffect(() => {
    aplicar.current = onResultado;
  });
  const digitos = valor.replace(/\D/g, "");

  async function buscar(d: string) {
    if (!cnpjValido(d)) {
      setErro("CNPJ inválido.");
      return;
    }
    ultimo.current = d;
    setBuscando(true);
    setErro(null);
    setAviso(null);
    setExistente(null);
    try {
      const r = await api.get<ConsultaCnpj>(`/nucleo/consultas/cnpj/${d}`);
      if (ultimo.current !== d) return;
      const preenchidos = aplicar.current(r);
      setAviso({ preenchidos, fonte: r.fonte, situacao: r.situacao });
      if (r.empresa_existente && r.empresa_existente.id !== registroId) setExistente(r.empresa_existente);
    } catch (e) {
      if (ultimo.current === d) setErro(mensagemConsulta(e, "CNPJ"));
    } finally {
      if (ultimo.current === d) setBuscando(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Field label={rotulo} erro={erro ?? erroExterno ?? undefined}>
        <div className="flex gap-2">
          <Input
            className="num h-9 flex-1"
            inputMode="numeric"
            value={valor}
            disabled={disabled}
            autoFocus={autoFocus}
            aria-invalid={!!(erro ?? erroExterno)}
            placeholder="00.000.000/0000-00"
            onChange={(e) => {
              const v = mascaraDocumento(e.target.value);
              onChange(v);
              const d = v.replace(/\D/g, "");
              setErro(d.length === 14 ? erroDocumentoLocal(d) : null);
              if (d.length < 14) {
                ultimo.current = "";
                setAviso(null);
                setExistente(null);
              } else if (automatico && d !== ultimo.current && cnpjValido(d)) void buscar(d);
            }}
          />
          {!disabled && (
            <Button type="button" variant="outline" className="h-9" disabled={digitos.length !== 14 || buscando} onClick={() => void buscar(digitos)}>
              {buscando ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
              Buscar CNPJ
            </Button>
          )}
        </div>
      </Field>
      {aviso && (
        <p className="text-xs text-muted">
          {aviso.preenchidos.length === 0
            ? "Nada a preencher: os campos já tinham valor."
            : `${aviso.preenchidos.length} ${aviso.preenchidos.length === 1 ? "campo preenchido" : "campos preenchidos"} pelo CNPJ: ${aviso.preenchidos.join(", ")}.`}{" "}
          Fonte: {aviso.fonte}.
          {aviso.situacao && aviso.situacao.toUpperCase() !== "ATIVA" && (
            <span className="mt-1 block font-semibold text-amber-ink">Situação na Receita: {aviso.situacao}.</span>
          )}
        </p>
      )}
      {existente && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-[8px] border border-amber/40 bg-amber/10 px-3 py-2 text-xs text-amber-ink">
          <span>
            Este CNPJ já está no cadastro: <strong>{existente.nome}</strong>. Evite duplicar.
          </span>
          {onAbrirExistente && (
            <Button type="button" size="sm" variant="outline" onClick={() => onAbrirExistente(existente.id)}>
              {rotuloExistente}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Preenche só os campos vazios do formulário com o que veio do CNPJ. `mapa`: campo do formulário → [rótulo, valor].
 * Devolve o formulário novo e os rótulos preenchidos.
 */
export function preencherVazios<F extends object>(form: F, mapa: Partial<Record<keyof F, [string, string | null | undefined]>>): { form: F; preenchidos: string[] } {
  const out = { ...form };
  const preenchidos: string[] = [];
  for (const k of Object.keys(mapa) as (keyof F)[]) {
    const par = mapa[k];
    if (!par) continue;
    const [rotulo, v] = par;
    const atual = out[k];
    if (v && typeof atual === "string" && atual.trim() === "") {
      out[k] = v as F[keyof F];
      preenchidos.push(rotulo);
    }
  }
  return { form: out, preenchidos };
}

const MSG_CNPJ_LOCAL = "CNPJ inválido: confira os dígitos.";

/** Checagem leve antes de enviar: só avisa quando há 14 dígitos com dígito verificador errado (CPF e dado antigo passam). */
export function erroDocumentoLocal(v: string | null | undefined): string | null {
  const d = (v ?? "").replace(/\D/g, "");
  return d.length === 14 && !cnpjValido(d) ? MSG_CNPJ_LOCAL : null;
}

/** Erro 400 do salvar que diz respeito ao documento (inválido ou já cadastrado) → texto para o campo; senão null. */
export function erroDeDocumento(e: unknown): string | null {
  if (!(e instanceof ApiError) || e.status !== 400) return null;
  return /cnpj|cpf|documento/i.test(e.message) ? e.message : null;
}
