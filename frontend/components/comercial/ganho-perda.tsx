"use client";

/**
 * GanhoDrawer — "Revisar fechamento" (protótipo `winForm`/`confirmWin`): prepara recebíveis em RASCUNHO e leva a
 * Financeiro › A receber. Não registra pagamento nem movimenta o caixa.
 * PerdaDrawer — perda com motivo obrigatório + concorrente + data de possível retomada. Nada é excluído.
 */
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { hojeISO } from "@/lib/format";
import type { GanhoOut, Oportunidade } from "@/lib/tipos-comercial";

import { CampoEmpresa, empresaDoTexto, lerForm, nulo, useInvalidarComercial, useOpcoes } from "./dados";

function somarDias(iso: string, dias: number) {
  const [a, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(a, m - 1, d + dias));
  return dt.toISOString().slice(0, 10);
}

export function GanhoDrawer({ oportunidade: o, aberto, onFechar }: { oportunidade: Oportunidade | null; aberto: boolean; onFechar: () => void }) {
  const router = useRouter();
  const { data: opcoes } = useOpcoes();
  const invalidar = useInvalidarComercial();
  const ganhar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) => api.post<GanhoOut>(`/comercial/oportunidades/${o?.id}/ganhar`, corpo),
    onSuccess: (r) => {
      invalidar();
      notificar(r.mensagem || "Venda ganha. Revise os recebíveis antes de confirmar.");
      onFechar();
      router.push("/financeiro/receber");
    },
  });

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = lerForm(e.currentTarget);
    if (!f.empresa.trim()) {
      notificar("Informe a empresa para preparar os recebíveis.");
      return;
    }
    ganhar.mutate({
      ...empresaDoTexto(f.empresa, opcoes?.empresas ?? []),
      valor: f.valor,
      condicao: f.condicao,
      primeiro_vencimento: nulo(f.primeiro_vencimento),
    });
  }

  return (
    <Drawer aberto={aberto && !!o} onFechar={onFechar} titulo="Revisar fechamento" descricao={o ? `${o.empresa_nome ?? "Empresa a definir"} · ${o.titulo}` : undefined}>
      {aberto && o && (
        <form onSubmit={enviar}>
          <CampoDrawer rotulo="Empresa" obrigatorio>
            <CampoEmpresa empresas={opcoes?.empresas} defaultValue={o.empresa_nome} required />
          </CampoDrawer>
          <CampoDrawer rotulo="Valor único acordado (R$)" obrigatorio>
            <Input name="valor" type="number" min="0.01" step="0.01" required defaultValue={Number(o.valor_unico) || ""} />
          </CampoDrawer>
          <CampoDrawer rotulo="Condição comercial">
            <NativeSelect name="condicao" defaultValue="Parcela única">
              {(opcoes?.condicoes_ganho ?? ["Parcela única", "2 parcelas iguais"]).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </NativeSelect>
          </CampoDrawer>
          <CampoDrawer rotulo="Primeiro vencimento" obrigatorio>
            <Input name="primeiro_vencimento" type="date" required defaultValue={somarDias(hojeISO(), 10)} />
          </CampoDrawer>
          <div className="mt-5 rounded-[8px] border border-electric/20 bg-electric/5 p-4 text-sm leading-relaxed">
            O fechamento prepara recebíveis em rascunho. Ele não registra pagamento nem movimenta o caixa.
          </div>
          <Button type="submit" className="mt-5" disabled={ganhar.isPending}>
            {ganhar.isPending && <Loader2 className="animate-spin" />}
            Confirmar venda e preparar recebíveis
          </Button>
        </form>
      )}
    </Drawer>
  );
}

export function PerdaDrawer({
  oportunidade: o,
  aberto,
  onFechar,
  aoPerder,
}: {
  oportunidade: Oportunidade | null;
  aberto: boolean;
  onFechar: () => void;
  aoPerder?: () => void;
}) {
  const invalidar = useInvalidarComercial();
  const perder = useMutation({
    mutationFn: (corpo: Record<string, unknown>) => api.post<Oportunidade>(`/comercial/oportunidades/${o?.id}/perder`, corpo),
    onSuccess: () => {
      invalidar();
      notificar("Oportunidade encerrada como perdida. O histórico foi mantido.");
      aoPerder?.();
      onFechar();
    },
  });

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = lerForm(e.currentTarget);
    if (!f.motivo.trim()) {
      notificar("Informe o motivo da perda");
      return;
    }
    perder.mutate({ motivo: f.motivo.trim(), concorrente: nulo(f.concorrente), data_retomada: nulo(f.data_retomada) });
  }

  return (
    <Drawer aberto={aberto && !!o} onFechar={onFechar} titulo="Registrar perda" descricao={o ? `${o.empresa_nome ?? "Sem empresa"} · ${o.titulo}` : undefined}>
      {aberto && o && (
        <form onSubmit={enviar}>
          <CampoDrawer rotulo="Motivo da perda" obrigatorio>
            <Textarea name="motivo" required />
          </CampoDrawer>
          <CampoDrawer rotulo="Concorrente">
            <Input name="concorrente" maxLength={200} />
          </CampoDrawer>
          <CampoDrawer rotulo="Data de possível retomada">
            <Input name="data_retomada" type="date" />
          </CampoDrawer>
          <p className="mt-4 text-xs text-muted">Nada é excluído: a oportunidade fica encerrada, com histórico, e pode ser reaberta.</p>
          <Button type="submit" className="mt-5" disabled={perder.isPending}>
            {perder.isPending && <Loader2 className="animate-spin" />}
            Registrar perda
          </Button>
        </form>
      )}
    </Drawer>
  );
}
