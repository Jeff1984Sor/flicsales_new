"use client";

/**
 * FormBaixa — drawer "Recebimento/Pagamento gerencial" (protótipo `settlementForm/saveSettlement`).
 * FormMotivo — drawer genérico com "Motivo *" (cancelar título, estornar baixa).
 */
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { hojeISO } from "@/lib/format";
import type { Baixa, BaixaIn, Forma, Titulo } from "@/lib/tipos-financeiro";

import { Campo, Escolha, Limite, ROTULO_FORMA, Texto, TextoLongo, deRotulos, paraOpcoes, textoOuNulo, useInvalidarFinanceiro, useOpcoes } from "./comum";

export function FormBaixa({ titulo, onFechar }: { titulo: Titulo | null; onFechar: () => void }) {
  const receber = titulo?.direcao === "receber";
  return (
    <Drawer
      aberto={!!titulo}
      onFechar={onFechar}
      rotulo={receber ? "BAIXA / RECEBIMENTO" : "BAIXA / PAGAMENTO"}
      titulo={`${receber ? "Recebimento" : "Pagamento"} gerencial`}
      descricao={
        titulo && (
          <>
            {titulo.empresa_nome} · saldo <Dinheiro valor={titulo.saldo} />
          </>
        )
      }
    >
      {titulo && <Corpo key={titulo.id} titulo={titulo} onFechar={onFechar} />}
    </Drawer>
  );
}

function Corpo({ titulo, onFechar }: { titulo: Titulo; onFechar: () => void }) {
  const opcoes = useOpcoes();
  const invalidar = useInvalidarFinanceiro();
  const [f, setF] = useState({
    valor: titulo.saldo,
    data: hojeISO(),
    conta_id: titulo.conta_prevista_id ? String(titulo.conta_prevista_id) : "",
    forma: (titulo.forma ?? "pix") as Forma,
    referencia: "",
    observacao: "",
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const salvar = useMutation({
    mutationFn: () => {
      const corpo: BaixaIn = {
        valor: f.valor.replace(",", "."),
        data: f.data,
        conta_id: Number(f.conta_id),
        forma: f.forma,
        referencia_comprovante: textoOuNulo(f.referencia),
        observacao: textoOuNulo(f.observacao),
      };
      return api.post<Baixa>(`/financeiro/titulos/${titulo.id}/baixas`, corpo);
    },
    onSuccess: () => {
      invalidar();
      notificar.sucesso("Saldo e caixa atualizados");
      onFechar();
    },
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const v = Number(f.valor.replace(",", "."));
        if (!(v > 0) || v > Number(titulo.saldo)) {
          notificar.erro("Valor deve ser positivo e não superar o saldo");
          return;
        }
        if (!f.conta_id) {
          notificar.erro("Selecione uma conta cadastrada");
          return;
        }
        salvar.mutate();
      }}
    >
      <Campo rotulo="Valor efetivo (R$)" obrigatorio>
        <Texto inputMode="decimal" className="num" value={f.valor} onChange={(e) => set("valor", e.target.value)} required />
      </Campo>
      <Campo rotulo="Data efetiva" obrigatorio>
        <Texto type="date" value={f.data} max={hojeISO()} onChange={(e) => set("data", e.target.value)} required />
      </Campo>
      <Campo rotulo="Conta financeira" obrigatorio>
        <Escolha valor={f.conta_id} onChange={(v) => set("conta_id", v)} opcoes={paraOpcoes(opcoes.data?.contas)} obrigatorio />
      </Campo>
      <Campo rotulo="Forma" obrigatorio>
        <Escolha valor={f.forma} onChange={(v) => set("forma", v as Forma)} opcoes={deRotulos(ROTULO_FORMA)} vazio={false} />
      </Campo>
      <Campo rotulo="Referência do comprovante">
        <Texto value={f.referencia} onChange={(e) => set("referencia", e.target.value)} maxLength={200} />
      </Campo>
      <Campo rotulo="Observação">
        <TextoLongo value={f.observacao} onChange={(e) => set("observacao", e.target.value)} />
      </Campo>
      <Limite>
        Baixa parcial mantém o saldo restante. Ajustes de juros e descontos exigem regra própria; a baixa não excede o saldo. Baixas são gerenciais. Nenhuma
        operação bancária é executada.
      </Limite>
      <Button type="submit" className="mt-4" disabled={salvar.isPending}>
        Confirmar baixa gerencial
      </Button>
    </form>
  );
}

export function FormMotivo({
  aberto,
  onFechar,
  titulo,
  descricao,
  rotulo,
  aviso,
  botao,
  enviando,
  onConfirmar,
}: {
  aberto: boolean;
  onFechar: () => void;
  titulo: string;
  descricao?: React.ReactNode;
  rotulo?: string;
  aviso?: React.ReactNode;
  botao: string;
  enviando?: boolean;
  onConfirmar: (motivo: string) => void;
}) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} rotulo={rotulo} titulo={titulo} descricao={descricao}>
      <CorpoMotivo aviso={aviso} botao={botao} enviando={enviando} onConfirmar={onConfirmar} />
    </Drawer>
  );
}

function CorpoMotivo({ aviso, botao, enviando, onConfirmar }: { aviso?: React.ReactNode; botao: string; enviando?: boolean; onConfirmar: (motivo: string) => void }) {
  const [motivo, setMotivo] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!motivo.trim()) {
          notificar.erro("Informe o motivo.");
          return;
        }
        onConfirmar(motivo.trim());
      }}
    >
      <Campo rotulo="Motivo" obrigatorio>
        <TextoLongo value={motivo} onChange={(e) => setMotivo(e.target.value)} required autoFocus />
      </Campo>
      {aviso && <Limite>{aviso}</Limite>}
      <Button type="submit" className="mt-4" disabled={enviando}>
        {botao}
      </Button>
    </form>
  );
}
