"use client";

/**
 * Cadastros do Financeiro (permissão `financeiro.cadastros`), fiéis aos `schemas` do protótipo:
 *  - `TelaFornecedores` (+ `DrawerFornecedor`)   fornecedor = empresa com papel fornecedor (cadastro único)
 *  - `TelaCategorias`   (+ `DrawerCategoria`)    natureza receita/despesa e categoria superior
 *  - `TelaCentrosCusto` (+ `DrawerCentroCusto`)  código único
 *  - `TelaContas`       (+ `DrawerConta`)        saldo inicial pode ser negativo; com movimento, saldo e data-base travam
 * Todas as telas aceitam `idInicial?: number | null` (abre o drawer). Drawers: `aberto`, `onFechar`, `id: number | null`.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { FolderTree, Landmark, LayoutGrid, Truck } from "lucide-react";
import { useState } from "react";

import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { Field, NativeSelect } from "@/components/flic/form";
import { PageHeader } from "@/components/flic/page-header";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data as fmtData } from "@/lib/format";
import type { Pagina } from "@/lib/types";
import {
  ROTULO_NATUREZA,
  type Categoria,
  type CentroCusto,
  type ContaFinanceira,
  type Fornecedor,
  type Natureza,
  type Situacao,
} from "@/lib/tipos-nucleo";

import { CHIPS_SITUACAO, RodapeFormulario, SeletorCategoria, SeletorResponsavel, alterados, paraEnvio, txt, useInvalidarCadastros } from "./comum";
import { SeletorEmpresa } from "./seletor-empresa";

const PERM = "financeiro.cadastros.editar";
const DESC = "Cadastros e comandos da operação.";

function AtivoSelect({ valor, onChange, disabled }: { valor: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <NativeSelect value={valor ? "sim" : "nao"} disabled={disabled} onChange={(e) => onChange(e.target.value === "sim")}>
      <option value="sim">Sim</option>
      <option value="nao">Não</option>
    </NativeSelect>
  );
}

const inativo = (ativo: boolean) => !ativo && <Etiqueta tom="amber">Inativo</Etiqueta>;

/** Drawer de formulário genérico: carrega o registro (se id), monta o form com `key` e salva POST/PATCH. */
function useCadastro<T, F extends object>(rota: string, chave: string, id: number | null, aberto: boolean, onFechar: () => void) {
  const invalidar = useInvalidarCadastros();
  const registro = useQuery({ queryKey: ["nucleo", chave, "detalhe", id], queryFn: () => api.get<T>(`${rota}/${id}`), enabled: aberto && id != null });
  const salvar = useMutation({
    mutationFn: (d: Partial<F>) => (id == null ? api.post<T>(rota, d) : api.patch<T>(`${rota}/${id}`, d)),
    onSuccess: () => {
      invalidar(chave);
      notificar.sucesso("Registro salvo");
      onFechar();
    },
  });
  const enviar = (inicial: F, atual: F) => {
    const a = paraEnvio(atual) as F;
    const d = id == null ? a : alterados(paraEnvio(inicial) as F, a);
    if (id != null && Object.keys(d).length === 0) return notificar("Nada mudou.");
    salvar.mutate(d);
  };
  return { registro: registro.data, pronto: id == null || !!registro.data, salvar, enviar };
}

// ================================================================================================= fornecedores
interface FormFornecedor {
  nome: string;
  documento: string;
  contato: string;
  email: string;
  telefone: string;
  categoria_padrao_id: number | null;
  condicao_habitual: string;
  observacoes: string;
  ativo: boolean;
}

export function DrawerFornecedor({ aberto, onFechar, id }: { aberto: boolean; onFechar: () => void; id: number | null }) {
  const { pode } = useAuth();
  const podeEditar = pode(PERM);
  const { registro: r, pronto, salvar, enviar } = useCadastro<Fornecedor, FormFornecedor & { empresa_id?: number | null }>("/nucleo/fornecedores", "fornecedores", id, aberto, onFechar);
  const formId = `f-forn-${id ?? "novo"}`;
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      rotulo={id == null ? undefined : "FORNECEDOR / CADASTRO ÚNICO"}
      titulo={id == null ? "Novo registro · Fornecedores" : `Editar · ${r?.nome ?? "…"}`}
      descricao={r ? `${r.titulos_pagar} título(s) a pagar · mesma empresa usada nos três módulos` : "Fornecedor é uma empresa do cadastro único, com papel fornecedor."}
      rodape={pronto && podeEditar ? <RodapeFormulario formId={formId} rotulo="Salvar registro" salvando={salvar.isPending} onCancelar={onFechar} /> : undefined}
    >
      {pronto && <FormularioFornecedor key={`${id}-${r?.id}`} r={r} formId={formId} desabilitado={!podeEditar} onEnviar={enviar} />}
    </Drawer>
  );
}

function FormularioFornecedor({
  r,
  formId,
  desabilitado,
  onEnviar,
}: {
  r?: Fornecedor;
  formId: string;
  desabilitado?: boolean;
  onEnviar: (inicial: FormFornecedor & { empresa_id?: number | null }, atual: FormFornecedor & { empresa_id?: number | null }) => void;
}) {
  const inicial: FormFornecedor = {
    nome: txt(r?.nome),
    documento: txt(r?.documento),
    contato: txt(r?.contato),
    email: txt(r?.email),
    telefone: txt(r?.telefone),
    categoria_padrao_id: r?.categoria_padrao_id ?? null,
    condicao_habitual: txt(r?.condicao_habitual),
    observacoes: txt(r?.observacoes),
    ativo: r?.ativo ?? true,
  };
  const [f, setF] = useState(inicial);
  const [existente, setExistente] = useState<number | null>(null);
  const set = <K extends keyof FormFornecedor>(k: K, v: FormFornecedor[K]) => setF((x) => ({ ...x, [k]: v }));
  const t = (k: "nome" | "documento" | "contato" | "email" | "telefone" | "condicao_habitual") => ({
    value: f[k],
    disabled: desabilitado,
    className: "h-9",
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => set(k, e.target.value),
  });
  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const { ativo, ...resto } = f;
        if (r) onEnviar(inicial, { ...resto, ativo });
        else if (existente) {
          // empresa existente: manda só o que foi preenchido (não apaga dados que a empresa já tem)
          const preenchidos = Object.fromEntries(Object.entries(paraEnvio(resto)).filter(([k, v]) => v != null && k !== "nome" && k !== "documento"));
          onEnviar(inicial, { ...preenchidos, empresa_id: existente } as FormFornecedor & { empresa_id: number });
        } else onEnviar(inicial, resto as FormFornecedor);
      }}
    >
      {!r && (
        <Field label="Empresa já cadastrada" dica="Opcional. Use para marcar como fornecedor uma empresa que já existe (sem duplicar o cadastro).">
          <SeletorEmpresa valor={existente} onChange={(v) => setExistente(v)} permitirCriar={false} placeholder="Buscar empresa existente" />
        </Field>
      )}
      {!existente && (
        <Field label="Razão social / nome" obrigatorio>
          <Input {...t("nome")} required autoFocus={!r} />
        </Field>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {!existente && (
          <Field label="CPF / CNPJ">
            <Input {...t("documento")} />
          </Field>
        )}
        <Field label="Contato">
          <Input {...t("contato")} />
        </Field>
        <Field label="E-mail">
          <Input {...t("email")} type="email" />
        </Field>
        <Field label="Telefone">
          <Input {...t("telefone")} />
        </Field>
        <Field label="Categoria padrão">
          <SeletorCategoria natureza="despesa" valor={f.categoria_padrao_id} onChange={(v) => set("categoria_padrao_id", v)} disabled={desabilitado} />
        </Field>
        <Field label="Condição habitual">
          <Input {...t("condicao_habitual")} placeholder="Ex.: boleto todo dia 5" />
        </Field>
        {r && (
          <Field label="Ativo">
            <AtivoSelect valor={f.ativo} onChange={(v) => set("ativo", v)} disabled={desabilitado} />
          </Field>
        )}
      </div>
      <Field label="Observações">
        <Textarea value={f.observacoes} disabled={desabilitado} onChange={(e) => set("observacoes", e.target.value)} />
      </Field>
    </form>
  );
}

function Lista<T>({
  titulo,
  descricao,
  rotuloNovo = "+ Novo registro",
  podeEditar,
  onNovo,
  q,
  setQ,
  situacao,
  setSituacao,
  exportar,
  colunas,
  linhas,
  carregando,
  onLinha,
  chave,
  icone,
  filtros,
  rodape,
}: {
  titulo: string;
  descricao: string;
  rotuloNovo?: string;
  podeEditar: boolean;
  onNovo: () => void;
  q: string;
  setQ: (v: string) => void;
  situacao: Situacao;
  setSituacao: (v: Situacao) => void;
  exportar: { nome: string; colunas: { titulo: string; valor: (l: T) => string | number | boolean | null | undefined }[] };
  colunas: Coluna<T>[];
  linhas: T[] | undefined;
  carregando: boolean;
  onLinha: (l: T) => void;
  chave: (l: T) => number;
  icone: React.ComponentType<{ className?: string }>;
  filtros?: React.ReactNode;
  rodape?: React.ReactNode;
}) {
  useAtalhoNovo(() => podeEditar && onNovo());
  return (
    <>
      <PageHeader titulo={titulo} descricao={descricao} acao={podeEditar && <Button onClick={onNovo}>{rotuloNovo}</Button>} />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar registros desta tela" }}
        chips={{ opcoes: CHIPS_SITUACAO, valor: situacao, onChange: (v) => setSituacao(v as Situacao) }}
        exportar={{ ...exportar, linhas: linhas ?? [] }}
      >
        {filtros}
      </BarraFiltros>
      <DataTable
        colunas={colunas}
        linhas={linhas}
        chave={chave}
        onLinha={onLinha}
        carregando={carregando}
        vazio={{ icone, titulo: "Nenhum registro.", descricao: "Use “Novo registro” para começar." }}
      />
      {rodape}
    </>
  );
}

export function TelaFornecedores({ idInicial = null }: { idInicial?: number | null }) {
  const { pode } = useAuth();
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [aberto, setAberto] = useState<number | null>(idInicial);
  const [novo, setNovo] = useState(false);
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "fornecedores", "lista", q, situacao],
    queryFn: () => api.get<Pagina<Fornecedor>>("/nucleo/fornecedores", { q, situacao, por_pagina: 200 }),
  });
  return (
    <>
      <Lista<Fornecedor>
        titulo="Fornecedores"
        descricao={DESC}
        podeEditar={pode(PERM)}
        onNovo={() => setNovo(true)}
        q={q}
        setQ={setQ}
        situacao={situacao}
        setSituacao={setSituacao}
        linhas={data?.itens}
        carregando={isPending}
        chave={(f) => f.id}
        onLinha={(f) => setAberto(f.id)}
        icone={Truck}
        colunas={[
          { id: "nome", titulo: "Razão social / nome", celula: (f) => <><strong className="text-[13px]">{f.nome}</strong> {inativo(f.ativo)}<p className="text-muted">{f.documento ?? "—"}</p></> },
          { id: "contato", titulo: "Contato", celula: (f) => <>{f.contato ?? "—"}<p className="text-muted">{[f.email, f.telefone].filter(Boolean).join(" · ")}</p></> },
          { id: "cat", titulo: "Categoria padrão", celula: (f) => f.categoria_padrao_nome ?? "—" },
          { id: "cond", titulo: "Condição habitual", celula: (f) => f.condicao_habitual ?? "—" },
          { id: "tit", titulo: "A pagar", alinhar: "direita", celula: (f) => <span className="num">{f.titulos_pagar}</span> },
        ]}
        exportar={{
          nome: "fornecedores",
          colunas: [
            { titulo: "Razão social / nome", valor: (f) => f.nome },
            { titulo: "CPF / CNPJ", valor: (f) => f.documento },
            { titulo: "Contato", valor: (f) => f.contato },
            { titulo: "E-mail", valor: (f) => f.email },
            { titulo: "Telefone", valor: (f) => f.telefone },
            { titulo: "Categoria padrão", valor: (f) => f.categoria_padrao_nome },
            { titulo: "Condição habitual", valor: (f) => f.condicao_habitual },
            { titulo: "Ativo", valor: (f) => (f.ativo ? "Sim" : "Não") },
          ],
        }}
      />
      <DrawerFornecedor aberto={novo} onFechar={() => setNovo(false)} id={null} />
      <DrawerFornecedor aberto={aberto != null} onFechar={() => setAberto(null)} id={aberto} />
    </>
  );
}

// ================================================================================================= categorias
interface FormCategoria {
  nome: string;
  natureza: Natureza;
  superior_id: number | null;
  ativo: boolean;
}

export function DrawerCategoria({ aberto, onFechar, id }: { aberto: boolean; onFechar: () => void; id: number | null }) {
  const { pode } = useAuth();
  const podeEditar = pode(PERM);
  const { registro: r, pronto, salvar, enviar } = useCadastro<Categoria, FormCategoria>("/nucleo/categorias", "categorias", id, aberto, onFechar);
  const formId = `f-cat-${id ?? "nova"}`;
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      titulo={id == null ? "Novo registro · Categorias" : `Editar · ${r?.nome ?? "…"}`}
      rodape={pronto && podeEditar ? <RodapeFormulario formId={formId} rotulo="Salvar registro" salvando={salvar.isPending} onCancelar={onFechar} /> : undefined}
    >
      {pronto && <FormularioCategoria key={`${id}-${r?.id}`} r={r} formId={formId} desabilitado={!podeEditar} onEnviar={enviar} />}
    </Drawer>
  );
}

function FormularioCategoria({ r, formId, desabilitado, onEnviar }: { r?: Categoria; formId: string; desabilitado?: boolean; onEnviar: (i: FormCategoria, a: FormCategoria) => void }) {
  const inicial: FormCategoria = { nome: txt(r?.nome), natureza: r?.natureza ?? "receita", superior_id: r?.superior_id ?? null, ativo: r?.ativo ?? true };
  const [f, setF] = useState(inicial);
  const set = <K extends keyof FormCategoria>(k: K, v: FormCategoria[K]) => setF((x) => ({ ...x, [k]: v }));
  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const { ativo, ...resto } = f;
        onEnviar(inicial, (r ? { ...resto, ativo } : resto) as FormCategoria);
      }}
    >
      <Field label="Nome" obrigatorio>
        <Input className="h-9" value={f.nome} required autoFocus={!r} disabled={desabilitado} onChange={(e) => set("nome", e.target.value)} />
      </Field>
      <Field label="Natureza" obrigatorio>
        <NativeSelect value={f.natureza} disabled={desabilitado} onChange={(e) => setF((x) => ({ ...x, natureza: e.target.value as Natureza, superior_id: null }))}>
          <option value="receita">Receita</option>
          <option value="despesa">Despesa</option>
        </NativeSelect>
      </Field>
      <Field label="Categoria superior" dica="Opcional. Mesma natureza.">
        <SeletorCategoria natureza={f.natureza} valor={f.superior_id} onChange={(v) => set("superior_id", v)} disabled={desabilitado} vazio="Nenhuma (categoria principal)" />
      </Field>
      {r && (
        <Field label="Ativo">
          <AtivoSelect valor={f.ativo} onChange={(v) => set("ativo", v)} disabled={desabilitado} />
        </Field>
      )}
    </form>
  );
}

export function TelaCategorias({ idInicial = null }: { idInicial?: number | null }) {
  const { pode } = useAuth();
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [natureza, setNatureza] = useState<Natureza | "">("");
  const [aberto, setAberto] = useState<number | null>(idInicial);
  const [novo, setNovo] = useState(false);
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "categorias", "lista", q, situacao, natureza],
    queryFn: () => api.get<Categoria[]>("/nucleo/categorias", { q, situacao, natureza }),
  });
  return (
    <>
      <Lista<Categoria>
        titulo="Categorias"
        descricao={DESC}
        podeEditar={pode(PERM)}
        onNovo={() => setNovo(true)}
        q={q}
        setQ={setQ}
        situacao={situacao}
        setSituacao={setSituacao}
        linhas={data}
        carregando={isPending}
        chave={(c) => c.id}
        onLinha={(c) => setAberto(c.id)}
        icone={FolderTree}
        filtros={
          <div className="w-40">
            <NativeSelect aria-label="Natureza" value={natureza} onChange={(e) => setNatureza(e.target.value as Natureza | "")}>
              <option value="">Todas as naturezas</option>
              <option value="receita">Receita</option>
              <option value="despesa">Despesa</option>
            </NativeSelect>
          </div>
        }
        colunas={[
          { id: "nome", titulo: "Nome", celula: (c) => <><strong className="text-[13px]">{c.nome}</strong> {inativo(c.ativo)}</> },
          { id: "nat", titulo: "Natureza", celula: (c) => <Etiqueta tom={c.natureza === "receita" ? "green" : "amber"}>{ROTULO_NATUREZA[c.natureza]}</Etiqueta> },
          { id: "sup", titulo: "Categoria superior", celula: (c) => c.superior_nome ?? "—" },
          { id: "ativo", titulo: "Ativo", celula: (c) => (c.ativo ? "Sim" : "Não") },
        ]}
        exportar={{
          nome: "categorias",
          colunas: [
            { titulo: "Nome", valor: (c) => c.nome },
            { titulo: "Natureza", valor: (c) => ROTULO_NATUREZA[c.natureza] },
            { titulo: "Categoria superior", valor: (c) => c.superior_nome },
            { titulo: "Ativo", valor: (c) => (c.ativo ? "Sim" : "Não") },
          ],
        }}
      />
      <DrawerCategoria aberto={novo} onFechar={() => setNovo(false)} id={null} />
      <DrawerCategoria aberto={aberto != null} onFechar={() => setAberto(null)} id={aberto} />
    </>
  );
}

// ================================================================================================= centros de custo
interface FormCentro {
  nome: string;
  codigo: string;
  responsavel_id: number | null;
  ativo: boolean;
}

export function DrawerCentroCusto({ aberto, onFechar, id }: { aberto: boolean; onFechar: () => void; id: number | null }) {
  const { pode } = useAuth();
  const podeEditar = pode(PERM);
  const { registro: r, pronto, salvar, enviar } = useCadastro<CentroCusto, FormCentro>("/nucleo/centros-custo", "centros-custo", id, aberto, onFechar);
  const formId = `f-cc-${id ?? "novo"}`;
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      titulo={id == null ? "Novo registro · Centros de custo" : `Editar · ${r?.nome ?? "…"}`}
      rodape={pronto && podeEditar ? <RodapeFormulario formId={formId} rotulo="Salvar registro" salvando={salvar.isPending} onCancelar={onFechar} /> : undefined}
    >
      {pronto && <FormularioCentro key={`${id}-${r?.id}`} r={r} formId={formId} desabilitado={!podeEditar} onEnviar={enviar} />}
    </Drawer>
  );
}

function FormularioCentro({ r, formId, desabilitado, onEnviar }: { r?: CentroCusto; formId: string; desabilitado?: boolean; onEnviar: (i: FormCentro, a: FormCentro) => void }) {
  const inicial: FormCentro = { nome: txt(r?.nome), codigo: txt(r?.codigo), responsavel_id: r?.responsavel_id ?? null, ativo: r?.ativo ?? true };
  const [f, setF] = useState(inicial);
  const set = <K extends keyof FormCentro>(k: K, v: FormCentro[K]) => setF((x) => ({ ...x, [k]: v }));
  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const { ativo, ...resto } = f;
        onEnviar(inicial, (r ? { ...resto, ativo } : resto) as FormCentro);
      }}
    >
      <Field label="Nome" obrigatorio>
        <Input className="h-9" value={f.nome} required autoFocus={!r} disabled={desabilitado} onChange={(e) => set("nome", e.target.value)} />
      </Field>
      <Field label="Código" obrigatorio dica="Único. Ex.: OP">
        <Input className="num h-9 uppercase" value={f.codigo} required disabled={desabilitado} onChange={(e) => set("codigo", e.target.value)} />
      </Field>
      <Field label="Responsável">
        <SeletorResponsavel valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} disabled={desabilitado} />
      </Field>
      {r && (
        <Field label="Ativo">
          <AtivoSelect valor={f.ativo} onChange={(v) => set("ativo", v)} disabled={desabilitado} />
        </Field>
      )}
    </form>
  );
}

export function TelaCentrosCusto({ idInicial = null }: { idInicial?: number | null }) {
  const { pode } = useAuth();
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [aberto, setAberto] = useState<number | null>(idInicial);
  const [novo, setNovo] = useState(false);
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "centros-custo", "lista", q, situacao],
    queryFn: () => api.get<CentroCusto[]>("/nucleo/centros-custo", { q, situacao }),
  });
  return (
    <>
      <Lista<CentroCusto>
        titulo="Centros de custo"
        descricao={DESC}
        podeEditar={pode(PERM)}
        onNovo={() => setNovo(true)}
        q={q}
        setQ={setQ}
        situacao={situacao}
        setSituacao={setSituacao}
        linhas={data}
        carregando={isPending}
        chave={(c) => c.id}
        onLinha={(c) => setAberto(c.id)}
        icone={LayoutGrid}
        colunas={[
          { id: "nome", titulo: "Nome", celula: (c) => <><strong className="text-[13px]">{c.nome}</strong> {inativo(c.ativo)}</> },
          { id: "codigo", titulo: "Código", celula: (c) => <span className="num">{c.codigo}</span> },
          { id: "resp", titulo: "Responsável", celula: (c) => c.responsavel_nome ?? "—" },
          { id: "ativo", titulo: "Ativo", celula: (c) => (c.ativo ? "Sim" : "Não") },
        ]}
        exportar={{
          nome: "centros-de-custo",
          colunas: [
            { titulo: "Nome", valor: (c) => c.nome },
            { titulo: "Código", valor: (c) => c.codigo },
            { titulo: "Responsável", valor: (c) => c.responsavel_nome },
            { titulo: "Ativo", valor: (c) => (c.ativo ? "Sim" : "Não") },
          ],
        }}
      />
      <DrawerCentroCusto aberto={novo} onFechar={() => setNovo(false)} id={null} />
      <DrawerCentroCusto aberto={aberto != null} onFechar={() => setAberto(null)} id={aberto} />
    </>
  );
}

// ================================================================================================= contas financeiras
interface FormConta {
  nome: string;
  instituicao: string;
  saldo_inicial: string;
  data_base: string;
  ativo: boolean;
}

export function DrawerConta({ aberto, onFechar, id }: { aberto: boolean; onFechar: () => void; id: number | null }) {
  const { pode } = useAuth();
  const podeEditar = pode(PERM);
  const { registro: r, pronto, salvar, enviar } = useCadastro<ContaFinanceira, FormConta>("/nucleo/contas", "contas", id, aberto, onFechar);
  const formId = `f-conta-${id ?? "nova"}`;
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      titulo={id == null ? "Novo registro · Contas financeiras" : `Editar · ${r?.nome ?? "…"}`}
      rodape={pronto && podeEditar ? <RodapeFormulario formId={formId} rotulo="Salvar registro" salvando={salvar.isPending} onCancelar={onFechar} /> : undefined}
    >
      {pronto && <FormularioConta key={`${id}-${r?.id}`} r={r} formId={formId} desabilitado={!podeEditar} onEnviar={enviar} />}
    </Drawer>
  );
}

function FormularioConta({ r, formId, desabilitado, onEnviar }: { r?: ContaFinanceira; formId: string; desabilitado?: boolean; onEnviar: (i: FormConta, a: FormConta) => void }) {
  const inicial: FormConta = { nome: txt(r?.nome), instituicao: txt(r?.instituicao), saldo_inicial: txt(r?.saldo_inicial), data_base: txt(r?.data_base), ativo: r?.ativo ?? true };
  const [f, setF] = useState(inicial);
  const set = <K extends keyof FormConta>(k: K, v: FormConta[K]) => setF((x) => ({ ...x, [k]: v }));
  const travado = desabilitado || !!r?.tem_movimento;
  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const { ativo, ...resto } = f;
        onEnviar(inicial, (r ? { ...resto, ativo } : resto) as FormConta);
      }}
    >
      <Field label="Nome da conta" obrigatorio>
        <Input className="h-9" value={f.nome} required autoFocus={!r} disabled={desabilitado} onChange={(e) => set("nome", e.target.value)} />
      </Field>
      <Field label="Instituição / identificação gerencial">
        <Input className="h-9" value={f.instituicao} disabled={desabilitado} onChange={(e) => set("instituicao", e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Saldo inicial (R$)" obrigatorio dica="Pode ser negativo.">
          <Input className="num h-9" type="number" step="0.01" required value={f.saldo_inicial} disabled={travado} onChange={(e) => set("saldo_inicial", e.target.value)} />
        </Field>
        <Field label="Data-base do saldo" obrigatorio>
          <Input className="h-9" type="date" required value={f.data_base} disabled={travado} onChange={(e) => set("data_base", e.target.value)} />
        </Field>
      </div>
      {r?.tem_movimento && <p className="rounded-[8px] bg-amber/10 px-3 py-2 text-xs text-amber-ink">Conta com movimentos: preserve saldo inicial e data-base.</p>}
      {r && (
        <Field label="Ativo">
          <AtivoSelect valor={f.ativo} onChange={(v) => set("ativo", v)} disabled={desabilitado} />
        </Field>
      )}
    </form>
  );
}

export function TelaContas({ idInicial = null }: { idInicial?: number | null }) {
  const { pode } = useAuth();
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [aberto, setAberto] = useState<number | null>(idInicial);
  const [novo, setNovo] = useState(false);
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "contas", "lista", q, situacao],
    queryFn: () => api.get<ContaFinanceira[]>("/nucleo/contas", { q, situacao }),
  });
  return (
    <>
      <Lista<ContaFinanceira>
        titulo="Contas financeiras"
        descricao={DESC}
        podeEditar={pode(PERM)}
        onNovo={() => setNovo(true)}
        q={q}
        setQ={setQ}
        situacao={situacao}
        setSituacao={setSituacao}
        linhas={data}
        carregando={isPending}
        chave={(c) => c.id}
        onLinha={(c) => setAberto(c.id)}
        icone={Landmark}
        colunas={[
          { id: "nome", titulo: "Nome da conta", celula: (c) => <><strong className="text-[13px]">{c.nome}</strong> {inativo(c.ativo)}</> },
          { id: "inst", titulo: "Instituição / identificação gerencial", celula: (c) => c.instituicao ?? "—" },
          { id: "saldo", titulo: "Saldo inicial", alinhar: "direita", celula: (c) => <Dinheiro valor={c.saldo_inicial} /> },
          { id: "base", titulo: "Data-base do saldo", celula: (c) => fmtData(c.data_base) },
          { id: "mov", titulo: "Movimento", celula: (c) => (c.tem_movimento ? <Etiqueta tom="azul">Com movimentos</Etiqueta> : <span className="text-muted">Sem movimentos</span>) },
        ]}
        exportar={{
          nome: "contas-financeiras",
          colunas: [
            { titulo: "Nome da conta", valor: (c) => c.nome },
            { titulo: "Instituição", valor: (c) => c.instituicao },
            { titulo: "Saldo inicial", valor: (c) => c.saldo_inicial },
            { titulo: "Data-base", valor: (c) => fmtData(c.data_base) },
            { titulo: "Ativo", valor: (c) => (c.ativo ? "Sim" : "Não") },
          ],
        }}
        rodape={<p className="mt-4 text-xs text-muted">Contas gerenciais: sem conciliação bancária. O saldo atual por conta fica em Caixa.</p>}
      />
      <DrawerConta aberto={novo} onFechar={() => setNovo(false)} id={null} />
      <DrawerConta aberto={aberto != null} onFechar={() => setAberto(null)} id={aberto} />
    </>
  );
}
