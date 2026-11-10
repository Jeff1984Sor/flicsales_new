"use client";

/**
 * FormRecorrencia — drawer "Novo registro / Editar · Recorrências" (protótipo `schemas.Recorrências`).
 * FormGerarCompetencia — drawer "Gerar competência" (protótipo `generateCycle/saveCycle`): título em rascunho.
 */
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hojeISO } from "@/lib/format";
import type { Direcao, Frequencia, Recorrencia, RecorrenciaIn, SituacaoRecorrencia, Titulo } from "@/lib/tipos-financeiro";

import {
  Campo,
  Escolha,
  Limite,
  ROTULO_FREQUENCIA,
  ROTULO_SIT_RECORRENCIA,
  Texto,
  deRotulos,
  idOuNulo,
  paraOpcoes,
  useInvalidarFinanceiro,
  useOpcoes,
  useUsuarios,
} from "./comum";

export function FormRecorrencia({ aberto, onFechar, recorrencia }: { aberto: boolean; onFechar: () => void; recorrencia?: Recorrencia | null }) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} rotulo="RECORRÊNCIAS" titulo={recorrencia ? "Editar · Recorrências" : "Novo registro · Recorrências"}>
      <Corpo key={recorrencia?.id ?? "nova"} recorrencia={recorrencia ?? null} onFechar={onFechar} />
    </Drawer>
  );
}

function Corpo({ recorrencia: r, onFechar }: { recorrencia: Recorrencia | null; onFechar: () => void }) {
  const { usuario } = useAuth();
  const opcoes = useOpcoes();
  const usuarios = useUsuarios();
  const invalidar = useInvalidarFinanceiro();
  const [f, setF] = useState({
    descricao: r?.descricao ?? "",
    direcao: (r?.direcao ?? "receber") as Direcao,
    empresa_id: r ? String(r.empresa_id) : "",
    valor_ciclo: r?.valor_ciclo ?? "",
    frequencia: (r?.frequencia ?? "mensal") as Frequencia,
    inicio: r?.inicio ?? hojeISO(),
    fim: r?.fim ?? "",
    dia_vencimento: r ? String(r.dia_vencimento) : "",
    categoria_id: r?.categoria_id ? String(r.categoria_id) : "",
    centro_custo_id: r?.centro_custo_id ? String(r.centro_custo_id) : "",
    responsavel_id: r?.responsavel_id ? String(r.responsavel_id) : usuario ? String(usuario.id) : "",
    situacao: (r?.situacao ?? "ativa") as SituacaoRecorrencia,
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const salvar = useMutation({
    mutationFn: () => {
      const corpo: RecorrenciaIn = {
        descricao: f.descricao,
        direcao: f.direcao,
        empresa_id: Number(f.empresa_id),
        valor_ciclo: f.valor_ciclo.replace(",", "."),
        frequencia: f.frequencia,
        inicio: f.inicio,
        fim: f.fim,
        dia_vencimento: Number(f.dia_vencimento),
        categoria_id: idOuNulo(f.categoria_id),
        centro_custo_id: idOuNulo(f.centro_custo_id),
        responsavel_id: idOuNulo(f.responsavel_id),
        situacao: f.situacao,
      };
      return r ? api.patch<Recorrencia>(`/financeiro/recorrencias/${r.id}`, corpo) : api.post<Recorrencia>("/financeiro/recorrencias", corpo);
    },
    onSuccess: () => {
      invalidar();
      notificar.sucesso("Registro salvo");
      onFechar();
    },
  });
  const categorias = (opcoes.data?.categorias ?? []).filter((c) => c.natureza === (f.direcao === "receber" ? "receita" : "despesa"));
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const dia = Number(f.dia_vencimento);
        if (!(Number(f.valor_ciclo.replace(",", ".")) > 0) || !Number.isInteger(dia) || dia < 1 || dia > 28) {
          notificar.erro("Informe valor positivo e dia inteiro entre 1 e 28");
          return;
        }
        if (f.fim < f.inicio) {
          notificar.erro("A data final deve ser igual ou posterior ao início");
          return;
        }
        salvar.mutate();
      }}
    >
      <Campo rotulo="Descrição" obrigatorio>
        <Texto value={f.descricao} onChange={(e) => set("descricao", e.target.value)} required maxLength={300} />
      </Campo>
      <Campo rotulo="Natureza" obrigatorio>
        <Escolha
          valor={f.direcao}
          onChange={(v) => set("direcao", v as Direcao)}
          opcoes={[
            { valor: "receber", rotulo: "A receber" },
            { valor: "pagar", rotulo: "A pagar" },
          ]}
          vazio={false}
        />
      </Campo>
      <Campo rotulo="Cliente / fornecedor" obrigatorio>
        <Escolha valor={f.empresa_id} onChange={(v) => set("empresa_id", v)} opcoes={paraOpcoes(opcoes.data?.empresas)} obrigatorio />
      </Campo>
      <Campo rotulo="Valor por ciclo (R$)" obrigatorio>
        <Texto inputMode="decimal" className="num" value={f.valor_ciclo} onChange={(e) => set("valor_ciclo", e.target.value)} required placeholder="0,00" />
      </Campo>
      <Campo rotulo="Frequência" obrigatorio>
        <Escolha valor={f.frequencia} onChange={(v) => set("frequencia", v as Frequencia)} opcoes={deRotulos(ROTULO_FREQUENCIA)} vazio={false} />
      </Campo>
      <Campo rotulo="Início" obrigatorio>
        <Texto type="date" value={f.inicio} onChange={(e) => set("inicio", e.target.value)} required />
      </Campo>
      <Campo rotulo="Fim" obrigatorio>
        <Texto type="date" value={f.fim} onChange={(e) => set("fim", e.target.value)} required />
      </Campo>
      <Campo rotulo="Dia do vencimento (1–28)" obrigatorio>
        <Texto type="number" min={1} max={28} step={1} value={f.dia_vencimento} onChange={(e) => set("dia_vencimento", e.target.value)} required />
      </Campo>
      <Campo rotulo="Categoria">
        <Escolha valor={f.categoria_id} onChange={(v) => set("categoria_id", v)} opcoes={paraOpcoes(categorias)} vazio="—" />
      </Campo>
      <Campo rotulo="Centro de custo">
        <Escolha valor={f.centro_custo_id} onChange={(v) => set("centro_custo_id", v)} opcoes={paraOpcoes(opcoes.data?.centros_custo)} vazio="—" />
      </Campo>
      <Campo rotulo="Responsável">
        <Escolha valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} opcoes={paraOpcoes(usuarios.data)} vazio="—" />
      </Campo>
      <Campo rotulo="Situação" obrigatorio>
        <Escolha valor={f.situacao} onChange={(v) => set("situacao", v as SituacaoRecorrencia)} opcoes={deRotulos(ROTULO_SIT_RECORRENCIA)} vazio={false} />
      </Campo>
      <Limite>Cada competência gera um título em rascunho, sem duplicar, dentro da vigência e alinhado à frequência. Nada é cobrado automaticamente.</Limite>
      <Button type="submit" className="mt-4" disabled={salvar.isPending}>
        Salvar registro
      </Button>
    </form>
  );
}

export function FormGerarCompetencia({ recorrencia, onFechar, onGerado }: { recorrencia: Recorrencia | null; onFechar: () => void; onGerado?: (t: Titulo) => void }) {
  return (
    <Drawer
      aberto={!!recorrencia}
      onFechar={onFechar}
      rotulo="RECORRÊNCIAS / COMPETÊNCIA"
      titulo="Gerar competência"
      descricao={
        recorrencia && (
          <>
            {recorrencia.descricao} · <Dinheiro valor={recorrencia.valor_ciclo} />
          </>
        )
      }
    >
      {recorrencia && <CorpoGerar key={recorrencia.id} r={recorrencia} onFechar={onFechar} onGerado={onGerado} />}
    </Drawer>
  );
}

function CorpoGerar({ r, onFechar, onGerado }: { r: Recorrencia; onFechar: () => void; onGerado?: (t: Titulo) => void }) {
  const invalidar = useInvalidarFinanceiro();
  const [comp, setComp] = useState(r.proxima_competencia ?? hojeISO().slice(0, 7));
  const gerar = useMutation({
    mutationFn: () => api.post<Titulo>(`/financeiro/recorrencias/${r.id}/gerar`, { competencia: comp }),
    onSuccess: (t) => {
      invalidar();
      notificar.sucesso("Título criado em rascunho, sem duplicar competência");
      onGerado?.(t);
      onFechar();
    },
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        gerar.mutate();
      }}
    >
      <Campo rotulo="Competência" obrigatorio dica={r.competencias_geradas.length ? `Já geradas: ${r.competencias_geradas.join(", ")}` : undefined}>
        <Texto type="month" value={comp} onChange={(e) => setComp(e.target.value)} required />
      </Campo>
      <Button type="submit" className="mt-5" disabled={gerar.isPending}>
        Gerar título em rascunho
      </Button>
    </form>
  );
}
