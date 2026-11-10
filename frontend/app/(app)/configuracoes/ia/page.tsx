"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Save, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Field, NativeSelect, SwitchRow } from "@/components/flic/form";
import { SenhaInput } from "@/components/flic/senha-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import type { ConfigIAOut } from "@/lib/types";

const AVISO =
  "Os textos enviados à IA (melhoria de evoluções, preenchimento de cadastros) vão ao provedor escolhido. Use uma conta empresarial com retenção de dados desligada e não envie mais do que o necessário.";

function useDebounce<T>(valor: T, ms: number): T {
  const [atual, setAtual] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setAtual(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return atual;
}

function Formulario({ cfg }: { cfg: ConfigIAOut }) {
  const qc = useQueryClient();
  const [ativo, setAtivo] = useState(cfg.ativo);
  const [provedor, setProvedor] = useState(cfg.provedor);
  const [modelo, setModelo] = useState(cfg.modelo ?? "");
  const [chave, setChave] = useState("");
  // chave digitada (ainda não salva) ou a salva do mesmo provedor; espera a digitação parar antes de consultar
  const chaveLimpa = useDebounce(chave.trim(), 600);
  const temChave = chaveLimpa.length >= 20 || (cfg.chave_definida && provedor === cfg.provedor);
  const lista = useQuery({
    queryKey: ["config-ia-modelos", provedor, chaveLimpa || cfg.chave_final],
    queryFn: () => api.post<string[]>("/config/ia/modelos", { provedor, chave: chaveLimpa || null }),
    enabled: temChave,
    retry: false,
    staleTime: 5 * 60_000,
    meta: { silencioso: true },
  });
  const modelos = lista.data ?? [];
  const usarLista = modelos.length > 0;
  const salvar = useMutation({
    mutationFn: () => api.put<ConfigIAOut>("/config/ia", { ativo, provedor, modelo: modelo || null, chave: chave || null }),
    onSuccess: (novo) => {
      qc.setQueryData(["config-ia"], novo);
      setChave("");
      toast.success("Configuração de IA salva");
    },
  });
  return (
    <form
      className="card-surface max-w-2xl space-y-4 p-5"
      onSubmit={(e) => {
        e.preventDefault();
        salvar.mutate();
      }}
    >
      <p className="rounded-lg border border-warning/30 bg-warning/8 px-3 py-2 text-xs text-warning-ink">{AVISO}</p>
      <SwitchRow titulo="Usar Inteligência Artificial" descricao="Liga os botões de IA nas telas que oferecem esse recurso.">
        <Switch checked={ativo} onCheckedChange={setAtivo} />
      </SwitchRow>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Provedor">
          <NativeSelect value={provedor} onChange={(e) => (setProvedor(e.target.value as ConfigIAOut["provedor"]), setModelo(""))}>
            {Object.entries(cfg.provedores).map(([id, nome]) => (
              <option key={id} value={id}>
                {nome}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field
          label="Modelo"
          dica={
            lista.isFetching
              ? "Buscando os modelos no provedor…"
              : lista.isError
                ? `${(lista.error as Error).message} Você também pode digitar o nome (ex.: gpt-4o-mini).`
                : usarLista
                  ? `${modelos.length} modelos disponíveis para esta chave.`
                  : "Cole a chave abaixo e os modelos aparecem aqui."
          }
        >
          {usarLista ? (
            <NativeSelect value={modelo} onChange={(e) => setModelo(e.target.value)}>
              <option value="">Escolha o modelo</option>
              {modelo && !modelos.includes(modelo) && <option value={modelo}>{modelo}</option>}
              {modelos.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </NativeSelect>
          ) : (
            <Input
              value={modelo}
              onChange={(e) => setModelo(e.target.value)}
              placeholder={lista.isFetching ? "carregando modelos…" : "nome do modelo"}
            />
          )}
        </Field>
      </div>
      <Field
        label="Chave de API"
        dica={
          cfg.chave_definida
            ? `Chave salva (termina em ${cfg.chave_final}). Preencha só para trocar. Ela fica cifrada no banco.`
            : "Cole a chave do provedor. Ela fica cifrada no banco."
        }
      >
        <SenhaInput value={chave} onChange={setChave} autoComplete="off" />
      </Field>
      <div className="flex justify-end">
        <Button type="submit" disabled={salvar.isPending}>
          {salvar.isPending ? <Loader2 className="animate-spin" /> : <Save />} Salvar
        </Button>
      </div>
    </form>
  );
}

export default function IAPage() {
  const q = useQuery({ queryKey: ["config-ia"], queryFn: () => api.get<ConfigIAOut>("/config/ia") });
  return (
    <div className="space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Sparkles className="size-5 text-info-ink" /> Inteligência Artificial
        </h2>
        <p className="text-sm text-muted-foreground">Provedor e chave usados pelos recursos de IA do sistema.</p>
      </div>
      {q.data ? <Formulario cfg={q.data} /> : <Skeleton className="h-72 max-w-2xl rounded-2xl" />}
    </div>
  );
}
