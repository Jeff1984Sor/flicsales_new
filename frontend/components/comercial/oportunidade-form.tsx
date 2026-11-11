"use client";

/**
 * OportunidadeForm — drawer "Nova oportunidade" (protótipo `newDeal`, 2ª versão) e "Editar oportunidade" (`editDeal`).
 *
 * Props:
 *  - `aberto`, `onFechar`
 *  - `oportunidade?: Oportunidade | null`  edição (inclui troca de etapa e funil)
 *  - `funilId?: number | null`             funil pré-selecionado na criação
 *  - `aoSalvar?: (o: Oportunidade) => void`
 *
 * Empresa: selecionar ou CRIAR pelo nome (nasce como prospect no cadastro único). A nova oportunidade nasce na
 * 1ª etapa do funil. Venda ganha não muda valor por aqui (revisão financeira).
 * Campos padrões seguem "Campos de dados" (invisível some e não é enviado; obrigatório ganha "*") e os campos
 * personalizados de oportunidade aparecem conforme "Exibir na etapa" (funil e etapa atuais).
 */
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CamposPersonalizados } from "@/components/cadastros/campos-personalizados";
import { useCamposPadroes } from "@/components/cadastros/campos-padroes";
import type { Oportunidade, OportunidadeEntrada } from "@/lib/tipos-comercial";
import type { ValoresCampos } from "@/lib/tipos-nucleo";

import { CampoEmpresa, empresaDoTexto, lerForm, nulo, numeroOuNulo, useInvalidarComercial, useOpcoes, useUsuarios } from "./dados";

export function OportunidadeForm({
  aberto,
  onFechar,
  oportunidade,
  funilId,
  aoSalvar,
}: {
  aberto: boolean;
  onFechar: () => void;
  oportunidade?: Oportunidade | null;
  funilId?: number | null;
  aoSalvar?: (o: Oportunidade) => void;
}) {
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      titulo={oportunidade ? "Editar oportunidade" : "Nova oportunidade"}
      descricao={oportunidade ? oportunidade.titulo : "Comece com o essencial. Enriqueça no momento certo."}
    >
      {aberto && <Corpo key={oportunidade?.id ?? "nova"} oportunidade={oportunidade} funilId={funilId} onFechar={onFechar} aoSalvar={aoSalvar} />}
    </Drawer>
  );
}

function Corpo({
  oportunidade: o,
  funilId,
  onFechar,
  aoSalvar,
}: {
  oportunidade?: Oportunidade | null;
  funilId?: number | null;
  onFechar: () => void;
  aoSalvar?: (o: Oportunidade) => void;
}) {
  const { usuario, pode } = useAuth();
  const { data: opcoes } = useOpcoes();
  const { data: usuarios } = useUsuarios();
  const invalidar = useInvalidarComercial();
  const funis = opcoes?.funis ?? [];
  const [funil, setFunil] = useState<string>(String(o?.funil_id ?? funilId ?? funis[0]?.id ?? ""));
  const funilAtual = funis.find((f) => String(f.id) === funil);
  const cp = useCamposPadroes("oportunidade");
  const [campos, setCampos] = useState<ValoresCampos>((o?.campos_custom ?? {}) as ValoresCampos);
  // etapa escolhida no select (null = a do registro, ou a 1ª do funil na criação)
  const [etapaEscolhida, setEtapaEscolhida] = useState<string | null>(null);
  const etapaPadrao = o && o.funil_id === Number(funil) ? (o.etapa_id ?? null) : (funilAtual?.etapas[0]?.id ?? null);
  const etapaAtual = etapaEscolhida != null ? Number(etapaEscolhida) : etapaPadrao;
  const ganha = o?.resultado === "ganha";
  const aberta = !o || o.resultado === "aberta";
  const restrito = !!usuario?.somente_meus_registros;

  const salvar = useMutation({
    mutationFn: (corpo: OportunidadeEntrada) =>
      o ? api.patch<Oportunidade>(`/comercial/oportunidades/${o.id}`, corpo) : api.post<Oportunidade>("/comercial/oportunidades", corpo),
    onSuccess: (r) => {
      invalidar();
      notificar(o ? "Dados comerciais atualizados" : "Oportunidade criada no funil selecionado");
      aoSalvar?.(r);
      onFechar();
    },
  });

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = lerForm(e.currentTarget);
    const empresa = empresaDoTexto(f.empresa ?? "", opcoes?.empresas ?? []);
    // na edição a empresa é obrigatória (na criação continua opcional, como no protótipo)
    if ((o || cp.obrigatorio("empresa_id")) && cp.visivel("empresa_id") && !empresa.empresa_id && !empresa.empresa_nome) {
      notificar("Informe a empresa da oportunidade.");
      return;
    }
    // campo padrão invisível não vai no corpo (undefined some no JSON): o valor gravado fica como está
    const se = <T,>(campo: string, v: T): T | undefined => (cp.visivel(campo) ? v : undefined);
    const corpo: OportunidadeEntrada & { campos_custom?: ValoresCampos } = {
      titulo: f.titulo.trim(),
      funil_id: Number(f.funil_id || funil),
      ...(cp.visivel("empresa_id") ? empresa : {}),
      responsavel_id: numeroOuNulo(f.responsavel_id),
      contato_id: se("contato_id", numeroOuNulo(f.contato_id)),
      previsao_fechamento: se("previsao_fechamento", nulo(f.previsao_fechamento)),
      proxima_acao: se("proxima_acao", nulo(f.proxima_acao)),
      proxima_acao_prazo: se("proxima_acao_prazo", nulo(f.proxima_acao_prazo)),
      interesse: nulo(f.interesse),
      origem: se("origem", nulo(f.origem)),
      necessidade: se("necessidade", nulo(f.necessidade)),
      decisor: se("decisor", nulo(f.decisor)),
      orcamento_concorrencia: se("orcamento_concorrencia", nulo(f.orcamento_concorrencia)),
      criterio_sucesso: se("criterio_sucesso", nulo(f.criterio_sucesso)),
    };
    if (JSON.stringify(campos) !== JSON.stringify(o?.campos_custom ?? {})) corpo.campos_custom = campos;
    if (!ganha) {
      corpo.valor_unico = nulo(f.valor_unico) ?? "0";
      corpo.valor_recorrente_mensal = nulo(f.valor_recorrente_mensal) ?? "0";
    }
    if (o && aberta && f.etapa_id) corpo.etapa_id = Number(f.etapa_id);
    salvar.mutate(corpo);
  }

  return (
    <form onSubmit={enviar}>
      <CampoDrawer rotulo="Título" obrigatorio>
        <Input name="titulo" required maxLength={200} defaultValue={o?.titulo ?? ""} placeholder="Ex.: Consultoria de expansão" />
      </CampoDrawer>
      <CampoDrawer rotulo="Funil" obrigatorio>
        <NativeSelect
          name="funil_id"
          value={funil}
          onChange={(e) => {
            setFunil(e.target.value);
            setEtapaEscolhida(null);
          }}
          disabled={!aberta}
          required
        >
          {funis.map((x) => (
            <option key={x.id} value={x.id}>
              {x.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      {o && aberta && (
        <CampoDrawer rotulo="Etapa" dica="Ganha e Perdida ficam no detalhe da oportunidade.">
          <NativeSelect name="etapa_id" key={funil} value={String(etapaAtual ?? "")} onChange={(e) => setEtapaEscolhida(e.target.value)}>
            {(funilAtual?.etapas ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
      )}
      {cp.visivel("empresa_id") && (
        <CampoDrawer rotulo="Empresa · selecionar ou criar" dica="Nome novo cria a empresa no cadastro compartilhado." obrigatorio={!!o || cp.obrigatorio("empresa_id")}>
          <CampoEmpresa empresas={opcoes?.empresas} defaultValue={o?.empresa_nome} required={!!o || cp.obrigatorio("empresa_id")} />
        </CampoDrawer>
      )}
      <CampoDrawer rotulo="Responsável" obrigatorio>
        <NativeSelect name="responsavel_id" defaultValue={String(o?.responsavel_id ?? usuario?.id ?? "")} disabled={restrito}>
          {(usuarios ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      {cp.visivel("contato_id") && (
        <CampoDrawer rotulo="Contato principal" obrigatorio={cp.obrigatorio("contato_id")}>
          <NativeSelect name="contato_id" defaultValue={String(o?.contato_id ?? "")} required={cp.obrigatorio("contato_id")}>
            <option value="">Não informado</option>
            {(opcoes?.pessoas ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
      )}
      <div className="grid grid-cols-2 gap-3">
        <CampoDrawer rotulo="Valor único previsto (R$)" dica={ganha ? "Venda ganha: ajuste pela revisão financeira." : undefined}>
          <Input name="valor_unico" type="number" min={0} step="0.01" defaultValue={o ? Number(o.valor_unico) : ""} disabled={ganha} />
        </CampoDrawer>
        <CampoDrawer rotulo="Valor recorrente mensal (R$)">
          <Input name="valor_recorrente_mensal" type="number" min={0} step="0.01" defaultValue={o ? Number(o.valor_recorrente_mensal) : ""} disabled={ganha} />
        </CampoDrawer>
      </div>
      {cp.visivel("previsao_fechamento") && (
        <CampoDrawer rotulo="Previsão de fechamento" obrigatorio={cp.obrigatorio("previsao_fechamento")}>
          <Input name="previsao_fechamento" type="date" defaultValue={o?.previsao_fechamento ?? ""} required={cp.obrigatorio("previsao_fechamento")} />
        </CampoDrawer>
      )}
      {cp.visivel("proxima_acao") && (
        <CampoDrawer rotulo="Próxima ação" obrigatorio={cp.obrigatorio("proxima_acao")}>
          <Input name="proxima_acao" maxLength={300} defaultValue={o?.proxima_acao ?? ""} required={cp.obrigatorio("proxima_acao")} />
        </CampoDrawer>
      )}
      {cp.visivel("proxima_acao_prazo") && (
        <CampoDrawer rotulo="Prazo da próxima ação" obrigatorio={cp.obrigatorio("proxima_acao_prazo")}>
          <Input name="proxima_acao_prazo" type="date" defaultValue={o?.proxima_acao_prazo ?? ""} required={cp.obrigatorio("proxima_acao_prazo")} />
        </CampoDrawer>
      )}
      <CampoDrawer rotulo="Interesse · personalizado">
        <NativeSelect name="interesse" defaultValue={o?.interesse ?? "Médio"}>
          {(opcoes?.interesse ?? ["Baixo", "Médio", "Alto"]).map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <details className="mt-5 rounded-[8px] border border-line p-3" open={!!(o?.necessidade || o?.decisor)}>
        <summary className="cursor-pointer text-sm font-semibold">Qualificação e estratégia</summary>
        {cp.visivel("origem") && (
          <CampoDrawer rotulo="Origem / canal" obrigatorio={cp.obrigatorio("origem")}>
            <Input name="origem" defaultValue={o?.origem ?? ""} maxLength={100} required={cp.obrigatorio("origem")} />
          </CampoDrawer>
        )}
        {cp.visivel("necessidade") && (
          <CampoDrawer rotulo="Necessidade e impacto" obrigatorio={cp.obrigatorio("necessidade")}>
            <Textarea name="necessidade" defaultValue={o?.necessidade ?? ""} required={cp.obrigatorio("necessidade")} />
          </CampoDrawer>
        )}
        {cp.visivel("decisor") && (
          <CampoDrawer rotulo="Decisor e processo de compra" obrigatorio={cp.obrigatorio("decisor")}>
            <Input name="decisor" defaultValue={o?.decisor ?? ""} maxLength={200} required={cp.obrigatorio("decisor")} />
          </CampoDrawer>
        )}
        {cp.visivel("orcamento_concorrencia") && (
          <CampoDrawer rotulo="Orçamento / concorrente" obrigatorio={cp.obrigatorio("orcamento_concorrencia")}>
            <Input name="orcamento_concorrencia" defaultValue={o?.orcamento_concorrencia ?? ""} required={cp.obrigatorio("orcamento_concorrencia")} />
          </CampoDrawer>
        )}
        {cp.visivel("criterio_sucesso") && (
          <CampoDrawer rotulo="Critério de sucesso" obrigatorio={cp.obrigatorio("criterio_sucesso")}>
            <Input name="criterio_sucesso" defaultValue={o?.criterio_sucesso ?? ""} required={cp.obrigatorio("criterio_sucesso")} />
          </CampoDrawer>
        )}
      </details>
      <div className="mt-5">
        <CamposPersonalizados
          objeto="oportunidade"
          valores={campos}
          onChange={setCampos}
          etapaId={etapaAtual}
          exibicao={{
            funilId: Number(funil) || null,
            etapaId: etapaAtual,
            ordemDe: (id) => funilAtual?.etapas.find((e) => e.id === id)?.ordem ?? null,
          }}
        />
      </div>
      {!o && <p className="mt-4 text-xs text-muted">A oportunidade nasce na primeira etapa do funil.</p>}
      <div className="mt-5 flex gap-2">
        <Button type="submit" disabled={salvar.isPending || !pode("comercial.oportunidades.editar")}>
          {salvar.isPending && <Loader2 className="animate-spin" />}
          Salvar oportunidade
        </Button>
        <Button type="button" variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
