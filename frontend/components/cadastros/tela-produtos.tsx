"use client";

/**
 * TelaProdutos — "Produtos e serviços" (protótipo schema "Produtos e serviços") + `DrawerProduto`.
 * Mora na Governança de ajustes (aba Produtos e serviços, `embutida`) e no Comercial (/comercial/produtos).
 * Props da tela: `embutida?: boolean` (sem PageHeader; Importar → "+ Produto ou serviço" numa linha própria) ·
 * `idInicial?: number | null`.
 * DrawerProduto: `aberto`, `onFechar`, `produtoId: number | null` (null = novo), `onSalvo?(produto)`.
 * Formulário: desconto em % ou R$, recorrência (frequência, a cada N, dias da semana no semanal), campos personalizados
 * de produto e campos padrões conforme "Campos de dados" (visível / obrigatório).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Boxes } from "lucide-react";
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
import { decimal, moeda } from "@/lib/format";
import type { Pagina } from "@/lib/types";
import {
  DIAS_SEMANA,
  FREQUENCIAS,
  ROTULO_TIPO_PRODUTO,
  type DescontoTipo,
  type DiaSemana,
  type Frequencia,
  type Produto,
  type Situacao,
  type TipoProduto,
  type ValoresCampos,
} from "@/lib/tipos-nucleo";
import { cn } from "@/lib/utils";

import { useCamposPadroes } from "./campos-padroes";
import { CamposPersonalizados } from "./campos-personalizados";
import { AcoesLista, CHIPS_SITUACAO, RodapeFormulario, alterados, txt, useInvalidarCadastros } from "./comum";
import { dadosParaIA, mesclarSugestoes } from "./consultas";
import { EnriquecerIA } from "./enriquecer-ia";
import { BotaoImportarPlanilha } from "./importar-planilha";

const POR_PAGINA = 50;

interface FormProduto {
  nome: string;
  tipo: TipoProduto;
  codigo: string;
  unidade: string;
  preco_referencia: string;
  desconto_tipo: DescontoTipo | "";
  desconto_valor: string;
  recorrente: boolean;
  frequencia: Frequencia | "";
  intervalo: string;
  dias_semana: DiaSemana[];
  descricao: string;
  ativo: boolean;
  campos_custom: ValoresCampos;
}

/** Corpo enviado à API (campo vazio vai como null). */
interface ProdutoEntrada {
  nome?: string;
  tipo?: TipoProduto;
  codigo?: string | null;
  unidade?: string | null;
  preco_referencia?: string | null;
  desconto_tipo?: DescontoTipo | null;
  desconto_valor?: string | null;
  recorrente?: boolean;
  frequencia?: Frequencia | null;
  intervalo?: number | null;
  dias_semana?: DiaSemana[];
  descricao?: string | null;
  ativo?: boolean;
  campos_custom?: ValoresCampos;
}

const formDe = (p?: Produto): FormProduto => ({
  nome: txt(p?.nome),
  tipo: p?.tipo ?? "servico",
  codigo: txt(p?.codigo),
  unidade: txt(p?.unidade),
  preco_referencia: txt(p?.preco_referencia),
  desconto_tipo: p?.desconto_tipo ?? "",
  desconto_valor: txt(p?.desconto_valor),
  recorrente: p?.recorrente ?? false,
  frequencia: p?.frequencia ?? "",
  intervalo: txt(p?.intervalo),
  dias_semana: p?.dias_semana ?? [],
  descricao: txt(p?.descricao),
  ativo: p?.ativo ?? true,
  campos_custom: p?.campos_custom ?? {},
});

const nulo = (v: string) => (v.trim() === "" ? null : v.trim());

/** Formulário → corpo da API: recorrência e desconto só existem quando ligados. */
function paraEntrada(f: FormProduto): ProdutoEntrada {
  const semanal = f.recorrente && f.frequencia === "semanal";
  return {
    nome: f.nome.trim(),
    tipo: f.tipo,
    codigo: nulo(f.codigo),
    unidade: nulo(f.unidade),
    preco_referencia: nulo(f.preco_referencia),
    desconto_tipo: f.desconto_tipo || null,
    desconto_valor: f.desconto_tipo ? nulo(f.desconto_valor) : null,
    recorrente: f.recorrente,
    frequencia: f.recorrente ? f.frequencia || null : null,
    intervalo: f.recorrente ? (f.frequencia === "semestral" ? 1 : f.intervalo.trim() === "" ? null : Number(f.intervalo)) : null,
    dias_semana: semanal ? DIAS_SEMANA.map((d) => d.valor).filter((d) => f.dias_semana.includes(d)) : [],
    descricao: nulo(f.descricao),
    ativo: f.ativo,
    campos_custom: f.campos_custom,
  };
}

/** Regras do contrato conferidas antes de enviar (o servidor confere de novo). */
function problema(f: FormProduto): string | null {
  if (f.desconto_tipo) {
    const v = Number(f.desconto_valor);
    if (f.desconto_valor.trim() === "" || !Number.isFinite(v)) return "Informe o valor do desconto.";
    if (v < 0) return "O desconto não pode ser negativo.";
    if (f.desconto_tipo === "percentual" && v > 100) return "Desconto percentual vai de 0 a 100%.";
    if (f.desconto_tipo === "valor" && f.preco_referencia.trim() !== "" && v > Number(f.preco_referencia))
      return "O desconto não pode passar do preço de referência.";
  }
  if (f.recorrente) {
    if (!f.frequencia) return "Escolha a frequência da recorrência.";
    if (f.frequencia !== "semestral" && (!Number.isInteger(Number(f.intervalo)) || Number(f.intervalo) < 1)) return "O intervalo é um número inteiro a partir de 1.";
    if (f.frequencia === "semanal" && f.dias_semana.length === 0) return "Marque ao menos um dia da semana.";
  }
  return null;
}

/** Texto local da recorrência enquanto o servidor não devolve `recorrencia_texto`. */
function textoRecorrencia(p: Produto): string {
  if (p.recorrencia_texto) return p.recorrencia_texto;
  return p.recorrente ? "Recorrente" : "—";
}

function textoDesconto(p: Pick<Produto, "desconto_tipo" | "desconto_valor">): string {
  if (!p.desconto_tipo || p.desconto_valor == null) return "—";
  return p.desconto_tipo === "percentual" ? `${decimal(p.desconto_valor)}%` : moeda(p.desconto_valor);
}

const ROTULOS: Record<string, string> = {
  nome: "Nome",
  tipo: "Tipo",
  codigo: "Código / SKU",
  unidade: "Unidade",
  preco_referencia: "Preço de referência (R$)",
  desconto_valor: "Desconto",
  recorrente: "Recorrente",
  frequencia: "Frequência",
  intervalo: "Intervalo",
  descricao: "Descrição / escopo",
};

function DiasSemana({ valor, onChange, disabled }: { valor: DiaSemana[]; onChange: (v: DiaSemana[]) => void; disabled?: boolean }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Dias da semana">
      {DIAS_SEMANA.map((d) => {
        const on = valor.includes(d.valor);
        return (
          <button
            key={d.valor}
            type="button"
            disabled={disabled}
            aria-pressed={on}
            onClick={() => onChange(on ? valor.filter((x) => x !== d.valor) : [...valor, d.valor])}
            className={cn(
              "min-w-11 rounded-[7px] border px-2.5 py-1.5 text-xs transition",
              on ? "border-primary bg-tint font-semibold text-primary" : "border-line bg-surface text-muted hover:border-primary",
            )}
          >
            {d.rotulo}
          </button>
        );
      })}
    </div>
  );
}

function Formulario({
  inicial,
  produtoId,
  formId,
  onSalvar,
  desabilitado,
}: {
  inicial: FormProduto;
  produtoId: number | null;
  formId: string;
  onSalvar: (d: ProdutoEntrada) => void;
  desabilitado?: boolean;
}) {
  const editando = produtoId != null;
  // recorrente sem frequência gravada (cadastro anterior): sugere mensal, a cada 1
  const [f, setF] = useState<FormProduto>(() =>
    inicial.recorrente ? { ...inicial, frequencia: inicial.frequencia || "mensal", intervalo: inicial.intervalo || "1" } : inicial,
  );
  const cp = useCamposPadroes("produto");
  const set = <K extends keyof FormProduto>(k: K, v: FormProduto[K]) => setF((x) => ({ ...x, [k]: v }));
  const unidadeFreq = FREQUENCIAS.find((x) => x.valor === f.frequencia)?.unidade ?? "";
  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const falta = cp.faltando({ ...f }, ROTULOS);
        const erro = falta ? `Preencha ${falta}.` : problema(f);
        if (erro) {
          notificar.erro(erro);
          return;
        }
        const atual = paraEntrada(f);
        if (editando) return onSalvar(alterados(paraEntrada(inicial), atual));
        // cadastro novo: o que está desligado/vazio não vai (o servidor usa o padrão)
        const { ativo: _ativo, desconto_tipo, desconto_valor, frequencia, intervalo, dias_semana, campos_custom, ...resto } = atual;
        void _ativo;
        onSalvar({
          ...resto,
          ...(desconto_tipo ? { desconto_tipo, desconto_valor } : {}),
          ...(atual.recorrente ? { frequencia, intervalo, dias_semana } : {}),
          ...(campos_custom && Object.keys(campos_custom).length ? { campos_custom } : {}),
        });
      }}
    >
      <EnriquecerIA
        objeto="produto"
        registroId={produtoId}
        dados={dadosParaIA(f)}
        rotulos={ROTULOS}
        disabled={desabilitado}
        onAplicar={(v) => setF((x) => mesclarSugestoes(x, v))}
      />
      <Field label="Nome" obrigatorio>
        <Input className="h-9" value={f.nome} disabled={desabilitado} required autoFocus={!editando} onChange={(e) => set("nome", e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tipo" obrigatorio>
          <NativeSelect value={f.tipo} required disabled={desabilitado} onChange={(e) => set("tipo", e.target.value as TipoProduto)}>
            <option value="servico">Serviço</option>
            <option value="produto">Produto</option>
          </NativeSelect>
        </Field>
        {cp.visivel("codigo") && (
          <Field label="Código / SKU" obrigatorio={cp.obrigatorio("codigo")}>
            <Input className="h-9" value={f.codigo} disabled={desabilitado} onChange={(e) => set("codigo", e.target.value)} />
          </Field>
        )}
        {cp.visivel("unidade") && (
          <Field label="Unidade" obrigatorio={cp.obrigatorio("unidade")}>
            <Input className="h-9" value={f.unidade} disabled={desabilitado} placeholder="projeto, hora, mês…" onChange={(e) => set("unidade", e.target.value)} />
          </Field>
        )}
        {cp.visivel("preco_referencia") && (
          <Field label="Preço de referência (R$)" obrigatorio={cp.obrigatorio("preco_referencia")}>
            <Input
              className="num h-9"
              type="number"
              min="0"
              step="0.01"
              value={f.preco_referencia}
              disabled={desabilitado}
              onChange={(e) => set("preco_referencia", e.target.value)}
            />
          </Field>
        )}
        <Field label="Desconto">
          <NativeSelect
            value={f.desconto_tipo}
            disabled={desabilitado}
            onChange={(e) => setF((x) => ({ ...x, desconto_tipo: e.target.value as DescontoTipo | "", desconto_valor: e.target.value ? x.desconto_valor : "" }))}
          >
            <option value="">Sem desconto</option>
            <option value="percentual">Percentual (%)</option>
            <option value="valor">Valor (R$)</option>
          </NativeSelect>
        </Field>
        {f.desconto_tipo && (
          <Field
            label={f.desconto_tipo === "percentual" ? "Desconto (%)" : "Desconto (R$)"}
            obrigatorio
            dica={f.desconto_tipo === "percentual" ? "De 0 a 100%." : "Até o preço de referência."}
          >
            <Input
              className="num h-9"
              type="number"
              min="0"
              max={f.desconto_tipo === "percentual" ? "100" : f.preco_referencia || undefined}
              step="0.01"
              required
              value={f.desconto_valor}
              disabled={desabilitado}
              onChange={(e) => set("desconto_valor", e.target.value)}
            />
          </Field>
        )}
        <Field label="Recorrente">
          <NativeSelect
            value={f.recorrente ? "sim" : "nao"}
            disabled={desabilitado}
            onChange={(e) =>
              setF((x) =>
                e.target.value === "sim"
                  ? { ...x, recorrente: true, frequencia: x.frequencia || "mensal", intervalo: x.intervalo || "1" }
                  : { ...x, recorrente: false },
              )
            }
          >
            <option value="nao">Não</option>
            <option value="sim">Sim</option>
          </NativeSelect>
        </Field>
        {editando && (
          <Field label="Ativo">
            <NativeSelect value={f.ativo ? "sim" : "nao"} disabled={desabilitado} onChange={(e) => set("ativo", e.target.value === "sim")}>
              <option value="sim">Sim</option>
              <option value="nao">Não</option>
            </NativeSelect>
          </Field>
        )}
      </div>
      {f.recorrente && (
        <div className="flex flex-col gap-4 rounded-[10px] border border-line p-4">
          <span className="eyebrow">RECORRÊNCIA</span>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Frequência" obrigatorio>
              <NativeSelect value={f.frequencia} required disabled={desabilitado} onChange={(e) => set("frequencia", e.target.value as Frequencia)}>
                {FREQUENCIAS.map((x) => (
                  <option key={x.valor} value={x.valor}>
                    {x.rotulo}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            {f.frequencia !== "semestral" && (
              <Field label={`A cada quantos ${unidadeFreq}`} obrigatorio>
                <Input className="num h-9" type="number" min="1" step="1" required value={f.intervalo} disabled={desabilitado} onChange={(e) => set("intervalo", e.target.value)} />
              </Field>
            )}
          </div>
          {f.frequencia === "semanal" && (
            <Field label="Dias da semana" obrigatorio>
              <DiasSemana valor={f.dias_semana} onChange={(v) => set("dias_semana", v)} disabled={desabilitado} />
            </Field>
          )}
        </div>
      )}
      {cp.visivel("descricao") && (
        <Field label="Descrição / escopo" obrigatorio={cp.obrigatorio("descricao")}>
          <Textarea value={f.descricao} disabled={desabilitado} onChange={(e) => set("descricao", e.target.value)} />
        </Field>
      )}
      <CamposPersonalizados objeto="produto" valores={f.campos_custom} onChange={(v) => set("campos_custom", v)} somenteLeitura={desabilitado} />
    </form>
  );
}

export function DrawerProduto({ aberto, onFechar, produtoId, onSalvo }: { aberto: boolean; onFechar: () => void; produtoId: number | null; onSalvo?: (p: Produto) => void }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.cadastros.editar");
  const invalidar = useInvalidarCadastros();
  const formId = `f-produto-${produtoId ?? "novo"}`;
  const { data: p } = useQuery({
    queryKey: ["nucleo", "produtos", "detalhe", produtoId],
    queryFn: () => api.get<Produto>(`/nucleo/produtos/${produtoId}`),
    enabled: aberto && produtoId != null,
  });
  const salvar = useMutation({
    mutationFn: (d: ProdutoEntrada) => (produtoId == null ? api.post<Produto>("/nucleo/produtos", d) : api.patch<Produto>(`/nucleo/produtos/${produtoId}`, d)),
    onSuccess: (r) => {
      invalidar("produtos");
      notificar.sucesso("Registro salvo");
      onSalvo?.(r);
      onFechar();
    },
  });
  const pronto = produtoId == null || !!p;
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      titulo={produtoId == null ? "Novo registro · Produtos e serviços" : `Editar · ${p?.nome ?? "…"}`}
      rodape={pronto && podeEditar ? <RodapeFormulario formId={formId} rotulo="Salvar registro" salvando={salvar.isPending} onCancelar={onFechar} /> : undefined}
    >
      {pronto && (
        <Formulario
          key={`${produtoId ?? "novo"}-${p?.id ?? ""}`}
          inicial={formDe(p)}
          produtoId={produtoId}
          formId={formId}
          desabilitado={!podeEditar}
          onSalvar={(d) => (produtoId != null && Object.keys(d).length === 0 ? notificar("Nada mudou.") : salvar.mutate(d))}
        />
      )}
    </Drawer>
  );
}

export function TelaProdutos({ embutida, idInicial = null }: { embutida?: boolean; idInicial?: number | null }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.cadastros.editar");
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState<Situacao>("ativos");
  const [pagina, setPagina] = useState(1);
  const [aberto, setAberto] = useState<number | null>(idInicial);
  const [novo, setNovo] = useState(false);
  useAtalhoNovo(() => podeEditar && setNovo(true));

  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "produtos", "lista", q, situacao, pagina],
    queryFn: () => api.get<Pagina<Produto>>("/nucleo/produtos", { q, situacao, pagina, por_pagina: POR_PAGINA }),
  });

  const colunas: Coluna<Produto>[] = [
    {
      id: "nome",
      titulo: "Nome",
      celula: (p) => (
        <>
          <strong className="text-[13px]">{p.nome}</strong> {!p.ativo && <Etiqueta tom="amber">Inativo</Etiqueta>}
          {p.descricao && <p className="line-clamp-1 text-muted">{p.descricao}</p>}
        </>
      ),
    },
    { id: "tipo", titulo: "Tipo", celula: (p) => <Etiqueta tom={p.recorrente ? "green" : "neutra"}>{ROTULO_TIPO_PRODUTO[p.tipo]}</Etiqueta> },
    { id: "recorrencia", titulo: "Recorrência", celula: (p) => <span className={cn(!p.recorrente && "text-muted")}>{textoRecorrencia(p)}</span> },
    { id: "codigo", titulo: "Código / SKU", celula: (p) => p.codigo ?? "—" },
    { id: "unidade", titulo: "Unidade", celula: (p) => p.unidade ?? "—" },
    { id: "preco", titulo: "Preço de referência", alinhar: "direita", celula: (p) => <Dinheiro valor={p.preco_referencia} /> },
    { id: "desconto", titulo: "Desconto", alinhar: "direita", celula: (p) => <span className="num">{textoDesconto(p)}</span> },
  ];

  return (
    <>
      {!embutida && (
        <PageHeader
          titulo="Produtos e serviços"
          descricao="O que você vende, com preço de referência para propostas."
          acoes={<BotaoImportarPlanilha objeto="produtos" />}
          acao={podeEditar && <Button onClick={() => setNovo(true)}>+ Novo registro</Button>}
        />
      )}
      {embutida && (
        <AcoesLista>
          <BotaoImportarPlanilha objeto="produtos" />
          {podeEditar && <Button onClick={() => setNovo(true)}>+ Produto ou serviço</Button>}
        </AcoesLista>
      )}
      <BarraFiltros
        busca={{ valor: q, onChange: (v) => (setQ(v), setPagina(1)), placeholder: "Filtrar registros desta tela" }}
        chips={{ opcoes: CHIPS_SITUACAO, valor: situacao, onChange: (v) => (setSituacao(v as Situacao), setPagina(1)) }}
        exportar={{
          nome: "produtos-e-servicos",
          linhas: data?.itens ?? [],
          colunas: [
            { titulo: "Nome", valor: (p) => p.nome },
            { titulo: "Tipo", valor: (p) => ROTULO_TIPO_PRODUTO[p.tipo] },
            { titulo: "Código / SKU", valor: (p) => p.codigo },
            { titulo: "Unidade", valor: (p) => p.unidade },
            { titulo: "Preço de referência", valor: (p) => p.preco_referencia },
            { titulo: "Desconto", valor: (p) => (textoDesconto(p) === "—" ? "" : textoDesconto(p)) },
            { titulo: "Recorrente", valor: (p) => (p.recorrente ? "Sim" : "Não") },
            { titulo: "Recorrência", valor: (p) => p.recorrencia_texto ?? "" },
            { titulo: "Ativo", valor: (p) => (p.ativo ? "Sim" : "Não") },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={data?.itens}
        chave={(p) => p.id}
        onLinha={(p) => setAberto(p.id)}
        carregando={isPending}
        vazio={{ icone: Boxes, titulo: "Nenhum registro.", descricao: "Use “Novo registro” para começar." }}
        paginacao={data && data.total > POR_PAGINA ? { pagina, porPagina: POR_PAGINA, total: data.total, onChange: setPagina } : undefined}
      />
      <DrawerProduto aberto={novo} onFechar={() => setNovo(false)} produtoId={null} />
      <DrawerProduto aberto={aberto != null} onFechar={() => setAberto(null)} produtoId={aberto} />
    </>
  );
}
