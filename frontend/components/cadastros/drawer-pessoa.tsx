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
 * "✧ Enriquecer com IA" separa nome, cargo e contatos de um texto colado.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { Field, NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROTULO_CANAL, type CanalPreferido, type Empresa, type Pessoa, type ValoresCampos } from "@/lib/tipos-nucleo";

import { CamposPersonalizados } from "./campos-personalizados";
import { dadosParaIA, mesclarSugestoes } from "./consultas";
import { BlocoEndereco, enderecoDe, type ValorEndereco } from "./endereco";
import { EnriquecerIA } from "./enriquecer-ia";
import { RodapeFormulario, SeletorResponsavel, alterados, paraEnvio, txt, useInvalidarCadastros } from "./comum";
import { SeletorEmpresa } from "./seletor-empresa";

interface FormPessoa extends ValorEndereco {
  nome: string;
  empresa_id: number | null;
  cargo: string;
  email: string;
  telefone: string;
  responsavel_id: number | null;
  canal_preferido: CanalPreferido | "";
  observacoes: string;
  campos_custom: ValoresCampos;
  usa_endereco_da_empresa: boolean;
}

const ROTULOS: Record<string, string> = {
  nome: "Nome",
  cargo: "Cargo / papel na compra",
  email: "E-mail",
  telefone: "Telefone / WhatsApp",
  canal_preferido: "Canal preferido",
  observacoes: "Observações",
  cep: "CEP",
  logradouro: "Logradouro",
  numero: "Número",
  complemento: "Complemento",
  bairro: "Bairro",
  cidade: "Cidade",
  uf: "UF",
};

function formDe(p: Pessoa | undefined, empresaId: number | null): FormPessoa {
  return {
    nome: txt(p?.nome),
    empresa_id: p ? p.empresa_id : empresaId,
    cargo: txt(p?.cargo),
    email: txt(p?.email),
    telefone: txt(p?.telefone),
    responsavel_id: p?.responsavel_id ?? null,
    canal_preferido: p?.canal_preferido ?? "",
    observacoes: txt(p?.observacoes),
    campos_custom: p?.campos_custom ?? {},
    ...enderecoDe(p),
    usa_endereco_da_empresa: p?.usa_endereco_da_empresa ?? true,
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
  const texto = (k: "nome" | "cargo" | "email" | "telefone") => ({
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
        const atual = paraEnvio({ ...f, ...endereco }) as FormPessoa;
        onSalvar(editando ? alterados(paraEnvio(inicial) as FormPessoa, atual) : atual);
      }}
    >
      <EnriquecerIA
        objeto="pessoa"
        registroId={pessoaId}
        dados={dadosParaIA({ ...f, ...endereco })}
        rotulos={ROTULOS}
        disabled={desabilitado}
        onAplicar={(v) =>
          setF((x) => {
            // sugestão de endereço vale como endereço próprio (parte do endereço que estava na tela)
            const mexeuEndereco = Object.keys(v).some((k) => k in endEmpresa);
            return mexeuEndereco && seguirEmpresa ? mesclarSugestoes({ ...x, ...endereco, usa_endereco_da_empresa: false }, v) : mesclarSugestoes(x, v);
          })
        }
      />
      <Field label="Nome" obrigatorio>
        <Input {...texto("nome")} required autoFocus={!editando} />
      </Field>
      <Field label="Empresa">
        <SeletorEmpresa valor={f.empresa_id} onChange={(id) => set("empresa_id", id)} disabled={desabilitado} />
      </Field>
      <Field label="Cargo / papel na compra">
        <Input {...texto("cargo")} placeholder="Ex.: Diretora de operações (decisora)" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="E-mail">
          <Input {...texto("email")} type="email" />
        </Field>
        <Field label="Telefone / WhatsApp">
          <Input {...texto("telefone")} />
        </Field>
        <Field label="Responsável">
          <SeletorResponsavel valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} disabled={desabilitado} />
        </Field>
        <Field label="Canal preferido">
          <NativeSelect value={f.canal_preferido} disabled={desabilitado} onChange={(e) => set("canal_preferido", e.target.value as CanalPreferido | "")}>
            <option value="">Selecionar</option>
            {(Object.keys(ROTULO_CANAL) as CanalPreferido[]).map((c) => (
              <option key={c} value={c}>
                {ROTULO_CANAL[c]}
              </option>
            ))}
          </NativeSelect>
        </Field>
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
        disabled={desabilitado || seguirEmpresa}
        onChange={(p) => setF((x) => ({ ...x, ...p }))}
        dica={seguirEmpresa && !empresa.data?.cep && !empresa.data?.logradouro ? "A empresa ainda não tem endereço." : undefined}
      />
      <Field label="Observações">
        <Textarea value={f.observacoes} disabled={desabilitado} onChange={(e) => set("observacoes", e.target.value)} />
      </Field>
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
