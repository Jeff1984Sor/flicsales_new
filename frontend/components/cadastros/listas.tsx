"use client";

/**
 * `<SelectLista tipo valor onChange disabled? id? />` — lista suspensa alimentada pela Governança de ajustes
 * (segmento · porte), usada nos cadastros de empresa e fornecedor.
 * Valor gravado (ou vindo do CNPJ) fora da lista aparece como opção e, para quem pode editar a governança
 * (`nucleo.administracao.editar`), ganha o botão "Adicionar à lista". Sem a rota publicada vira texto livre.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { chaveLista, useOpcoesLista } from "@/components/governanca/opcoes-lista";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { OpcaoLista, TipoLista } from "@/lib/tipos-governanca";

export function SelectLista({
  tipo,
  valor,
  onChange,
  disabled,
  id,
}: {
  tipo: TipoLista;
  valor: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  id?: string;
}) {
  const { pode } = useAuth();
  const qc = useQueryClient();
  const { opcoes, carregando, indisponivel } = useOpcoesLista(tipo);
  const adicionar = useMutation({
    mutationFn: (nome: string) => api.post<OpcaoLista>(`/nucleo/listas/${tipo}`, { nome }),
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: chaveLista(tipo) });
      notificar.sucesso(`“${o.nome}” adicionado à lista`);
    },
  });

  // rota ainda não publicada: mantém o texto livre
  if (indisponivel) return <Input id={id} className="h-9" value={valor} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;

  const nomes = opcoes.map((o) => o.nome);
  const foraDaLista = !!valor.trim() && !carregando && !nomes.some((n) => n.toLowerCase() === valor.trim().toLowerCase());
  return (
    <div className="flex flex-col gap-1.5">
      <NativeSelect id={id} value={valor} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">Selecionar</option>
        {valor && !nomes.includes(valor) && <option value={valor}>{valor}</option>}
        {nomes.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </NativeSelect>
      {foraDaLista && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>Fora da lista da governança.</span>
          {pode("nucleo.administracao.editar") && !disabled && (
            <Button type="button" size="sm" variant="outline" disabled={adicionar.isPending} onClick={() => adicionar.mutate(valor.trim())}>
              Adicionar à lista
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
