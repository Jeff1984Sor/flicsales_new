"use client";

/**
 * DrawerPessoa — cadastro de pessoa/contato no painel lateral (protótipo schema "Pessoas e contatos").
 *
 * Props:
 *  - `aberto: boolean`  `onFechar: () => void`
 *  - `pessoaId: number | null`              null = nova pessoa
 *  - `empresaIdInicial?: number | null`     vincula a nova pessoa a esta empresa ("Novo contato" da empresa)
 *  - `onSalva?: (pessoa: Pessoa) => void`
 * Com empresa vinculada, "Usar endereço da empresa" (ligado por padrão) copia e trava o endereço; desligar libera.
 * Vários telefones e e-mails ("+ Adicionar telefone" / "+ Adicionar e-mail"), cada um com tipo e marcador de principal
 * (exatamente um principal; se nenhum for marcado, o primeiro vira principal). Os campos padrões seguem a configuração
 * de "Campos de dados" (visível / obrigatório).
 * Grupo "ORIGEM" (LGPD): base legal e permissões de comunicação — opt-out é exclusivo (marcado, trava as demais;
 * com outra marcada, opt-out fica travado).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { Star, X } from "lucide-react";
import { useState } from "react";

import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { Field, NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  BASES_LEGAIS,
  PERMISSOES_COMUNICACAO,
  ROTULO_CANAL,
  ROTULO_TIPO_EMAIL,
  ROTULO_TIPO_TELEFONE,
  type BaseLegal,
  type CanalPreferido,
  type EmailPessoa,
  type Empresa,
  type PermissaoComunicacao,
  type Pessoa,
  type TelefonePessoa,
  type TipoEmail,
  type TipoTelefone,
  type ValoresCampos,
} from "@/lib/tipos-nucleo";
import { cn } from "@/lib/utils";

import { useCamposPadroes } from "./campos-padroes";
import { CamposPersonalizados } from "./campos-personalizados";
import { BlocoEndereco, enderecoDe, type ValorEndereco } from "./endereco";
import { RodapeFormulario, SeletorResponsavel, alterados, paraEnvio, txt, useInvalidarCadastros } from "./comum";
import { SeletorEmpresa } from "./seletor-empresa";

interface FormPessoa extends ValorEndereco {
  nome: string;
  empresa_id: number | null;
  cargo: string;
  telefones: TelefonePessoa[];
  emails: EmailPessoa[];
  responsavel_id: number | null;
  canal_preferido: CanalPreferido | "";
  observacoes: string;
  campos_custom: ValoresCampos;
  usa_endereco_da_empresa: boolean;
  base_legal: BaseLegal | "";
  permissoes_comunicacao: PermissaoComunicacao[];
}

/** Permissões de comunicação com opt-out exclusivo. */
function PermissoesComunicacao({
  valor,
  onChange,
  disabled,
}: {
  valor: PermissaoComunicacao[];
  onChange: (v: PermissaoComunicacao[]) => void;
  disabled?: boolean;
}) {
  const optOut = valor.includes("opt_out");
  const outras = valor.some((v) => v !== "opt_out");
  return (
    <div className="flex flex-col gap-2" role="group" aria-label="Permissão de comunicação">
      {PERMISSOES_COMUNICACAO.map((p) => {
        const travado = p.valor === "opt_out" ? outras : optOut;
        return (
          <label key={p.valor} className={`flex items-center gap-2.5 text-sm ${travado ? "text-muted" : ""}`}>
            <Checkbox
              checked={valor.includes(p.valor)}
              disabled={disabled || travado}
              onCheckedChange={(on) => {
                if (on !== true) return onChange(valor.filter((x) => x !== p.valor));
                onChange(p.valor === "opt_out" ? ["opt_out"] : [...valor.filter((x) => x !== "opt_out" && x !== p.valor), p.valor]);
              }}
            />
            {p.rotulo}
          </label>
        );
      })}
    </div>
  );
}

const ROTULOS_PESSOA: Record<string, string> = {
  empresa_id: "Empresa",
  cargo: "Cargo / papel na compra",
  telefone: "Telefone",
  email: "E-mail",
  responsavel_id: "Responsável",
  canal_preferido: "Canal preferido",
  observacoes: "Observações",
  base_legal: "Base legal",
};

/** Tira linhas vazias e garante exatamente um principal (o primeiro, se nenhum estiver marcado). */
function normalizar<T extends { principal: boolean }>(itens: T[], valor: (x: T) => string, comValor: (x: T, v: string) => T): T[] {
  const cheios = itens.map((x) => comValor(x, valor(x).trim())).filter((x) => valor(x) !== "");
  const idx = Math.max(0, cheios.findIndex((x) => x.principal));
  return cheios.map((x, i) => ({ ...x, principal: i === idx }));
}
const normTelefones = (l: TelefonePessoa[]) => normalizar(l, (t) => t.numero, (t, v) => ({ ...t, numero: v }));
const normEmails = (l: EmailPessoa[]) => normalizar(l, (x) => x.email, (x, v) => ({ ...x, email: v }));

/** Lista editável de telefones ou e-mails: valor, tipo, marcador de principal e remover. */
function ListaContatos<T extends { tipo: K; principal: boolean }, K extends string>({
  itens,
  onChange,
  disabled,
  valorDe,
  comValor,
  novo,
  tipos,
  rotuloAdicionar,
  rotuloCampo,
  tipoInput,
}: {
  itens: T[];
  onChange: (v: T[]) => void;
  disabled?: boolean;
  valorDe: (x: T) => string;
  comValor: (x: T, v: string) => T;
  novo: T;
  tipos: Record<K, string>;
  rotuloAdicionar: string;
  rotuloCampo: string;
  tipoInput: "tel" | "email";
}) {
  const principalIdx = Math.max(0, itens.findIndex((x) => x.principal));
  const trocar = (i: number, x: T) => onChange(itens.map((y, j) => (j === i ? x : y)));
  return (
    <div className="flex flex-col gap-2">
      {itens.length === 0 && disabled && <p className="text-sm text-muted">—</p>}
      {itens.map((x, i) => {
        const principal = i === principalIdx;
        return (
          <div key={i} className="flex items-center gap-2">
            <Input
              aria-label={rotuloCampo}
              type={tipoInput}
              className="h-9 min-w-0 flex-1"
              value={valorDe(x)}
              disabled={disabled}
              onChange={(e) => trocar(i, comValor(x, e.target.value))}
            />
            <div className="w-32 shrink-0">
              <NativeSelect
                aria-label={`Tipo de ${rotuloCampo.toLowerCase()}`}
                value={x.tipo}
                disabled={disabled}
                onChange={(e) => trocar(i, { ...x, tipo: e.target.value as K })}
              >
                {(Object.keys(tipos) as K[]).map((t) => (
                  <option key={t} value={t}>
                    {tipos[t]}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <button
              type="button"
              disabled={disabled}
              aria-pressed={principal}
              title={principal ? "Principal" : "Marcar como principal"}
              aria-label={principal ? "Principal" : "Marcar como principal"}
              onClick={() => onChange(itens.map((y, j) => ({ ...y, principal: j === i })))}
              className={cn(
                "grid size-9 shrink-0 place-items-center rounded-[7px] border transition",
                principal ? "border-primary bg-tint text-primary" : "border-line text-muted hover:border-primary",
              )}
            >
              <Star className={cn("size-4", principal && "fill-current")} />
            </button>
            {!disabled && (
              <button
                type="button"
                aria-label={`Remover ${rotuloCampo.toLowerCase()}`}
                onClick={() => onChange(itens.filter((_, j) => j !== i))}
                className="grid size-9 shrink-0 place-items-center rounded-[7px] border border-line text-muted transition hover:border-primary"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
        );
      })}
      {!disabled && (
        <Button type="button" size="sm" variant="outline" className="self-start" onClick={() => onChange([...itens, { ...novo, principal: itens.length === 0 }])}>
          {rotuloAdicionar}
        </Button>
      )}
      {itens.length > 1 && <p className="text-xs text-muted">A estrela marca o principal: é ele que aparece nas listas, na busca e nas mensagens.</p>}
    </div>
  );
}

function formDe(p: Pessoa | undefined, empresaId: number | null): FormPessoa {
  return {
    nome: txt(p?.nome),
    empresa_id: p ? p.empresa_id : empresaId,
    cargo: txt(p?.cargo),
    // cadastro novo começa com uma linha de cada; backend antigo: o e-mail/telefone únicos viram a linha principal
    telefones: p ? (p.telefones ?? (p.telefone ? [{ numero: p.telefone, tipo: "celular", principal: true }] : [])) : [{ numero: "", tipo: "celular", principal: true }],
    emails: p ? (p.emails ?? (p.email ? [{ email: p.email, tipo: "comercial", principal: true }] : [])) : [{ email: "", tipo: "comercial", principal: true }],
    responsavel_id: p?.responsavel_id ?? null,
    canal_preferido: p?.canal_preferido ?? "",
    observacoes: txt(p?.observacoes),
    campos_custom: p?.campos_custom ?? {},
    ...enderecoDe(p),
    usa_endereco_da_empresa: p?.usa_endereco_da_empresa ?? true,
    base_legal: p?.base_legal ?? "",
    permissoes_comunicacao: p?.permissoes_comunicacao ?? [],
  };
}

function Formulario({
  inicial,
  pessoaId,
  formId,
  onSalvar,
  desabilitado,
}: {
  inicial: FormPessoa;
  pessoaId: number | null;
  formId: string;
  onSalvar: (d: Partial<FormPessoa>) => void;
  desabilitado?: boolean;
}) {
  const editando = pessoaId != null;
  const [f, setF] = useState(inicial);
  // endereço da empresa escolhida (mesma chave do SeletorEmpresa: vem do cache)
  const empresa = useQuery({
    queryKey: ["nucleo", "empresas", "item", f.empresa_id],
    queryFn: () => api.get<Empresa>(`/nucleo/empresas/${f.empresa_id}`),
    enabled: f.empresa_id != null,
    staleTime: 60_000,
    meta: { silencioso: true },
  });
  const seguirEmpresa = f.empresa_id != null && f.usa_endereco_da_empresa;
  const endEmpresa = enderecoDe(empresa.data);
  // com a marca ligada o endereço exibido e enviado é o da empresa
  const endereco: ValorEndereco = seguirEmpresa ? (empresa.data ? endEmpresa : enderecoDe(f)) : enderecoDe(f);
  const set = <K extends keyof FormPessoa>(k: K, v: FormPessoa[K]) => setF((x) => ({ ...x, [k]: v }));
  const cp = useCamposPadroes("pessoa");
  const texto = (k: "nome" | "cargo") => ({
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
        const telefones = normTelefones(f.telefones);
        const emails = normEmails(f.emails);
        const principalTel = telefones.find((t) => t.principal)?.numero ?? "";
        const principalEmail = emails.find((x) => x.principal)?.email ?? "";
        const falta = cp.faltando({ ...f, telefone: principalTel, email: principalEmail, telefones, emails }, ROTULOS_PESSOA);
        if (falta) {
          notificar.erro(`Preencha ${falta}.`);
          return;
        }
        const atual = paraEnvio({ ...f, ...endereco, telefones, emails }) as FormPessoa;
        if (editando) {
          const base = paraEnvio({ ...inicial, telefones: normTelefones(inicial.telefones), emails: normEmails(inicial.emails) }) as FormPessoa;
          return onSalvar(alterados(base, atual));
        }
        // cadastro novo: campos LGPD vazios não vão (servidor usa o padrão)
        const { base_legal, permissoes_comunicacao, ...resto } = atual;
        onSalvar({
          ...resto,
          ...(base_legal ? { base_legal } : {}),
          ...(permissoes_comunicacao.length ? { permissoes_comunicacao } : {}),
        });
      }}
    >
      <Field label="Nome" obrigatorio>
        <Input {...texto("nome")} required autoFocus={!editando} />
      </Field>
      {cp.visivel("empresa_id") && (
        <Field label="Empresa" obrigatorio={cp.obrigatorio("empresa_id")}>
          <SeletorEmpresa valor={f.empresa_id} onChange={(id) => set("empresa_id", id)} disabled={desabilitado} />
        </Field>
      )}
      {cp.visivel("cargo") && (
        <Field label="Cargo / papel na compra" obrigatorio={cp.obrigatorio("cargo")}>
          <Input {...texto("cargo")} placeholder="Ex.: Diretora de operações (decisora)" />
        </Field>
      )}
      {cp.visivel("telefone") && (
        <Field label="Telefones / WhatsApp" obrigatorio={cp.obrigatorio("telefone")}>
          <ListaContatos<TelefonePessoa, TipoTelefone>
            itens={f.telefones}
            onChange={(v) => set("telefones", v)}
            disabled={desabilitado}
            valorDe={(t) => t.numero}
            comValor={(t, v) => ({ ...t, numero: v })}
            novo={{ numero: "", tipo: "celular", principal: false }}
            tipos={ROTULO_TIPO_TELEFONE}
            rotuloAdicionar="+ Adicionar telefone"
            rotuloCampo="Telefone"
            tipoInput="tel"
          />
        </Field>
      )}
      {cp.visivel("email") && (
        <Field label="E-mails" obrigatorio={cp.obrigatorio("email")}>
          <ListaContatos<EmailPessoa, TipoEmail>
            itens={f.emails}
            onChange={(v) => set("emails", v)}
            disabled={desabilitado}
            valorDe={(x) => x.email}
            comValor={(x, v) => ({ ...x, email: v })}
            novo={{ email: "", tipo: "comercial", principal: false }}
            tipos={ROTULO_TIPO_EMAIL}
            rotuloAdicionar="+ Adicionar e-mail"
            rotuloCampo="E-mail"
            tipoInput="email"
          />
        </Field>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {cp.visivel("responsavel_id") && (
          <Field label="Responsável" obrigatorio={cp.obrigatorio("responsavel_id")}>
            <SeletorResponsavel valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} disabled={desabilitado} />
          </Field>
        )}
        {cp.visivel("canal_preferido") && (
          <Field label="Canal preferido" obrigatorio={cp.obrigatorio("canal_preferido")}>
            <NativeSelect value={f.canal_preferido} disabled={desabilitado} onChange={(e) => set("canal_preferido", e.target.value as CanalPreferido | "")}>
              <option value="">Selecionar</option>
              {(Object.keys(ROTULO_CANAL) as CanalPreferido[]).map((c) => (
                <option key={c} value={c}>
                  {ROTULO_CANAL[c]}
                </option>
              ))}
            </NativeSelect>
          </Field>
        )}
      </div>
      {f.empresa_id != null && (
        <label className="flex items-center justify-between gap-4 rounded-[10px] border border-line px-3.5 py-3">
          <span>
            <span className="block text-sm font-medium">Usar endereço da empresa</span>
            <span className="block text-xs text-muted">
              {f.usa_endereco_da_empresa ? "Copia e acompanha o endereço da empresa." : "Endereço próprio deste contato."}
            </span>
          </span>
          <Switch
            checked={f.usa_endereco_da_empresa}
            disabled={desabilitado}
            onCheckedChange={(v) =>
              // ao desligar, parte do endereço da empresa para editar
              setF((x) => ({ ...x, ...(v ? {} : empresa.data ? endEmpresa : {}), usa_endereco_da_empresa: v }))
            }
          />
        </label>
      )}
      <BlocoEndereco
        valor={endereco}
        obrigatorio={cp.obrigatorio}
        disabled={desabilitado || seguirEmpresa}
        onChange={(p) => setF((x) => ({ ...x, ...p }))}
        dica={seguirEmpresa && !empresa.data?.cep && !empresa.data?.logradouro ? "A empresa ainda não tem endereço." : undefined}
      />
      <div className="flex flex-col gap-4 border-t border-line pt-4">
        <span className="eyebrow">ORIGEM</span>
        {cp.visivel("base_legal") && (
          <Field label="Base legal" obrigatorio={cp.obrigatorio("base_legal")}>
            <NativeSelect value={f.base_legal} disabled={desabilitado} onChange={(e) => set("base_legal", e.target.value as BaseLegal | "")}>
              <option value="">Selecionar</option>
              {BASES_LEGAIS.map((b) => (
                <option key={b.valor} value={b.valor}>
                  {b.rotulo}
                </option>
              ))}
            </NativeSelect>
          </Field>
        )}
        <Field label="Permissão de comunicação" dica="Opt-out não combina com as demais.">
          <PermissoesComunicacao valor={f.permissoes_comunicacao} onChange={(v) => set("permissoes_comunicacao", v)} disabled={desabilitado} />
        </Field>
      </div>
      {cp.visivel("observacoes") && (
        <Field label="Observações" obrigatorio={cp.obrigatorio("observacoes")}>
          <Textarea value={f.observacoes} disabled={desabilitado} onChange={(e) => set("observacoes", e.target.value)} />
        </Field>
      )}
      <CamposPersonalizados objeto="pessoa" valores={f.campos_custom} onChange={(v) => set("campos_custom", v)} somenteLeitura={desabilitado} />
    </form>
  );
}

export function DrawerPessoa({
  aberto,
  onFechar,
  pessoaId,
  empresaIdInicial = null,
  onSalva,
}: {
  aberto: boolean;
  onFechar: () => void;
  pessoaId: number | null;
  empresaIdInicial?: number | null;
  onSalva?: (pessoa: Pessoa) => void;
}) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.cadastros.editar");
  const invalidar = useInvalidarCadastros();
  const formId = `f-pessoa-${pessoaId ?? "nova"}`;
  const detalhe = useQuery({
    queryKey: ["nucleo", "pessoas", "detalhe", pessoaId],
    queryFn: () => api.get<Pessoa>(`/nucleo/pessoas/${pessoaId}`),
    enabled: aberto && pessoaId != null,
  });
  const p = detalhe.data;
  const salvar = useMutation({
    mutationFn: (d: Partial<FormPessoa>) => (pessoaId == null ? api.post<Pessoa>("/nucleo/pessoas", d) : api.patch<Pessoa>(`/nucleo/pessoas/${pessoaId}`, d)),
    onSuccess: (r) => {
      invalidar("pessoas", "empresas");
      notificar.sucesso(pessoaId == null ? "Contato cadastrado" : "Contato atualizado");
      onSalva?.(r);
      onFechar();
    },
  });
  const ativo = useMutation({
    mutationFn: (reativar: boolean) => (reativar ? api.patch<Pessoa>(`/nucleo/pessoas/${pessoaId}`, { ativo: true }) : api.del<Pessoa>(`/nucleo/pessoas/${pessoaId}`)),
    onSuccess: (r) => {
      invalidar("pessoas", "empresas");
      notificar(r.ativo ? "Contato reativado" : "Contato inativado");
    },
  });
  const pronto = pessoaId == null || !!p;

  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      rotulo={pessoaId == null ? undefined : "PESSOA / CONTATO"}
      titulo={pessoaId == null ? "Novo registro · Pessoas e contatos" : (p?.nome ?? "Carregando…")}
      descricao={p ? [p.cargo, p.empresa_nome].filter(Boolean).join(" · ") || "Sem empresa vinculada" : undefined}
      rodape={
        pronto && podeEditar ? (
          <RodapeFormulario
            formId={formId}
            rotulo="Salvar registro"
            salvando={salvar.isPending}
            onCancelar={onFechar}
            extra={
              p && (
                <Button type="button" variant="outline" disabled={ativo.isPending} onClick={() => ativo.mutate(!p.ativo)}>
                  {p.ativo ? "Inativar" : "Reativar"}
                </Button>
              )
            }
          />
        ) : undefined
      }
    >
      {p && !p.ativo && (
        <div className="mb-4">
          <Etiqueta tom="amber">Inativo</Etiqueta>
        </div>
      )}
      {pronto && (
        <Formulario
          key={`${pessoaId ?? "nova"}-${empresaIdInicial ?? ""}-${p?.id ?? ""}`}
          inicial={formDe(p, empresaIdInicial)}
          pessoaId={pessoaId}
          formId={formId}
          desabilitado={!podeEditar}
          onSalvar={(d) => {
            if (pessoaId != null && Object.keys(d).length === 0) {
              notificar("Nada mudou.");
              return;
            }
            salvar.mutate(d);
          }}
        />
      )}
    </Drawer>
  );
}
