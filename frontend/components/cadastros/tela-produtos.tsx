"use client";

/**
 * TelaProdutos — "Produtos e serviços" (protótipo schema "Produtos e serviços") + `DrawerProduto`.
 * Props da tela: `embutida?: boolean` · `idInicial?: number | null`.
 * DrawerProduto: `aberto`, `onFechar`, `produtoId: number | null` (null = novo), `onSalvo?(produto)`.
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
import type { Pagina } from "@/lib/types";
import { ROTULO_TIPO_PRODUTO, type Produto, type Situacao, type TipoProduto } from "@/lib/tipos-nucleo";

import { CHIPS_SITUACAO, RodapeFormulario, alterados, paraEnvio, txt, useInvalidarCadastros } from "./comum";
import { dadosParaIA, mesclarSugestoes } from "./consultas";
import { EnriquecerIA } from "./enriquecer-ia";
import { BotaoImportarPlanilha } from "./importar-planilha";

const POR_PAGINA = 50;

interface FormProduto {
  nome: string;
  tipo: TipoProduto | "";
  codigo: string;
  unidade: string;
  preco_referencia: string;
  recorrente: boolean;
  descricao: string;
  ativo: boolean;
}

const formDe = (p?: Produto): FormProduto => ({
  nome: txt(p?.nome),
  tipo: p?.tipo ?? "servico",
  codigo: txt(p?.codigo),
  unidade: txt(p?.unidade),
  preco_referencia: txt(p?.preco_referencia),
  recorrente: p?.recorrente ?? false,
  descricao: txt(p?.descricao),
  ativo: p?.ativo ?? true,
});

const ROTULOS: Record<string, string> = {
  nome: "Nome",
  tipo: "Tipo",
  codigo: "Código / SKU",
  unidade: "Unidade",
  preco_referencia: "Preço de referência (R$)",
  recorrente: "Recorrente",
  descricao: "Descrição / escopo",
};

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
  onSalvar: (d: Partial<FormProduto>) => void;
  desabilitado?: boolean;
}) {
  const editando = produtoId != null;
  const [f, setF] = useState(inicial);
  const set = <K extends keyof FormProduto>(k: K, v: FormProduto[K]) => setF((x) => ({ ...x, [k]: v }));
  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const atual = paraEnvio(f) as FormProduto;
        const dados = editando ? alterados(paraEnvio(inicial) as FormProduto, atual) : atual;
        if (!editando) delete dados.ativo;
        onSalvar(dados);
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
        <Field label="Código / SKU">
          <Input className="h-9" value={f.codigo} disabled={desabilitado} onChange={(e) => set("codigo", e.target.value)} />
        </Field>
        <Field label="Unidade">
          <Input className="h-9" value={f.unidade} disabled={desabilitado} placeholder="projeto, hora, mês…" onChange={(e) => set("unidade", e.target.value)} />
        </Field>
        <Field label="Preço de referência (R$)">
          <Input className="num h-9" type="number" min="0" step="0.01" value={f.preco_referencia} disabled={desabilitado} onChange={(e) => set("preco_referencia", e.target.value)} />
        </Field>
        <Field label="Recorrente">
          <NativeSelect value={f.recorrente ? "sim" : "nao"} disabled={desabilitado} onChange={(e) => set("recorrente", e.target.value === "sim")}>
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
      <Field label="Descrição / escopo">
        <Textarea value={f.descricao} disabled={desabilitado} onChange={(e) => set("descricao", e.target.value)} />
      </Field>
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
    mutationFn: (d: Partial<FormProduto>) => (produtoId == null ? api.post<Produto>("/nucleo/produtos", d) : api.patch<Produto>(`/nucleo/produtos/${produtoId}`, d)),
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
    { id: "tipo", titulo: "Tipo", celula: (p) => <Etiqueta tom={p.recorrente ? "green" : "neutra"}>{ROTULO_TIPO_PRODUTO[p.tipo]}{p.recorrente ? " · recorrente" : ""}</Etiqueta> },
    { id: "codigo", titulo: "Código / SKU", celula: (p) => p.codigo ?? "—" },
    { id: "unidade", titulo: "Unidade", celula: (p) => p.unidade ?? "—" },
    { id: "preco", titulo: "Preço de referência", alinhar: "direita", celula: (p) => <Dinheiro valor={p.preco_referencia} /> },
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
            { titulo: "Recorrente", valor: (p) => (p.recorrente ? "Sim" : "Não") },
            { titulo: "Ativo", valor: (p) => (p.ativo ? "Sim" : "Não") },
          ],
        }}
      >
        {embutida && <BotaoImportarPlanilha objeto="produtos" />}
        {embutida && podeEditar && <Button onClick={() => setNovo(true)}>+ Produto ou serviço</Button>}
      </BarraFiltros>
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
