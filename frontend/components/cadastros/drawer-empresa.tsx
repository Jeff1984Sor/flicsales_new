"use client";

/**
 * DrawerEmpresa — cadastro/detalhe da empresa no painel lateral (protótipo `newCompany`/`saveCompanyOps` e
 * `companyDetail`/`updateCompanyOps`). Nova: "Cadastro de empresa" (o nome basta). Existente: relacionamentos
 * (oportunidades, recebíveis), contatos com "Novo contato", formulário completo, "Analisar cadastro" e Inativar/Reativar.
 * Renomear atualiza todos os módulos (os vínculos são por id). CNPJ com "Buscar CNPJ" (preenche só campos vazios e avisa
 * se o CNPJ já existe), endereço estruturado com busca de CEP e "✧ Enriquecer com IA". Segmento e Porte vêm das listas da
 * Governança de ajustes; os campos padrões seguem a configuração de "Campos de dados" (visível / obrigatório).
 * Painel com largura "metade" (metade da tela, mínimo 640px).
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
import { Field, NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { cnpjValido } from "@/lib/validacao";
import { useAuth } from "@/lib/auth";
import { ORIGENS_EMPRESA, PAPEIS, type ConsultaCnpj, type EmpresaDetalhe, type EmpresaEntrada, type Papel, type ValoresCampos } from "@/lib/tipos-nucleo";
import { cn } from "@/lib/utils";

import { CampoCnpj, erroDeDocumento, erroDocumentoLocal, preencherVazios } from "./campo-cnpj";
import { useCamposPadroes } from "./campos-padroes";
import { CamposPersonalizados } from "./campos-personalizados";
import { SelectLista } from "./listas";
import { AnexosEmpresa, DadosReceita, QuadroSocietario, aplicarCnpj } from "./empresa-extras";
import { dadosParaIA, mesclarSugestoes } from "./consultas";
import { BlocoEndereco, enderecoDe, type ValorEndereco } from "./endereco";
import { EnriquecerIA } from "./enriquecer-ia";
import { RodapeFormulario, SeletorResponsavel, alterados, paraEnvio, txt, useInvalidarCadastros } from "./comum";
import { DrawerPessoa } from "./drawer-pessoa";

interface FormEmpresa extends ValorEndereco {
  nome: string;
  documento: string;
  nome_fantasia: string;
  segmento: string;
  porte: string;
  site: string;
  telefone: string;
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
    telefone: txt(e?.telefone),
    ...enderecoDe(e),
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

const ROTULOS: Record<string, string> = {
  nome: "Nome / razão social",
  documento: "CNPJ / CPF",
  nome_fantasia: "Nome fantasia",
  segmento: "Segmento",
  porte: "Porte",
  site: "Site",
  telefone: "Telefone",
  cep: "CEP",
  logradouro: "Logradouro",
  numero: "Número",
  complemento: "Complemento",
  bairro: "Bairro",
  cidade: "Cidade",
  uf: "UF",
  origem: "Origem",
  observacoes: "Observações",
};

/** Campos do formulário que o CNPJ pode preencher (só se estiverem vazios). */
function mapaCnpj(r: ConsultaCnpj): Partial<Record<keyof FormEmpresa, [string, string | null | undefined]>> {
  const m: Partial<Record<keyof FormEmpresa, [string, string | null | undefined]>> = {};
  const campos = ["nome", "nome_fantasia", "segmento", "porte", "telefone", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf"] as const;
  for (const k of campos) m[k] = [ROTULOS[k], r[k]];
  return m;
}

function Formulario({
  inicial,
  empresa,
  formId,
  onSalvar,
  onAbrirExistente,
  desabilitado,
  erroDocumento,
  onLimparErroDocumento,
}: {
  inicial: FormEmpresa;
  empresa?: EmpresaDetalhe;
  formId: string;
  onSalvar: (dados: EmpresaEntrada) => void;
  onAbrirExistente: (id: number) => void;
  desabilitado?: boolean;
  /** erro do salvar sobre o documento (inválido ou duplicado), mostrado no próprio campo */
  erroDocumento?: string | null;
  onLimparErroDocumento?: () => void;
}) {
  const [f, setF] = useState(inicial);
  const [erroDocLocal, setErroDocLocal] = useState<string | null>(null);
  const set = <K extends keyof FormEmpresa>(k: K, v: FormEmpresa[K]) => setF((x) => ({ ...x, [k]: v }));
  const cp = useCamposPadroes("empresa");
  const campo = (k: "nome" | "nome_fantasia" | "site" | "telefone") => ({
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
        const local = erroDocumentoLocal(f.documento);
        setErroDocLocal(local);
        if (local) return;
        const falta = cp.faltando({ ...f }, ROTULOS);
        if (falta) {
          notificar.erro(`Preencha ${falta}.`);
          return;
        }
        const atual = paraEnvio(f) as EmpresaEntrada;
        onSalvar(empresa ? alterados<EmpresaEntrada>(paraEnvio(inicial) as EmpresaEntrada, atual) : atual);
      }}
    >
      <EnriquecerIA
        objeto="empresa"
        registroId={empresa?.id ?? null}
        dados={dadosParaIA(f)}
        rotulos={ROTULOS}
        disabled={desabilitado}
        onAplicar={(v) => setF((x) => mesclarSugestoes(x, v))}
      />
      <Field label="Nome / razão social" obrigatorio>
        <Input {...campo("nome")} required autoFocus={!empresa} />
      </Field>
      {cp.visivel("documento") && (
        <CampoCnpj
          obrigatorio={cp.obrigatorio("documento")}
          valor={f.documento}
          onChange={(v) => {
            set("documento", v);
            setErroDocLocal(null);
            onLimparErroDocumento?.();
          }}
          erroExterno={erroDocLocal ?? erroDocumento}
          disabled={desabilitado}
          automatico={!empresa}
          registroId={empresa?.id ?? null}
          onAbrirExistente={onAbrirExistente}
          onResultado={(r) => {
            const { form, preenchidos } = preencherVazios(f, mapaCnpj(r));
            setF(form);
            return preenchidos;
          }}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {cp.visivel("nome_fantasia") && (
          <Field label="Nome fantasia" obrigatorio={cp.obrigatorio("nome_fantasia")}>
            <Input {...campo("nome_fantasia")} />
          </Field>
        )}
        {cp.visivel("segmento") && (
          <Field label="Segmento" obrigatorio={cp.obrigatorio("segmento")}>
            <SelectLista tipo="segmento" valor={f.segmento} onChange={(v) => set("segmento", v)} disabled={desabilitado} />
          </Field>
        )}
        {cp.visivel("porte") && (
          <Field label="Porte" obrigatorio={cp.obrigatorio("porte")}>
            <SelectLista tipo="porte" valor={f.porte} onChange={(v) => set("porte", v)} disabled={desabilitado} />
          </Field>
        )}
        {cp.visivel("site") && (
          <Field label="Site" obrigatorio={cp.obrigatorio("site")}>
            <Input {...campo("site")} type="url" placeholder="https://" />
          </Field>
        )}
        {cp.visivel("telefone") && (
          <Field label="Telefone" obrigatorio={cp.obrigatorio("telefone")}>
            <Input {...campo("telefone")} />
          </Field>
        )}
        {cp.visivel("responsavel_id") && (
          <Field label="Responsável" obrigatorio={cp.obrigatorio("responsavel_id")}>
            <SeletorResponsavel valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} disabled={desabilitado} />
          </Field>
        )}
      </div>
      <BlocoEndereco
        valor={f}
        disabled={desabilitado}
        obrigatorio={cp.obrigatorio}
        onChange={(p) => setF((x) => ({ ...x, ...p }))}
        dica={
          empresa?.endereco && !f.logradouro
            ? `Endereço anterior (texto livre): ${empresa.endereco}`
            : "Contatos que usam o endereço da empresa recebem a mudança."
        }
      />
      <Field label="Papéis">
        <ChipsPapeis valor={f.papeis} onChange={(v) => set("papeis", v)} disabled={desabilitado} />
      </Field>
      {cp.visivel("origem") && (
        <Field label="Origem" dica="Canal de entrada do relacionamento" obrigatorio={cp.obrigatorio("origem")}>
          <NativeSelect value={f.origem} disabled={desabilitado} onChange={(e) => set("origem", e.target.value)}>
            <option value="">Selecionar</option>
            {f.origem && !(ORIGENS_EMPRESA as readonly string[]).includes(f.origem) && <option value={f.origem}>{f.origem}</option>}
            {ORIGENS_EMPRESA.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </NativeSelect>
        </Field>
      )}
      {cp.visivel("observacoes") && (
        <Field label="Observações" obrigatorio={cp.obrigatorio("observacoes")}>
          <Textarea value={f.observacoes} disabled={desabilitado} onChange={(e) => set("observacoes", e.target.value)} />
        </Field>
      )}
      <CamposPersonalizados objeto="empresa" valores={f.campos_custom} onChange={(v) => set("campos_custom", v)} somenteLeitura={desabilitado} />
    </form>
  );
}

export function DrawerEmpresa({
  aberto,
  onFechar: onFecharProp,
  empresaId: empresaIdProp,
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
  // "Abrir cadastro existente" (CNPJ já cadastrado): o drawer passa a mostrar aquela empresa
  const [trocadaPara, setTrocadaPara] = useState<number | null>(null);
  const [erroDoc, setErroDoc] = useState<string | null>(null);
  const empresaId = trocadaPara ?? empresaIdProp;
  const onFechar = () => {
    setTrocadaPara(null);
    setErroDoc(null);
    onFecharProp();
  };
  const formId = `f-empresa-${empresaId ?? "nova"}`;

  const detalhe = useQuery({
    queryKey: ["nucleo", "empresas", "detalhe", empresaId],
    queryFn: () => api.get<EmpresaDetalhe>(`/nucleo/empresas/${empresaId}`),
    enabled: aberto && empresaId != null,
  });
  const e = detalhe.data;

  // remonta o formulário quando "Atualizar pela Receita" preenche campos no servidor
  const [versao, setVersao] = useState(0);
  const salvar = useMutation({
    mutationFn: async (dados: EmpresaEntrada) => {
      if (empresaId != null) return api.patch<EmpresaDetalhe>(`/nucleo/empresas/${empresaId}`, dados);
      const criada = await api.post<EmpresaDetalhe>("/nucleo/empresas", dados);
      // empresa nova com CNPJ: quadro societário, campos vazios e comprovante vêm da Receita logo depois de salvar
      if (cnpjValido(criada.documento)) {
        try {
          await aplicarCnpj(criada.id);
        } catch {
          notificar.info("Empresa salva. Os dados da Receita podem ser trazidos depois em “Atualizar pela Receita”.");
        }
      }
      return criada;
    },
    onMutate: () => setErroDoc(null),
    // o toast padrão continua; aqui só leva a mensagem ao campo CNPJ
    onError: (err) => setErroDoc(erroDeDocumento(err)),
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
        largura="metade"
        rotulo={empresaId == null ? undefined : "EMPRESA / CADASTRO ÚNICO"}
        titulo={empresaId == null ? "Cadastro de empresa" : (e?.nome ?? "Carregando…")}
        descricao={
          empresaId == null
            ? "O nome basta para começar."
            : e && `Empresa compartilhada · ${e.oportunidades ?? "—"} oportunidade(s) · ${e.titulos_receber ?? "—"} recebível(is)`
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
                {e.oportunidades ?? "—"} oportunidade(s)
                <br />
                {e.titulos_receber ?? "—"} recebível(is) · saldo aberto{" "}
                {e.saldo_receber == null ? "—" : <Dinheiro valor={e.saldo_receber} />}
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
            key={`${empresaId ?? "nova"}-${e?.criado_em ?? ""}-${nomeInicial ?? ""}-${versao}`}
            formId={formId}
            empresa={e}
            inicial={formDe(e, nomeInicial, papeisIniciais)}
            desabilitado={!podeEditar}
            erroDocumento={erroDoc}
            onLimparErroDocumento={() => setErroDoc(null)}
            onAbrirExistente={(id) => setTrocadaPara(id)}
            onSalvar={(d) => {
              if (empresaId != null && Object.keys(d).length === 0) {
                notificar("Nada mudou.");
                return;
              }
              salvar.mutate(d);
            }}
          />
        )}
        {e && (
          <div className="mt-8 flex flex-col gap-6 border-t border-line pt-6">
            <DadosReceita empresaId={e.id} />
            <QuadroSocietario empresaId={e.id} documento={e.documento} podeEditar={podeEditar} onAtualizado={() => setVersao((v) => v + 1)} />
            <AnexosEmpresa empresaId={e.id} podeEditar={podeEditar} />
          </div>
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
