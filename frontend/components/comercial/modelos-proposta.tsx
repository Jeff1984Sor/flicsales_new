"use client";

/**
 * ModelosProposta — Gestão comercial › "Modelos de proposta": lista + drawer (nome, padrão, validade em dias,
 * condição padrão, introdução, termos, rodapé). As variáveis são clicáveis e entram no texto onde está o cursor.
 *
 * Backend: `GET /comercial/modelos-proposta?incluir_inativos=true`, `POST`, `PATCH /{id}` (`comercial.recursos.*`).
 * Nada se exclui: inativar (o padrão não pode ser inativado). Marcar como padrão desmarca os outros.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";
import { useRef, useState } from "react";

import { DataTable, type Coluna } from "@/components/flic/data-table";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CONDICOES_PROPOSTA, type ModeloProposta, type ModeloPropostaIn, VARIAVEIS_PROPOSTA } from "@/lib/tipos-comercial";

import { useInvalidarComercial } from "./dados";

type CampoTexto = "introducao" | "termos" | "rodape";

export function ModelosProposta() {
  const { pode } = useAuth();
  const editar = pode("comercial.recursos.editar");
  const [form, setForm] = useState<{ aberto: boolean; m: ModeloProposta | null }>({ aberto: false, m: null });

  const { data, isPending } = useQuery({
    queryKey: ["comercial", "modelos-proposta", "todos"],
    queryFn: () => api.get<ModeloProposta[]>("/comercial/modelos-proposta", { incluir_inativos: true }),
  });

  const colunas: Coluna<ModeloProposta>[] = [
    {
      id: "nome",
      titulo: "Nome",
      celula: (m) => (
        <>
          <strong>{m.nome}</strong>
          <p className="line-clamp-1 text-muted">{m.introducao ?? "Sem introdução"}</p>
        </>
      ),
    },
    { id: "validade", titulo: "Validade", celula: (m) => <span className="num">{m.validade_dias} dia(s)</span> },
    { id: "condicao", titulo: "Condição padrão", celula: (m) => m.condicao_padrao ?? "À vista" },
    {
      id: "status",
      titulo: "Status",
      celula: (m) => (
        <div className="flex gap-1">
          {m.padrao && <Etiqueta tom="azul">Padrão</Etiqueta>}
          <Etiqueta tom={m.ativo ? "green" : "amber"}>{m.ativo ? "Ativo" : "Inativo"}</Etiqueta>
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">Textos do PDF e da proposta automática, com variáveis do registro.</p>
        {editar && <Button onClick={() => setForm({ aberto: true, m: null })}>+ Modelo de proposta</Button>}
      </div>
      <DataTable
        colunas={colunas}
        linhas={data}
        chave={(m) => m.id}
        onLinha={(m) => setForm({ aberto: true, m })}
        carregando={isPending}
        vazio={{ icone: FileText, titulo: "Nenhum modelo de proposta.", descricao: "Crie o primeiro para gerar propostas automáticas." }}
      />
      <Drawer
        aberto={form.aberto}
        onFechar={() => setForm({ aberto: false, m: null })}
        rotulo="GESTÃO COMERCIAL / MODELO DE PROPOSTA"
        titulo={form.m ? "Editar modelo de proposta" : "Novo modelo de proposta"}
      >
        {form.aberto && <FormModelo key={form.m?.id ?? "novo"} m={form.m} editar={editar} onFechar={() => setForm({ aberto: false, m: null })} />}
      </Drawer>
    </>
  );
}

function FormModelo({ m, editar, onFechar }: { m: ModeloProposta | null; editar: boolean; onFechar: () => void }) {
  const invalidar = useInvalidarComercial();
  const [nome, setNome] = useState(m?.nome ?? "");
  const [padrao, setPadrao] = useState(m?.padrao ?? false);
  const [validade, setValidade] = useState(String(m?.validade_dias ?? 15));
  const [condicao, setCondicao] = useState(m?.condicao_padrao ?? "");
  const [textos, setTextos] = useState<Record<CampoTexto, string>>({
    introducao: m?.introducao ?? "Prezado(a) {{contato.nome}}, apresentamos a proposta para {{empresa.nome}}.",
    termos: m?.termos ?? "Proposta válida até {{proposta.validade}}. Condição: {{proposta.condicao}}.",
    rodape: m?.rodape ?? "{{responsavel.nome}}",
  });
  const [foco, setFoco] = useState<CampoTexto>("introducao");
  const refs = {
    introducao: useRef<HTMLTextAreaElement>(null),
    termos: useRef<HTMLTextAreaElement>(null),
    rodape: useRef<HTMLTextAreaElement>(null),
  };

  const salvar = useMutation({
    mutationFn: (corpo: ModeloPropostaIn) =>
      m ? api.patch<ModeloProposta>(`/comercial/modelos-proposta/${m.id}`, corpo) : api.post<ModeloProposta>("/comercial/modelos-proposta", corpo),
    onSuccess: () => {
      invalidar();
      notificar("Modelo de proposta salvo");
      onFechar();
    },
  });
  const ativar = useMutation({
    mutationFn: (ativo: boolean) => api.patch<ModeloProposta>(`/comercial/modelos-proposta/${m?.id}`, { ativo } satisfies ModeloPropostaIn),
    onSuccess: (r) => {
      invalidar();
      notificar(r.ativo ? "Modelo reativado" : "Modelo inativado");
      onFechar();
    },
  });

  function inserir(chave: string) {
    const token = `{{${chave}}}`;
    const el = refs[foco].current;
    const atual = textos[foco];
    const ini = el?.selectionStart ?? atual.length;
    const fim = el?.selectionEnd ?? atual.length;
    setTextos((t) => ({ ...t, [foco]: atual.slice(0, ini) + token + atual.slice(fim) }));
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      el.setSelectionRange(ini + token.length, ini + token.length);
    });
  }

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const dias = Number(validade);
    if (!nome.trim()) {
      notificar.erro("Informe o nome do modelo.");
      return;
    }
    if (!Number.isInteger(dias) || dias < 1 || dias > 365) {
      notificar.erro("Validade deve ficar entre 1 e 365 dias.");
      return;
    }
    const vazio = (v: string) => (v.trim() ? v : null);
    salvar.mutate({
      nome: nome.trim(),
      padrao,
      validade_dias: dias,
      condicao_padrao: condicao || null,
      introducao: vazio(textos.introducao),
      termos: vazio(textos.termos),
      rodape: vazio(textos.rodape),
    });
  }

  const campoTexto = (campo: CampoTexto, rotulo: string, linhas: number) => (
    <CampoDrawer rotulo={rotulo} htmlFor={`mp-${campo}`}>
      <Textarea
        id={`mp-${campo}`}
        ref={refs[campo]}
        rows={linhas}
        value={textos[campo]}
        onFocus={() => setFoco(campo)}
        onChange={(e) => setTextos((t) => ({ ...t, [campo]: e.target.value }))}
        className={foco === campo ? "border-primary" : undefined}
      />
    </CampoDrawer>
  );

  return (
    <form id="f-modelo-proposta" onSubmit={enviar}>
      <fieldset disabled={!editar}>
        <CampoDrawer rotulo="Nome" obrigatorio htmlFor="mp-nome">
          <Input id="mp-nome" value={nome} onChange={(e) => setNome(e.target.value)} required maxLength={150} />
        </CampoDrawer>
        <label className="mt-4 flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4 accent-primary" checked={padrao} onChange={(e) => setPadrao(e.target.checked)} />
          Modelo padrão
        </label>
        <p className="mt-1 text-xs text-muted">O padrão já vem escolhido ao gerar proposta. Marcar este desmarca os outros.</p>
        <CampoDrawer rotulo="Validade (dias)" obrigatorio htmlFor="mp-validade" dica="De 1 a 365 dias a partir da emissão.">
          <Input id="mp-validade" type="number" min={1} max={365} step={1} value={validade} onChange={(e) => setValidade(e.target.value)} className="num" />
        </CampoDrawer>
        <CampoDrawer rotulo="Condição padrão" htmlFor="mp-condicao">
          <NativeSelect id="mp-condicao" value={condicao} onChange={(e) => setCondicao(e.target.value)}>
            <option value="">À vista (padrão)</option>
            {CONDICOES_PROPOSTA.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>

        <div className="mt-[17px] rounded-[9px] bg-subtle p-3">
          <span className="eyebrow">VARIÁVEIS</span>
          <p className="mt-1 text-xs text-muted">Clique para inserir no campo de texto selecionado.</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {VARIAVEIS_PROPOSTA.map((v) => (
              <button
                key={v.chave}
                type="button"
                title={v.rotulo}
                onClick={() => inserir(v.chave)}
                className="rounded-md border border-line bg-surface px-2 py-0.5 font-mono text-[11px] text-ink hover:border-primary disabled:opacity-50"
              >
                {`{{${v.chave}}}`}
              </button>
            ))}
          </div>
        </div>

        {campoTexto("introducao", "Introdução", 4)}
        {campoTexto("termos", "Termos", 5)}
        {campoTexto("rodape", "Rodapé", 2)}
      </fieldset>

      {editar && (
        <div className="mt-5 flex flex-wrap gap-2">
          <Button type="submit" disabled={salvar.isPending}>
            {salvar.isPending && <Loader2 className="animate-spin" />}
            Salvar registro
          </Button>
          {m && (
            <Button
              type="button"
              variant="outline"
              disabled={ativar.isPending || (m.ativo && m.padrao)}
              title={m.ativo && m.padrao ? "O modelo padrão não pode ser inativado." : undefined}
              onClick={() => ativar.mutate(!m.ativo)}
            >
              {m.ativo ? "Inativar" : "Reativar"}
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onFechar}>
            Cancelar
          </Button>
        </div>
      )}
      {m?.ativo && m.padrao && <p className="mt-3 text-xs text-muted">O modelo padrão não pode ser inativado: escolha outro padrão antes.</p>}
      <p className="mt-4 text-xs text-muted">Nada se exclui: modelos fora de uso ficam inativos.</p>
    </form>
  );
}
