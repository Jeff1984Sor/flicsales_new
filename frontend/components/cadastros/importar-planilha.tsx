"use client";

/**
 * Importar planilha — migração de cadastros por planilha (`/bff/nucleo/planilhas/{objeto}/…`).
 *  1) "Baixar modelo (.xlsx)"; 2) enviar o arquivo (.xlsx ou .csv, até 5 MB); 3) simulação automática com contadores,
 *  erros por linha/coluna e prévia; 4) "Importar N registros" só sem erros (tudo ou nada no servidor).
 *
 * `<BotaoImportarPlanilha objeto="empresas" />`  botão + drawer; só aparece com permissão de editar o cadastro
 *   (empresas/pessoas/produtos → nucleo.cadastros.editar; fornecedores/categorias/centros-custo/contas →
 *   financeiro.cadastros.editar).
 * `<DrawerImportarPlanilha objeto aberto onFechar />`  só o drawer.
 */
import { useMutation } from "@tanstack/react-query";
import { Download, FileSpreadsheet, Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { ApiError, api, baixar } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { numero } from "@/lib/format";
import type { ErroImportacao, ObjetoPlanilha, PreviaImportacao, ResultadoImportacao } from "@/lib/tipos-nucleo";

import { useInvalidarCadastros } from "./comum";
import { rotaAusente } from "./consultas";

const LIMITE_BYTES = 5 * 1024 * 1024;

const ROTULO: Record<ObjetoPlanilha, string> = {
  empresas: "Empresas",
  fornecedores: "Fornecedores",
  pessoas: "Pessoas e contatos",
  produtos: "Produtos e serviços",
  categorias: "Categorias",
  "centros-custo": "Centros de custo",
  contas: "Contas financeiras",
};

export const permissaoImportar = (o: ObjetoPlanilha) =>
  o === "empresas" || o === "pessoas" || o === "produtos" ? "nucleo.cadastros.editar" : "financeiro.cadastros.editar";

const ROTULO_ACAO: Record<PreviaImportacao["acao"], string> = { criar: "Criar", atualizar: "Atualizar", ignorar: "Ignorar" };
const TOM_ACAO: Record<PreviaImportacao["acao"], "green" | "azul" | "neutra"> = { criar: "green", atualizar: "azul", ignorar: "neutra" };

const COLUNAS_ERRO: Coluna<ErroImportacao>[] = [
  { id: "linha", titulo: "Linha", celula: (e) => <span className="num">{e.linha}</span> },
  { id: "coluna", titulo: "Coluna", celula: (e) => e.coluna ?? "—" },
  { id: "msg", titulo: "O que corrigir", celula: (e) => <span className="text-amber-ink">{e.mensagem}</span> },
];

const COLUNAS_PREVIA: Coluna<PreviaImportacao>[] = [
  { id: "linha", titulo: "Linha", celula: (p) => <span className="num">{p.linha}</span> },
  { id: "nome", titulo: "Registro", celula: (p) => p.nome ?? "—" },
  { id: "acao", titulo: "Ação", celula: (p) => <Etiqueta tom={TOM_ACAO[p.acao]}>{ROTULO_ACAO[p.acao]}</Etiqueta> },
];

function resultadoDoErro(e: unknown): ResultadoImportacao | null {
  if (!(e instanceof ApiError) || e.status !== 400) return null;
  // aceita {erros, ...} na raiz ou dentro de {detail: {...}}
  const raiz = e.body;
  const detail = raiz && typeof raiz === "object" && "detail" in raiz ? (raiz as { detail: unknown }).detail : null;
  const b = detail && typeof detail === "object" && !Array.isArray(detail) ? detail : raiz;
  if (b && typeof b === "object" && "erros" in b && Array.isArray((b as { erros: unknown }).erros)) {
    const r = b as Partial<ResultadoImportacao> & { erros: ErroImportacao[] };
    return { total: r.total ?? 0, criar: r.criar ?? 0, atualizar: r.atualizar ?? 0, ignorar: r.ignorar ?? 0, erros: r.erros, previa: r.previa ?? [] };
  }
  return null;
}

function mensagemErro(e: unknown) {
  if (rotaAusente(e)) return "A importação por planilha ainda não está disponível neste servidor.";
  if (e instanceof ApiError) return e.message;
  return "Não foi possível ler a planilha.";
}

function Contador({ rotulo, valor, destaque }: { rotulo: string; valor: number; destaque?: boolean }) {
  return (
    <div className="rounded-[10px] border border-line bg-surface px-3 py-2">
      <span className="eyebrow">{rotulo}</span>
      <p className={destaque ? "num text-xl font-bold text-amber-ink" : "num text-xl font-bold"}>{numero(valor)}</p>
    </div>
  );
}

export function DrawerImportarPlanilha({ objeto, aberto, onFechar }: { objeto: ObjetoPlanilha; aberto: boolean; onFechar: () => void }) {
  const invalidar = useInvalidarCadastros();
  const entrada = useRef<HTMLInputElement>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<ResultadoImportacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [baixando, setBaixando] = useState(false);

  const enviar = (simular: boolean, f: File) => {
    const fd = new FormData();
    fd.append("arquivo", f);
    return api.post<ResultadoImportacao>(`/nucleo/planilhas/${objeto}/importar`, fd, { query: { simular } });
  };

  const simular = useMutation({
    mutationFn: (f: File) => enviar(true, f),
    meta: { silencioso: true },
    onMutate: () => {
      setErro(null);
      setResultado(null);
    },
    onSuccess: setResultado,
    onError: (e) => {
      const r = resultadoDoErro(e);
      if (r) setResultado(r);
      else setErro(mensagemErro(e));
    },
  });

  const importar = useMutation({
    mutationFn: (f: File) => enviar(false, f),
    meta: { silencioso: true },
    onSuccess: (r) => {
      invalidar();
      notificar.sucesso(`${numero(r.criar + r.atualizar)} registro(s) importado(s): ${numero(r.criar)} novo(s), ${numero(r.atualizar)} atualizado(s).`);
      fechar();
    },
    onError: (e) => {
      const r = resultadoDoErro(e);
      if (r) {
        setResultado(r);
        setErro("Nada foi gravado: corrija os erros e envie de novo.");
      } else setErro(mensagemErro(e));
    },
  });

  function fechar() {
    setArquivo(null);
    setResultado(null);
    setErro(null);
    onFechar();
  }

  function escolher(f: File | undefined) {
    if (entrada.current) entrada.current.value = "";
    if (!f) return;
    if (!/\.(xlsx|csv)$/i.test(f.name)) {
      setErro("Envie um arquivo .xlsx ou .csv.");
      return;
    }
    if (f.size > LIMITE_BYTES) {
      setErro("Arquivo maior que 5 MB. Divida a planilha em partes.");
      return;
    }
    setArquivo(f);
    simular.mutate(f);
  }

  async function baixarModelo() {
    setBaixando(true);
    setErro(null);
    try {
      await baixar(`/nucleo/planilhas/${objeto}/modelo`, {}, `modelo-${objeto}.xlsx`);
    } catch (e) {
      setErro(rotaAusente(e) ? "O modelo ainda não está disponível neste servidor." : mensagemErro(e));
    } finally {
      setBaixando(false);
    }
  }

  const n = resultado ? resultado.criar + resultado.atualizar : 0;
  const temErros = !!resultado && resultado.erros.length > 0;

  return (
    <Drawer
      aberto={aberto}
      onFechar={fechar}
      largura={560}
      rotulo={`MIGRAÇÃO / ${ROTULO[objeto].toUpperCase()}`}
      titulo="Importar planilha"
      descricao="Baixe o modelo, preencha e envie. Simulamos antes de gravar."
      rodape={
        <>
          <Button type="button" disabled={!arquivo || !resultado || temErros || n === 0 || importar.isPending || simular.isPending} onClick={() => arquivo && importar.mutate(arquivo)}>
            {importar.isPending ? "Importando…" : `Importar ${numero(n)} ${n === 1 ? "registro" : "registros"}`}
          </Button>
          <Button type="button" variant="outline" onClick={fechar}>
            Cancelar
          </Button>
        </>
      }
    >
      <ol className="flex flex-col gap-5">
        <li>
          <span className="eyebrow">1 · MODELO</span>
          <p className="mt-1 mb-2 text-sm text-muted">Colunas em português, uma linha de exemplo (ignorada) e a aba Instruções.</p>
          <Button type="button" variant="outline" disabled={baixando} onClick={baixarModelo}>
            {baixando ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
            Baixar modelo (.xlsx)
          </Button>
        </li>
        <li>
          <span className="eyebrow">2 · ARQUIVO</span>
          <p className="mt-1 mb-2 text-sm text-muted">.xlsx ou .csv (; ou ,), até 5 MB e 5.000 linhas. Linhas já cadastradas são atualizadas, não duplicadas.</p>
          <input ref={entrada} type="file" accept=".xlsx,.csv" className="sr-only" aria-label="Arquivo da planilha" onChange={(e) => escolher(e.target.files?.[0])} />
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" disabled={simular.isPending || importar.isPending} onClick={() => entrada.current?.click()}>
              <Upload className="size-4" />
              {arquivo ? "Trocar arquivo" : "Enviar arquivo"}
            </Button>
            {arquivo && (
              <span className="inline-flex min-w-0 items-center gap-1.5 text-sm">
                <FileSpreadsheet className="size-4 shrink-0 text-primary" />
                <span className="truncate">{arquivo.name}</span>
              </span>
            )}
          </div>
        </li>
        {erro && <li className="rounded-[8px] border border-amber/40 bg-amber/10 px-3 py-2 text-sm text-amber-ink">{erro}</li>}
        {(simular.isPending || resultado) && (
          <li>
            <span className="eyebrow">3 · SIMULAÇÃO</span>
            {simular.isPending ? (
              <p className="mt-2 inline-flex items-center gap-2 text-sm text-muted">
                <Loader2 className="size-4 animate-spin" /> Conferindo a planilha…
              </p>
            ) : (
              resultado && (
                <div className="mt-2 flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Contador rotulo="TOTAL" valor={resultado.total} />
                    <Contador rotulo="CRIAR" valor={resultado.criar} />
                    <Contador rotulo="ATUALIZAR" valor={resultado.atualizar} />
                    <Contador rotulo="IGNORAR" valor={resultado.ignorar} />
                  </div>
                  {temErros ? (
                    <div>
                      <p className="mb-2 text-sm font-semibold text-amber-ink">
                        {numero(resultado.erros.length)} {resultado.erros.length === 1 ? "erro" : "erros"}: corrija na planilha e envie de novo. Nada é gravado com erro.
                      </p>
                      <DataTable colunas={COLUNAS_ERRO} linhas={resultado.erros} chave={(e) => `${e.linha}-${e.coluna ?? ""}-${e.mensagem}`} />
                    </div>
                  ) : (
                    <p className="text-sm text-muted">Sem erros. Confira a prévia e importe.</p>
                  )}
                  {resultado.previa.length > 0 && (
                    <div>
                      <span className="eyebrow">PRÉVIA</span>
                      <div className="mt-2">
                        <DataTable colunas={COLUNAS_PREVIA} linhas={resultado.previa} chave={(p) => p.linha} />
                      </div>
                    </div>
                  )}
                </div>
              )
            )}
          </li>
        )}
      </ol>
    </Drawer>
  );
}

export function BotaoImportarPlanilha({ objeto }: { objeto: ObjetoPlanilha }) {
  const { pode } = useAuth();
  const [aberto, setAberto] = useState(false);
  if (!pode(permissaoImportar(objeto))) return null;
  return (
    <>
      <Button type="button" variant="outline" onClick={() => setAberto(true)}>
        <FileSpreadsheet className="size-4" />
        Importar planilha
      </Button>
      <DrawerImportarPlanilha objeto={objeto} aberto={aberto} onFechar={() => setAberto(false)} />
    </>
  );
}
