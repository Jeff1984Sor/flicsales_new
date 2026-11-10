"use client";

/**
 * PropostaForm — drawer "Novo registro · Propostas" / "Editar proposta" (protótipo `schemas.Propostas`).
 * Total = quantidade × preço unitário × (1 − desconto). Desconto > 0 exige justificativa e passa por aprovação interna.
 * "Aceita" não fecha a oportunidade sozinha.
 */
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { Dinheiro } from "@/components/flic/dinheiro";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CONDICOES_PROPOSTA, type Proposta, STATUS_PROPOSTA, type StatusProposta } from "@/lib/tipos-comercial";

import { lerForm, nulo, numeroOuNulo, useInvalidarComercial, useOpcoes, useUsuarios } from "./dados";

export function PropostaForm({
  aberto,
  onFechar,
  proposta,
  oportunidadeId,
}: {
  aberto: boolean;
  onFechar: () => void;
  proposta?: Proposta | null;
  oportunidadeId?: number | null;
}) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} titulo={proposta ? "Editar proposta" : "Novo registro · Propostas"}>
      {aberto && <Corpo key={proposta?.id ?? "nova"} proposta={proposta} oportunidadeId={oportunidadeId} onFechar={onFechar} />}
    </Drawer>
  );
}

function Corpo({ proposta, oportunidadeId, onFechar }: { proposta?: Proposta | null; oportunidadeId?: number | null; onFechar: () => void }) {
  const { usuario } = useAuth();
  const { data: opcoes } = useOpcoes();
  const { data: usuarios } = useUsuarios();
  const invalidar = useInvalidarComercial();
  const [qtd, setQtd] = useState(proposta?.quantidade ?? "1");
  const [unit, setUnit] = useState(proposta?.preco_unitario ?? "");
  const [desc, setDesc] = useState(proposta?.desconto_pct ?? "0");
  const [opId, setOpId] = useState<string>(String(proposta?.oportunidade_id ?? oportunidadeId ?? ""));
  const total = Number(qtd || 0) * Number(unit || 0) * (1 - Number(desc || 0) / 100);

  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) =>
      proposta ? api.patch<Proposta>(`/comercial/propostas/${proposta.id}`, corpo) : api.post<Proposta>("/comercial/propostas", corpo),
    onSuccess: () => {
      invalidar();
      notificar(proposta ? "Proposta atualizada" : "Proposta registrada");
      onFechar();
    },
  });

  const op = opcoes?.oportunidades.find((o) => String(o.id) === opId);
  const empresaDaOp = opcoes?.empresas.find((e) => e.id === op?.empresa_id)?.nome;

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = lerForm(e.currentTarget);
    const q = Number(f.quantidade);
    const d = Number(f.desconto_pct || 0);
    if (!(q > 0) || d < 0 || d > 100) {
      notificar("Quantidade deve ser positiva e desconto entre 0 e 100%");
      return;
    }
    if (d > 0 && !f.justificativa_desconto.trim()) {
      notificar("Registre a justificativa do desconto");
      return;
    }
    const comum = {
      titulo: f.titulo.trim(),
      escopo: f.escopo.trim(),
      produto_id: numeroOuNulo(f.produto_id),
      quantidade: f.quantidade,
      preco_unitario: f.preco_unitario,
      desconto_pct: nulo(f.desconto_pct) ?? "0",
      mensalidade_adicional: nulo(f.mensalidade_adicional) ?? "0",
      validade: f.validade,
      condicao: f.condicao,
      responsavel_id: numeroOuNulo(f.responsavel_id),
      status: f.status as StatusProposta,
      justificativa_desconto: nulo(f.justificativa_desconto),
    };
    salvar.mutate(proposta ? comum : { ...comum, oportunidade_id: Number(f.oportunidade_id), versao: numeroOuNulo(f.versao) });
  }

  return (
    <form id="form-proposta" onSubmit={enviar}>
      <CampoDrawer rotulo="Título" obrigatorio>
        <Input name="titulo" required defaultValue={proposta?.titulo ?? ""} maxLength={200} />
      </CampoDrawer>
      <CampoDrawer rotulo="Oportunidade" obrigatorio>
        <NativeSelect name="oportunidade_id" required value={opId} onChange={(e) => setOpId(e.target.value)} disabled={!!proposta}>
          <option value="">Selecione</option>
          {(opcoes?.oportunidades ?? []).map((o) => (
            <option key={o.id} value={o.id}>
              {o.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Empresa" obrigatorio dica="Vem da oportunidade (cadastro compartilhado).">
        <Input value={proposta?.empresa_nome ?? empresaDaOp ?? ""} readOnly placeholder="Escolha a oportunidade" />
      </CampoDrawer>
      <CampoDrawer rotulo="Versão" obrigatorio dica={proposta ? "Para nova versão, use Duplicar." : "Em branco: próxima versão automaticamente."}>
        <Input name="versao" type="number" min={1} step={1} defaultValue={proposta?.versao ?? ""} disabled={!!proposta} />
      </CampoDrawer>
      <CampoDrawer rotulo="Escopo e entregáveis" obrigatorio>
        <Textarea name="escopo" required defaultValue={proposta?.escopo ?? ""} />
      </CampoDrawer>
      <CampoDrawer rotulo="Produto / serviço">
        <NativeSelect
          name="produto_id"
          defaultValue={String(proposta?.produto_id ?? "")}
          onChange={(e) => {
            const p = opcoes?.produtos.find((x) => String(x.id) === e.target.value);
            if (p?.preco_referencia && !unit) setUnit(p.preco_referencia);
          }}
        >
          <option value="">Sem produto</option>
          {(opcoes?.produtos ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <div className="grid grid-cols-2 gap-3">
        <CampoDrawer rotulo="Quantidade" obrigatorio>
          <Input name="quantidade" type="number" min="0.001" step="0.001" required value={qtd} onChange={(e) => setQtd(e.target.value)} />
        </CampoDrawer>
        <CampoDrawer rotulo="Preço unitário (R$)" obrigatorio>
          <Input name="preco_unitario" type="number" min="0" step="0.01" required value={unit} onChange={(e) => setUnit(e.target.value)} />
        </CampoDrawer>
        <CampoDrawer rotulo="Desconto (%)">
          <Input name="desconto_pct" type="number" min="0" max="100" step="0.01" value={desc} onChange={(e) => setDesc(e.target.value)} />
        </CampoDrawer>
        <CampoDrawer rotulo="Mensalidade adicional (R$)">
          <Input name="mensalidade_adicional" type="number" min="0" step="0.01" defaultValue={proposta?.mensalidade_adicional ?? ""} />
        </CampoDrawer>
      </div>
      <p className="mt-3 text-sm">
        Total calculado: <Dinheiro valor={Number.isFinite(total) ? total.toFixed(2) : null} className="font-bold" />
      </p>
      <CampoDrawer rotulo="Validade" obrigatorio>
        <Input name="validade" type="date" required defaultValue={proposta?.validade ?? ""} />
      </CampoDrawer>
      <CampoDrawer rotulo="Condição de pagamento" obrigatorio>
        <NativeSelect name="condicao" defaultValue={proposta?.condicao ?? CONDICOES_PROPOSTA[0]}>
          {CONDICOES_PROPOSTA.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Responsável" obrigatorio>
        <NativeSelect name="responsavel_id" defaultValue={String(proposta?.responsavel_id ?? usuario?.id ?? "")}>
          {(usuarios ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Status" obrigatorio>
        <NativeSelect name="status" defaultValue={proposta?.status ?? "rascunho"}>
          {STATUS_PROPOSTA.map((s) => (
            <option key={s.valor} value={s.valor}>
              {s.rotulo}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Justificativa / aprovação de desconto" obrigatorio={Number(desc) > 0} dica="Desconto passa por aprovação interna antes do envio.">
        <Textarea name="justificativa_desconto" defaultValue={proposta?.justificativa_desconto ?? ""} />
      </CampoDrawer>
      <p className="mt-4 text-xs text-muted">Registrar “Aceita” não fecha a oportunidade automaticamente. Use o fechamento para revisar o financeiro.</p>
      <div className="mt-5 flex gap-2">
        <Button type="submit" disabled={salvar.isPending}>
          {salvar.isPending && <Loader2 className="animate-spin" />}
          Salvar registro
        </Button>
        <Button type="button" variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
