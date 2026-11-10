"use client";

/**
 * DrawerEmpresa — cadastro/detalhe da empresa no painel lateral (protótipo `newCompany`/`saveCompanyOps` e
 * `companyDetail`/`updateCompanyOps`). Nova: "Cadastro de empresa" (o nome basta). Existente: relacionamentos
 * (oportunidades, recebíveis), contatos com "Novo contato", formulário completo, "Analisar cadastro" e Inativar/Reativar.
 * Renomear atualiza todos os módulos (os vínculos são por id).
 *
 * Props:
 *  - `aberto: boolean`  `onFechar: () => void`
 *  - `empresaId: number | null`                 null = nova empresa
 *  - `nomeInicial?: string`                      pré-preenche o nome (criação contextual)
 *  - `papeisIniciais?: Papel[]`                  padrão ["prospect"]
 *  - `onSalva?: (empresa: EmpresaDetalhe) => void`
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ConfirmDialog } from "@/components/flic/confirm-dialog";
import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { abrirAssistente } from "@/components/flic/eventos";
import { Field } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PAPEIS, type EmpresaDetalhe, type EmpresaEntrada, type Papel, type ValoresCampos } from "@/lib/tipos-nucleo";
import { cn } from "@/lib/utils";

import { CamposPersonalizados } from "./campos-personalizados";
import { RodapeFormulario, SeletorResponsavel, alterados, paraEnvio, txt, useInvalidarCadastros } from "./comum";
import { DrawerPessoa } from "./drawer-pessoa";

interface FormEmpresa {
  nome: string;
  documento: string;
  nome_fantasia: string;
  segmento: string;
  porte: string;
  site: string;
  email_financeiro: string;
  telefone: string;
  endereco: string;
  responsavel_id: number | null;
  papeis: Papel[];
  origem: string;
  observacoes: string;
  campos_custom: ValoresCampos;
}

function formDe(e: EmpresaDetalhe | undefined, nome = "", papeis: Papel[] = ["prospect"]): FormEmpresa {
  return {
    nome: e?.nome ?? nome,
    documento: txt(e?.documento),
    nome_fantasia: txt(e?.nome_fantasia),
    segmento: txt(e?.segmento),
    porte: txt(e?.porte),
    site: txt(e?.site),
    email_financeiro: txt(e?.email_financeiro),
    telefone: txt(e?.telefone),
    endereco: txt(e?.endereco),
    responsavel_id: e?.responsavel_id ?? null,
    papeis: e?.papeis ?? papeis,
    origem: txt(e?.origem),
    observacoes: txt(e?.observacoes),
    campos_custom: e?.campos_custom ?? {},
  };
}

/** Seletor de papéis em chips (multi). */
export function ChipsPapeis({ valor, onChange, disabled }: { valor: Papel[]; onChange: (v: Papel[]) => void; disabled?: boolean }) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Papéis">
      {PAPEIS.map((p) => {
        const on = valor.includes(p.valor);
        return (
          <button
            key={p.valor}
            type="button"
            disabled={disabled}
            aria-pressed={on}
            onClick={() => onChange(on ? valor.filter((x) => x !== p.valor) : [...valor, p.valor])}
            className={cn(
              "rounded-[7px] border px-3 py-1.5 text-xs transition",
              on ? "border-primary bg-tint font-semibold text-primary" : "border-line bg-surface text-muted hover:border-primary",
            )}
          >
            {p.rotulo}
          </button>
        );
      })}
    </div>
  );
}

function Formulario({
  inicial,
  empresa,
  formId,
  onSalvar,
  desabilitado,
}: {
  inicial: FormEmpresa;
  empresa?: EmpresaDetalhe;
  formId: string;
  onSalvar: (dados: EmpresaEntrada) => void;
  desabilitado?: boolean;
}) {
  const [f, setF] = useState(inicial);
  const set = <K extends keyof FormEmpresa>(k: K, v: FormEmpresa[K]) => setF((x) => ({ ...x, [k]: v }));
  const campo = (k: Exclude<keyof FormEmpresa, "responsavel_id" | "papeis" | "campos_custom">) => ({
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
        const atual = paraEnvio(f) as EmpresaEntrada;
        onSalvar(empresa ? alterados<EmpresaEntrada>(paraEnvio(inicial) as EmpresaEntrada, atual) : atual);
      }}
    >
      <Field label="Nome / razão social" obrigatorio>
        <Input {...campo("nome")} required autoFocus={!empresa} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="CNPJ / CPF">
          <Input {...campo("documento")} />
        </Field>
        <Field label="Nome fantasia">
          <Input {...campo("nome_fantasia")} />
        </Field>
        <Field label="Segmento">
          <Input {...campo("segmento")} />
        </Field>
        <Field label="Porte">
          <Input {...campo("porte")} />
        </Field>
        <Field label="Site">
          <Input {...campo("site")} type="url" placeholder="https://" />
        </Field>
        <Field label="E-mail financeiro">
          <Input {...campo("email_financeiro")} type="email" />
        </Field>
        <Field label="Telefone">
          <Input {...campo("telefone")} />
        </Field>
        <Field label="Responsável">
          <SeletorResponsavel valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} disabled={desabilitado} />
        </Field>
      </div>
      <Field label="Endereço">
        <Input {...campo("endereco")} />
      </Field>
      <Field label="Papéis">
        <ChipsPapeis valor={f.papeis} onChange={(v) => set("papeis", v)} disabled={desabilitado} />
      </Field>
      <Field label="Origem">
        <Input {...campo("origem")} />
      </Field>
      <Field label="Observações">
        <Textarea value={f.observacoes} disabled={desabilitado} onChange={(e) => set("observacoes", e.target.value)} />
      </Field>
      <CamposPersonalizados objeto="empresa" valores={f.campos_custom} onChange={(v) => set("campos_custom", v)} somenteLeitura={desabilitado} />
    </form>
  );
}

export function DrawerEmpresa({
  aberto,
  onFechar,
  empresaId,
  nomeInicial,
  papeisIniciais,
  onSalva,
}: {
  aberto: boolean;
  onFechar: () => void;
  empresaId: number | null;
  nomeInicial?: string;
  papeisIniciais?: Papel[];
  onSalva?: (empresa: EmpresaDetalhe) => void;
}) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.cadastros.editar");
  const invalidar = useInvalidarCadastros();
  const [novoContato, setNovoContato] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const formId = `f-empresa-${empresaId ?? "nova"}`;

  const detalhe = useQuery({
    queryKey: ["nucleo", "empresas", "detalhe", empresaId],
    queryFn: () => api.get<EmpresaDetalhe>(`/nucleo/empresas/${empresaId}`),
    enabled: aberto && empresaId != null,
  });
  const e = detalhe.data;

  const salvar = useMutation({
    mutationFn: (dados: EmpresaEntrada) =>
      empresaId == null ? api.post<EmpresaDetalhe>("/nucleo/empresas", dados) : api.patch<EmpresaDetalhe>(`/nucleo/empresas/${empresaId}`, dados),
    onSuccess: (r) => {
      invalidar("empresas");
      notificar.sucesso(empresaId == null ? "Empresa disponível nos três módulos" : "Cadastro e vínculos atualizados");
      onSalva?.(r);
      onFechar();
    },
  });
  const ativo = useMutation({
    mutationFn: (reativar: boolean) =>
      reativar ? api.patch<EmpresaDetalhe>(`/nucleo/empresas/${empresaId}`, { ativo: true }) : api.del<EmpresaDetalhe>(`/nucleo/empresas/${empresaId}`),
    onSuccess: (r) => {
      invalidar("empresas");
      setConfirmar(false);
      notificar(r.ativo ? "Empresa reativada" : "Empresa inativada. O histórico e os vínculos continuam.");
    },
  });

  const pronto = empresaId == null || !!e;

  return (
    <>
      <Drawer
        aberto={aberto}
        onFechar={onFechar}
        rotulo={empresaId == null ? undefined : "EMPRESA / CADASTRO ÚNICO"}
        titulo={empresaId == null ? "Cadastro de empresa" : (e?.nome ?? "Carregando…")}
        descricao={
          empresaId == null
            ? "O nome basta para começar."
            : e && `Empresa compartilhada · ${e.oportunidades} oportunidade(s) · ${e.titulos_receber} recebível(is)`
        }
        rodape={
          pronto &&
          (podeEditar ? (
            <RodapeFormulario
              formId={formId}
              rotulo={empresaId == null ? "Salvar empresa" : "Salvar cadastro"}
              salvando={salvar.isPending}
              onCancelar={onFechar}
              extra={
                e && (
                  <Button type="button" variant="outline" onClick={() => (e.ativo ? setConfirmar(true) : ativo.mutate(true))}>
                    {e.ativo ? "Inativar" : "Reativar"}
                  </Button>
                )
              }
            />
          ) : undefined)
        }
      >
        {e && (
          <div className="mb-6 flex flex-col gap-4">
            <div className="flex flex-wrap gap-1.5">
              {!e.ativo && <Etiqueta tom="amber">Inativa</Etiqueta>}
              {e.papeis.map((p) => (
                <Etiqueta key={p} tom="azul">
                  {PAPEIS.find((x) => x.valor === p)?.rotulo}
                </Etiqueta>
              ))}
            </div>
            <div className="rounded-[10px] border border-electric/20 bg-electric/5 p-4">
              <h3 className="mb-2 text-sm font-bold">Relacionamentos</h3>
              <p className="text-sm">
                {e.oportunidades} oportunidade(s)
                <br />
                {e.titulos_receber} recebível(is) · saldo aberto <Dinheiro valor={e.saldo_receber} />
              </p>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="eyebrow">CONTATOS</span>
                {podeEditar && (
                  <Button type="button" size="sm" variant="outline" onClick={() => setNovoContato(true)}>
                    + Novo contato
                  </Button>
                )}
              </div>
              {e.contatos.length === 0 ? (
                <p className="text-sm text-muted">Nenhum contato vinculado.</p>
              ) : (
                <ul className="divide-y divide-line rounded-[10px] border border-line">
                  {e.contatos.map((c) => (
                    <li key={c.id} className="px-3 py-2 text-sm">
                      <strong>{c.nome}</strong>
                      <p className="text-xs text-muted">{[c.cargo, c.email, c.telefone].filter(Boolean).join(" · ") || "Sem dados de contato"}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <Button type="button" variant="outline" className="self-start" onClick={() => abrirAssistente("Este registro", { tipo: "empresa", id: e.id, rotulo: e.nome })}>
              ✧ Analisar cadastro
            </Button>
          </div>
        )}
        {pronto && (
          <Formulario
            key={`${empresaId ?? "nova"}-${e?.criado_em ?? ""}-${nomeInicial ?? ""}`}
            formId={formId}
            empresa={e}
            inicial={formDe(e, nomeInicial, papeisIniciais)}
            desabilitado={!podeEditar}
            onSalvar={(d) => {
              if (empresaId != null && Object.keys(d).length === 0) {
                notificar("Nada mudou.");
                return;
              }
              salvar.mutate(d);
            }}
          />
        )}
      </Drawer>
      {e && (
        <DrawerPessoa
          aberto={novoContato}
          onFechar={() => setNovoContato(false)}
          pessoaId={null}
          empresaIdInicial={e.id}
          onSalva={() => invalidar("empresas")}
        />
      )}
      <ConfirmDialog
        open={confirmar}
        onOpenChange={setConfirmar}
        titulo="Inativar empresa?"
        descricao="Ela sai das listas e dos seletores, mas nada é apagado: oportunidades, títulos e histórico continuam vinculados."
        confirmar="Inativar"
        destrutivo
        carregando={ativo.isPending}
        onConfirm={() => ativo.mutate(false)}
      />
    </>
  );
}
