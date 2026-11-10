"use client";

/** FormTransferencia — drawer "Transferência gerencial" (protótipo `transferForm/saveTransfer`). */
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Drawer } from "@/components/flic/drawer";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { hojeISO } from "@/lib/format";
import type { Transferencia, TransferenciaIn } from "@/lib/tipos-financeiro";

import { Campo, Escolha, Limite, Texto, TextoLongo, paraOpcoes, textoOuNulo, useInvalidarFinanceiro, useOpcoes } from "./comum";

export function FormTransferencia({ aberto, onFechar }: { aberto: boolean; onFechar: () => void }) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} rotulo="CAIXA / TRANSFERÊNCIA" titulo="Transferência gerencial">
      <Corpo onFechar={onFechar} />
    </Drawer>
  );
}

function Corpo({ onFechar }: { onFechar: () => void }) {
  const opcoes = useOpcoes();
  const invalidar = useInvalidarFinanceiro();
  const [f, setF] = useState({ origem: "", destino: "", valor: "", data: hojeISO(), descricao: "" });
  const set = <K extends keyof typeof f>(k: K, v: string) => setF((x) => ({ ...x, [k]: v }));
  const salvar = useMutation({
    mutationFn: () => {
      const corpo: TransferenciaIn = {
        conta_origem_id: Number(f.origem),
        conta_destino_id: Number(f.destino),
        valor: f.valor.replace(",", "."),
        data: f.data,
        descricao: textoOuNulo(f.descricao),
      };
      return api.post<Transferencia>("/financeiro/transferencias", corpo);
    },
    onSuccess: () => {
      invalidar();
      notificar.sucesso("Movimentos internos registrados");
      onFechar();
    },
  });
  const contas = paraOpcoes(opcoes.data?.contas);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!f.origem || f.origem === f.destino || !(Number(f.valor.replace(",", ".")) > 0)) {
          notificar.erro("Selecione contas diferentes e valor positivo");
          return;
        }
        salvar.mutate();
      }}
    >
      <Campo rotulo="Conta de origem" obrigatorio>
        <Escolha valor={f.origem} onChange={(v) => set("origem", v)} opcoes={contas} obrigatorio />
      </Campo>
      <Campo rotulo="Conta de destino" obrigatorio>
        <Escolha valor={f.destino} onChange={(v) => set("destino", v)} opcoes={contas} obrigatorio />
      </Campo>
      <Campo rotulo="Valor (R$)" obrigatorio>
        <Texto inputMode="decimal" className="num" value={f.valor} onChange={(e) => set("valor", e.target.value)} required placeholder="0,00" />
      </Campo>
      <Campo rotulo="Data" obrigatorio>
        <Texto type="date" value={f.data} max={hojeISO()} onChange={(e) => set("data", e.target.value)} required />
      </Campo>
      <Campo rotulo="Descrição">
        <TextoLongo value={f.descricao} onChange={(e) => set("descricao", e.target.value)} maxLength={300} />
      </Campo>
      <Limite>Registro entre contas, sem envio de dinheiro. Não altera receita ou despesa.</Limite>
      <Button type="submit" className="mt-4" disabled={salvar.isPending}>
        Registrar transferência
      </Button>
    </form>
  );
}
