"use client";

/**
 * Drawers do funil: "Criar funil de vendas" (protótipo `newFunnel`) e "Etapas · {funil}" (`editFunnel`).
 * Ganha e Perdida são resultados finais, não etapas. Probabilidade é parâmetro configurado, não previsão de IA.
 */
import { useMutation } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useState } from "react";

import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { Funil } from "@/lib/tipos-comercial";

import { useInvalidarComercial } from "./dados";

const MSG_ETAPAS = "Defina pelo menos duas etapas únicas, sem Ganha ou Perdida";

function etapasValidas(nomes: string[]) {
  const chaves = nomes.map((n) => n.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase());
  return nomes.length >= 2 && new Set(chaves).size === chaves.length && !chaves.some((c) => ["ganha", "perdida", "ganho", "perdido"].includes(c));
}

export function NovoFunilDrawer({ aberto, onFechar, aoCriar }: { aberto: boolean; onFechar: () => void; aoCriar?: (f: Funil) => void }) {
  const invalidar = useInvalidarComercial();
  const criar = useMutation({
    mutationFn: (corpo: { nome: string; etapas: string[] }) => api.post<Funil>("/comercial/funis", corpo),
    onSuccess: (f) => {
      invalidar();
      notificar("Funil criado");
      aoCriar?.(f);
      onFechar();
    },
  });

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const nomes = String(fd.get("etapas") ?? "")
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean);
    if (!etapasValidas(nomes)) {
      notificar(MSG_ETAPAS);
      return;
    }
    criar.mutate({ nome: String(fd.get("nome") ?? "").trim(), etapas: nomes });
  }

  return (
    <Drawer aberto={aberto} onFechar={onFechar} titulo="Criar funil de vendas">
      {aberto && (
        <form onSubmit={enviar}>
          <CampoDrawer rotulo="Nome do funil" obrigatorio>
            <Input name="nome" required placeholder="Ex.: Novos negócios" maxLength={120} />
          </CampoDrawer>
          <CampoDrawer rotulo="Etapas, uma por linha" obrigatorio>
            <Textarea name="etapas" required rows={6} defaultValue={"Entrada\nQualificação\nDiscovery\nProposta\nNegociação"} />
          </CampoDrawer>
          <p className="mt-3 text-xs text-muted">Ganha e Perdida são resultados finais. As etapas são exclusivas deste funil.</p>
          <Button type="submit" className="mt-5" disabled={criar.isPending}>
            {criar.isPending && <Loader2 className="animate-spin" />}
            Criar funil
          </Button>
        </form>
      )}
    </Drawer>
  );
}

interface EtapaEdicao {
  chave: string;
  id: number | null;
  nome: string;
  probabilidade: string;
  limite_dias: string;
  criterios: string;
}

export function EtapasDrawer({ funil, aberto, onFechar }: { funil: Funil | null; aberto: boolean; onFechar: () => void }) {
  return (
    <Drawer aberto={aberto && !!funil} onFechar={onFechar} titulo={funil ? `Etapas · ${funil.nome}` : "Etapas"}>
      {aberto && funil && <EtapasCorpo key={funil.id} funil={funil} onFechar={onFechar} />}
    </Drawer>
  );
}

function EtapasCorpo({ funil, onFechar }: { funil: Funil; onFechar: () => void }) {
  const invalidar = useInvalidarComercial();
  const [etapas, setEtapas] = useState<EtapaEdicao[]>(() =>
    funil.etapas.map((e) => ({
      chave: String(e.id),
      id: e.id,
      nome: e.nome,
      probabilidade: String(e.probabilidade),
      limite_dias: e.limite_dias == null ? "" : String(e.limite_dias),
      criterios: e.criterios ?? "",
    })),
  );
  const salvar = useMutation({
    mutationFn: () =>
      api.put<Funil>(`/comercial/funis/${funil.id}/etapas`, {
        etapas: etapas.map((e) => ({
          id: e.id,
          nome: e.nome.trim(),
          probabilidade: Number(e.probabilidade),
          limite_dias: e.limite_dias === "" ? null : Number(e.limite_dias),
          criterios: e.criterios.trim() || null,
        })),
      }),
    onSuccess: () => {
      invalidar();
      notificar("Critérios do funil atualizados");
      onFechar();
    },
  });

  const alterar = (i: number, campo: keyof EtapaEdicao, valor: string) =>
    setEtapas((lista) => lista.map((e, j) => (j === i ? { ...e, [campo]: valor } : e)));

  function enviar(ev: React.FormEvent) {
    ev.preventDefault();
    if (!etapasValidas(etapas.map((e) => e.nome.trim()).filter(Boolean)) || etapas.some((e) => !e.nome.trim())) {
      notificar(MSG_ETAPAS);
      return;
    }
    salvar.mutate();
  }

  return (
    <form onSubmit={enviar}>
      {etapas.map((e, i) => (
        <div key={e.chave} className="card-surface mb-3 p-4">
          <div className="flex items-center justify-between gap-2">
            <Input aria-label="Nome da etapa" value={e.nome} onChange={(x) => alterar(i, "nome", x.target.value)} className="font-semibold" required />
            {e.id == null && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setEtapas((l) => l.filter((_, j) => j !== i))}>
                Remover
              </Button>
            )}
          </div>
          <CampoDrawer rotulo="Probabilidade configurada (%)" obrigatorio>
            <Input type="number" min={0} max={100} required value={e.probabilidade} onChange={(x) => alterar(i, "probabilidade", x.target.value)} />
          </CampoDrawer>
          <CampoDrawer rotulo="Limite de permanência (dias)">
            <Input type="number" min={1} value={e.limite_dias} onChange={(x) => alterar(i, "limite_dias", x.target.value)} />
          </CampoDrawer>
          <CampoDrawer rotulo="Critérios e campos exigidos">
            <Input value={e.criterios} onChange={(x) => alterar(i, "criterios", x.target.value)} />
          </CampoDrawer>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setEtapas((l) => [...l, { chave: `nova-${l.length}-${Date.now()}`, id: null, nome: "", probabilidade: "50", limite_dias: "7", criterios: "" }])}
      >
        <Plus /> Etapa
      </Button>
      <p className="mt-3 text-xs text-muted">
        Probabilidades são parâmetros configurados, não previsões de IA. Etapas com oportunidades não podem ser removidas.
      </p>
      <Button type="submit" className="mt-5" disabled={salvar.isPending}>
        {salvar.isPending && <Loader2 className="animate-spin" />}
        Salvar configuração
      </Button>
    </form>
  );
}
