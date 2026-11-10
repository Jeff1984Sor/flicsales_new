"use client";

/**
 * Seções extras do drawer de empresa e de fornecedor (fornecedor é empresa: mesmas rotas).
 *
 *  - `<QuadroSocietario empresaId documento podeEditar onAtualizado? />`
 *      tabela nome · qualificação · entrada (`GET /bff/nucleo/empresas/{id}/socios`) e "Atualizar pela Receita"
 *      (`POST /bff/nucleo/empresas/{id}/cnpj/aplicar`: troca o quadro, preenche só campos vazios e gera o comprovante).
 *  - `<AnexosEmpresa empresaId podeEditar />`
 *      lista com baixar/arquivar e envio com tipo (`/bff/nucleo/empresas/{id}/anexos`); o comprovante CNPJ aparece com
 *      a etiqueta "Cartão CNPJ".
 *  - `aplicarCnpj(empresaId)`  chamada usada logo depois de criar empresa com CNPJ.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Download, Loader2, Paperclip, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";

import { ConfirmDialog } from "@/components/flic/confirm-dialog";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Etiqueta } from "@/components/flic/etiqueta";
import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { ApiError, api, baixar } from "@/lib/api";
import { data as fmtData, dataHora, tamanhoArquivo } from "@/lib/format";
import { ROTULO_TIPO_ANEXO, type AnexoEmpresa, type Empresa, type Socio, type TipoAnexo } from "@/lib/tipos-nucleo";
import { cnpjValido } from "@/lib/validacao";

import { rotaAusente } from "./consultas";

const LIMITE_ANEXO = 10 * 1024 * 1024;

export const aplicarCnpj = (empresaId: number) => api.post<Empresa>(`/nucleo/empresas/${empresaId}/cnpj/aplicar`);

function mensagem(e: unknown, indisponivel: string) {
  if (rotaAusente(e)) return indisponivel;
  if (e instanceof ApiError) return e.message;
  return "Não foi possível concluir. Tente de novo.";
}

function useInvalidarEmpresa(empresaId: number) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["nucleo", "empresas"] });
    qc.invalidateQueries({ queryKey: ["nucleo", "fornecedores"] });
    qc.invalidateQueries({ queryKey: ["nucleo", "pessoas"] });
    qc.invalidateQueries({ queryKey: ["nucleo", "empresa-extras", empresaId] });
  };
}

function Secao({ titulo, acao, children }: { titulo: string; acao?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow">{titulo}</span>
        {acao}
      </div>
      {children}
    </section>
  );
}

const COLUNAS_SOCIOS: Coluna<Socio>[] = [
  {
    id: "nome",
    titulo: "Nome",
    celula: (s) => (
      <>
        <strong className="text-[13px]">{s.nome}</strong>
        {s.documento && <p className="num text-muted">{s.documento}</p>}
      </>
    ),
  },
  { id: "qualif", titulo: "Qualificação", celula: (s) => s.qualificacao ?? "—" },
  { id: "entrada", titulo: "Entrada", celula: (s) => (s.data_entrada ? fmtData(s.data_entrada) : "—") },
];

export function QuadroSocietario({
  empresaId,
  documento,
  podeEditar,
  onAtualizado,
}: {
  empresaId: number;
  documento: string | null;
  podeEditar: boolean;
  onAtualizado?: (e: Empresa) => void;
}) {
  const invalidar = useInvalidarEmpresa(empresaId);
  const [erro, setErro] = useState<string | null>(null);
  const socios = useQuery({
    queryKey: ["nucleo", "empresa-extras", empresaId, "socios"],
    queryFn: () => api.get<Socio[]>(`/nucleo/empresas/${empresaId}/socios`),
    meta: { silencioso: true },
    retry: false,
  });
  const atualizar = useMutation({
    mutationFn: () => aplicarCnpj(empresaId),
    meta: { silencioso: true },
    onMutate: () => setErro(null),
    onSuccess: (e) => {
      invalidar();
      notificar.sucesso("Dados da Receita aplicados. Comprovante anexado.");
      onAtualizado?.(e);
    },
    onError: (e) => setErro(mensagem(e, "A atualização pela Receita ainda não está disponível neste servidor.")),
  });
  const temCnpj = cnpjValido(documento);

  return (
    <Secao
      titulo="QUADRO SOCIETÁRIO"
      acao={
        podeEditar && (
          <Button type="button" size="sm" variant="outline" disabled={!temCnpj || atualizar.isPending} onClick={() => atualizar.mutate()}>
            {atualizar.isPending ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            Atualizar pela Receita
          </Button>
        )
      }
    >
      {socios.isError ? (
        <p className="text-sm text-muted">
          {rotaAusente(socios.error) ? "Quadro societário ainda indisponível neste servidor." : mensagem(socios.error, "")}
        </p>
      ) : socios.data && socios.data.length === 0 ? (
        <p className="text-sm text-muted">
          {temCnpj ? "Sem sócios registrados. Use “Atualizar pela Receita”." : "Informe um CNPJ válido para trazer o quadro societário."}
        </p>
      ) : (
        <DataTable colunas={COLUNAS_SOCIOS} linhas={socios.data} chave={(s) => s.id} carregando={socios.isPending} />
      )}
      {erro && <p className="text-xs text-danger-ink">{erro}</p>}
    </Secao>
  );
}

export function AnexosEmpresa({ empresaId, podeEditar }: { empresaId: number; podeEditar: boolean }) {
  const invalidar = useInvalidarEmpresa(empresaId);
  const entrada = useRef<HTMLInputElement>(null);
  const [tipo, setTipo] = useState<TipoAnexo>("documento");
  const [erro, setErro] = useState<string | null>(null);
  const [arquivar, setArquivar] = useState<AnexoEmpresa | null>(null);
  const [baixando, setBaixando] = useState<number | null>(null);

  const anexos = useQuery({
    queryKey: ["nucleo", "empresa-extras", empresaId, "anexos"],
    queryFn: () => api.get<AnexoEmpresa[]>(`/nucleo/empresas/${empresaId}/anexos`),
    meta: { silencioso: true },
    retry: false,
  });
  const enviar = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("arquivo", f);
      fd.append("tipo", tipo);
      return api.post<AnexoEmpresa>(`/nucleo/empresas/${empresaId}/anexos`, fd);
    },
    meta: { silencioso: true },
    onMutate: () => setErro(null),
    onSuccess: () => {
      invalidar();
      notificar.sucesso("Anexo enviado");
    },
    onError: (e) => setErro(mensagem(e, "Anexos ainda indisponíveis neste servidor.")),
  });
  const arquivarM = useMutation({
    mutationFn: (a: AnexoEmpresa) => api.del(`/nucleo/empresas/${empresaId}/anexos/${a.id}`),
    meta: { silencioso: true },
    onSuccess: () => {
      invalidar();
      setArquivar(null);
      notificar("Anexo arquivado. O registro continua no histórico.");
    },
    onError: (e) => {
      setArquivar(null);
      setErro(mensagem(e, "Anexos ainda indisponíveis neste servidor."));
    },
  });

  async function baixarAnexo(a: AnexoEmpresa) {
    setBaixando(a.id);
    setErro(null);
    try {
      await baixar(`/nucleo/empresas/${empresaId}/anexos/${a.id}/arquivo`, {}, a.nome);
    } catch (e) {
      setErro(mensagem(e, "Download ainda indisponível neste servidor."));
    } finally {
      setBaixando(null);
    }
  }

  function escolher(f: File | undefined) {
    if (entrada.current) entrada.current.value = "";
    if (!f) return;
    if (f.size > LIMITE_ANEXO) {
      setErro("Arquivo maior que 10 MB.");
      return;
    }
    enviar.mutate(f);
  }

  const lista = anexos.data ?? [];

  return (
    <Secao titulo="ANEXOS">
      <p className="text-xs text-muted">
        O comprovante gerado pela consulta traz os dados públicos, a fonte e a hora. O cartão oficial da Receita pode ser anexado aqui como “Cartão CNPJ”.
      </p>
      {anexos.isError ? (
        <p className="text-sm text-muted">{rotaAusente(anexos.error) ? "Anexos ainda indisponíveis neste servidor." : mensagem(anexos.error, "")}</p>
      ) : anexos.isPending ? (
        <p className="text-sm text-muted">Carregando…</p>
      ) : lista.length === 0 ? (
        <p className="text-sm text-muted">Nenhum anexo.</p>
      ) : (
        <ul className="divide-y divide-line rounded-[10px] border border-line">
          {lista.map((a) => (
            <li key={a.id} className="flex items-center gap-3 px-3 py-2">
              <Paperclip className="size-4 shrink-0 text-muted" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {a.nome} {a.tipo === "cartao_cnpj" ? <Etiqueta tom="green">Cartão CNPJ</Etiqueta> : <Etiqueta>{ROTULO_TIPO_ANEXO[a.tipo] ?? a.tipo}</Etiqueta>}
                </p>
                <p className="text-xs text-muted">{[tamanhoArquivo(a.tamanho), a.enviado_por_nome, dataHora(a.criado_em)].filter(Boolean).join(" · ")}</p>
              </div>
              <Button type="button" size="icon-sm" variant="outline" aria-label={`Baixar ${a.nome}`} disabled={baixando === a.id} onClick={() => baixarAnexo(a)}>
                {baixando === a.id ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
              </Button>
              {podeEditar && (
                <Button type="button" size="icon-sm" variant="outline" aria-label={`Arquivar ${a.nome}`} onClick={() => setArquivar(a)}>
                  <Archive className="size-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {podeEditar && !anexos.isError && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-40">
            <NativeSelect aria-label="Tipo do anexo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoAnexo)}>
              {(Object.keys(ROTULO_TIPO_ANEXO) as TipoAnexo[]).map((t) => (
                <option key={t} value={t}>
                  {ROTULO_TIPO_ANEXO[t]}
                </option>
              ))}
            </NativeSelect>
          </div>
          <input
            ref={entrada}
            type="file"
            className="sr-only"
            aria-label="Arquivo do anexo"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.xlsx"
            onChange={(e) => escolher(e.target.files?.[0])}
          />
          <Button type="button" size="sm" variant="outline" disabled={enviar.isPending} onClick={() => entrada.current?.click()}>
            {enviar.isPending ? <Loader2 className="size-4 animate-spin" /> : <Paperclip className="size-4" />}
            Enviar arquivo
          </Button>
          <span className="text-xs text-muted">PDF, imagem, .docx ou .xlsx, até 10 MB.</span>
        </div>
      )}
      {erro && <p className="text-xs text-danger-ink">{erro}</p>}
      <ConfirmDialog
        open={!!arquivar}
        onOpenChange={(o) => !o && setArquivar(null)}
        titulo="Arquivar anexo?"
        descricao="Ele sai da lista, mas nada é apagado: o arquivo e o registro ficam no histórico."
        confirmar="Arquivar"
        carregando={arquivarM.isPending}
        onConfirm={() => arquivar && arquivarM.mutate(arquivar)}
      />
    </Secao>
  );
}
