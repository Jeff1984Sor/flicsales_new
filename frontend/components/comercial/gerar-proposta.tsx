"use client";

/**
 * GerarPropostaDrawer — "✧ Gerar proposta": cria uma proposta em rascunho a partir da oportunidade
 * (`POST /comercial/oportunidades/{id}/proposta-automatica`) e devolve a proposta criada em `aoCriar`.
 *
 * Props:
 *  - `aberto`, `onFechar`
 *  - `oportunidadeId?`  fixa a oportunidade (drawer da Oportunidade); sem ele, o formulário pede a oportunidade
 *  - `aoCriar(p)`       chamado com a proposta criada (quem chama abre o PropostaDrawer)
 *
 * Valores vêm do cadastro (produto ou valor da oportunidade). "Redigir escopo com IA" só aparece com a IA ligada;
 * se a IA falhar, o servidor segue sem ela e manda um aviso.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ModeloProposta, Proposta, PropostaAutomaticaIn } from "@/lib/tipos-comercial";
import type { EstadoIA } from "@/lib/tipos-orquestracao";
import { moeda } from "@/lib/format";

import { useInvalidarComercial, useOpcoes } from "./dados";

export function GerarPropostaDrawer({
  aberto,
  onFechar,
  oportunidadeId,
  aoCriar,
}: {
  aberto: boolean;
  onFechar: () => void;
  oportunidadeId?: number | null;
  aoCriar: (p: Proposta) => void;
}) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} rotulo="PROPOSTA / AUTOMÁTICA" titulo="✧ Gerar proposta" descricao="Rascunho montado com o modelo, o produto e a oportunidade.">
      {aberto && <Corpo key={oportunidadeId ?? "livre"} oportunidadeId={oportunidadeId ?? null} onFechar={onFechar} aoCriar={aoCriar} />}
    </Drawer>
  );
}

function Corpo({ oportunidadeId, onFechar, aoCriar }: { oportunidadeId: number | null; onFechar: () => void; aoCriar: (p: Proposta) => void }) {
  const invalidar = useInvalidarComercial();
  const { data: opcoes } = useOpcoes();
  const [opId, setOpId] = useState(oportunidadeId != null ? String(oportunidadeId) : "");
  const [modeloEscolhido, setModeloEscolhido] = useState<string | null>(null);
  const [produtoId, setProdutoId] = useState("");
  const [usarIa, setUsarIa] = useState(false);

  const modelos = useQuery({
    queryKey: ["comercial", "modelos-proposta", "ativos"],
    queryFn: () => api.get<ModeloProposta[]>("/comercial/modelos-proposta"),
    meta: { silencioso: true },
  });
  const ia = useQuery({
    queryKey: ["orquestracao", "ia", "estado"],
    queryFn: () => api.get<EstadoIA>("/orquestracao/ia/estado"),
    meta: { silencioso: true },
  });
  const iaLigada = ia.data?.ligada === true;

  const ativos = (modelos.data ?? []).filter((m) => m.ativo);
  // sem escolha explícita, fica o modelo padrão
  const modeloId = modeloEscolhido ?? String(ativos.find((m) => m.padrao)?.id ?? ativos[0]?.id ?? "");
  const modelo = ativos.find((m) => String(m.id) === modeloId);

  const gerar = useMutation({
    mutationFn: () => {
      const corpo: PropostaAutomaticaIn = {
        modelo_proposta_id: modeloId ? Number(modeloId) : null,
        produto_id: produtoId ? Number(produtoId) : null,
        usar_ia: iaLigada && usarIa,
      };
      return api.post<Proposta>(`/comercial/oportunidades/${opId}/proposta-automatica`, corpo);
    },
    onSuccess: (p) => {
      invalidar();
      notificar.sucesso(`Proposta v${p.versao} criada em rascunho`);
      if (p.aviso) notificar.info(p.aviso);
      onFechar();
      aoCriar(p);
    },
  });

  const oportunidades = (opcoes?.oportunidades ?? []).filter((o) => o.resultado === "aberta" || String(o.id) === opId);

  return (
    <form
      id="f-gerar-proposta"
      onSubmit={(e) => {
        e.preventDefault();
        if (!opId) {
          notificar.erro("Escolha a oportunidade.");
          return;
        }
        gerar.mutate();
      }}
    >
      {oportunidadeId == null && (
        <CampoDrawer rotulo="Oportunidade" obrigatorio>
          <NativeSelect value={opId} onChange={(e) => setOpId(e.target.value)} required>
            <option value="">Selecione</option>
            {oportunidades.map((o) => (
              <option key={o.id} value={o.id}>
                {o.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
      )}
      <CampoDrawer
        rotulo="Modelo de proposta"
        dica={
          modelos.isError
            ? "Modelos indisponíveis no momento: a proposta sai com os textos padrão."
            : modelo
              ? `Validade de ${modelo.validade_dias} dia(s) · condição ${modelo.condicao_padrao ?? "à vista"}.`
              : "Cadastre modelos em Gestão comercial."
        }
      >
        <NativeSelect value={modeloId} onChange={(e) => setModeloEscolhido(e.target.value)}>
          {ativos.length === 0 && <option value="">Sem modelo</option>}
          {ativos.map((m) => (
            <option key={m.id} value={m.id}>
              {m.nome}
              {m.padrao ? " (padrão)" : ""}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Produto ou serviço" dica="Opcional. Sem produto, vale o da oportunidade ou o valor dela.">
        <NativeSelect value={produtoId} onChange={(e) => setProdutoId(e.target.value)}>
          <option value="">Da oportunidade</option>
          {(opcoes?.produtos ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.nome}
              {p.preco_referencia ? ` · ${moeda(p.preco_referencia)}` : ""}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      {iaLigada ? (
        <label className="mt-4 flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4 accent-primary" checked={usarIa} onChange={(e) => setUsarIa(e.target.checked)} />
          <span>
            <span className="text-accent">✧</span> Redigir escopo com IA
          </span>
        </label>
      ) : (
        <p className="mt-4 text-xs text-muted">IA desligada: o escopo sai da descrição do produto.</p>
      )}
      <p className="mt-4 text-xs text-muted">
        A proposta nasce em rascunho. Valores vêm do cadastro: a IA só redige o texto do escopo, nunca preço ou desconto.
      </p>
      <div className="mt-5 flex gap-2">
        <Button type="submit" disabled={gerar.isPending || !opId}>
          {gerar.isPending && <Loader2 className="animate-spin" />}
          Gerar proposta
        </Button>
        <Button type="button" variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
