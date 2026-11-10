"use client";

/**
 * TelaCampos — "Campos personalizados" (protótipo `fields`/`newField`/`fieldDeps`): catálogo (campo · tipo · objeto,
 * usos, Inspecionar dependências), drawer de criação/edição e drawer de dependências com arquivamento revisado
 * (sem dependência ativa arquiva direto; com dependências, só com confirmação explícita listando-as).
 * Também exporta `DrawerDependencias` ({ campoId, onFechar }).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { BarraFiltros } from "@/components/flic/barra-filtros";
import { ConfirmDialog } from "@/components/flic/confirm-dialog";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { Field, NativeSelect } from "@/components/flic/form";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  ROTULO_OBJETO,
  ROTULO_TIPO_CAMPO,
  type CampoCustom,
  type DependenciasCampo,
  type EtapaOpcao,
  type ObjetoCampo,
  type TipoCampo,
} from "@/lib/tipos-nucleo";

import { RodapeFormulario, useInvalidarCadastros } from "./comum";

const ROTULO_DEP = { dashboard: "Dashboard", automacao: "Automação", etapa: "Etapa", registros: "Cadastro" } as const;

interface FormCampo {
  nome: string;
  tipo: TipoCampo;
  objeto: ObjetoCampo;
  opcoes: string;
  obrigatorio: boolean;
  exigido_na_etapa_id: number | null;
}

function FormularioCampo({ c, formId, onEnviar, desabilitado }: { c?: CampoCustom; formId: string; onEnviar: (d: Record<string, unknown>) => void; desabilitado?: boolean }) {
  const [f, setF] = useState<FormCampo>({
    nome: c?.nome ?? "",
    tipo: c?.tipo ?? "texto",
    objeto: c?.objeto ?? "oportunidade",
    opcoes: (c?.opcoes ?? []).join("\n"),
    obrigatorio: c?.obrigatorio ?? false,
    exigido_na_etapa_id: c?.exigido_na_etapa_id ?? null,
  });
  const set = <K extends keyof FormCampo>(k: K, v: FormCampo[K]) => setF((x) => ({ ...x, [k]: v }));
  const etapas = useQuery({
    queryKey: ["nucleo", "campos", "etapas"],
    queryFn: () => api.get<EtapaOpcao[]>("/nucleo/campos/etapas"),
    enabled: f.objeto === "oportunidade",
  });
  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const opcoes = f.tipo === "lista" ? f.opcoes.split("\n").map((o) => o.trim()).filter(Boolean) : [];
        const base = { nome: f.nome, obrigatorio: f.obrigatorio, exigido_na_etapa_id: f.objeto === "oportunidade" ? f.exigido_na_etapa_id : null };
        onEnviar(c ? { ...base, ...(c.tipo === "lista" ? { opcoes } : {}) } : { ...base, tipo: f.tipo, objeto: f.objeto, opcoes });
      }}
    >
      <Field label="Nome" obrigatorio>
        <Input className="h-9" value={f.nome} required autoFocus={!c} disabled={desabilitado} onChange={(e) => set("nome", e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tipo">
          <NativeSelect value={f.tipo} disabled={!!c || desabilitado} onChange={(e) => set("tipo", e.target.value as TipoCampo)}>
            {(Object.keys(ROTULO_TIPO_CAMPO) as TipoCampo[]).map((t) => (
              <option key={t} value={t}>
                {ROTULO_TIPO_CAMPO[t]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Objeto">
          <NativeSelect value={f.objeto} disabled={!!c || desabilitado} onChange={(e) => set("objeto", e.target.value as ObjetoCampo)}>
            <option value="oportunidade">Oportunidade</option>
            <option value="empresa">Empresa</option>
            <option value="pessoa">Pessoa</option>
          </NativeSelect>
        </Field>
      </div>
      {c && <p className="text-xs text-muted">Tipo e objeto não mudam depois de criado: os valores já gravados dependem deles.</p>}
      {f.tipo === "lista" && (
        <Field label="Opções" obrigatorio dica="Uma por linha. Opção em uso não pode sair da lista.">
          <Textarea value={f.opcoes} disabled={desabilitado} rows={4} onChange={(e) => set("opcoes", e.target.value)} placeholder={"Baixo\nMédio\nAlto"} />
        </Field>
      )}
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={f.obrigatorio} disabled={desabilitado} onCheckedChange={(v) => set("obrigatorio", v === true)} />
        Obrigatório no cadastro
      </label>
      {f.objeto === "oportunidade" && (
        <Field label="Exigir na etapa" dica="Opcional. A oportunidade só avança para esta etapa com o campo preenchido.">
          <NativeSelect value={f.exigido_na_etapa_id ?? ""} disabled={desabilitado} onChange={(e) => set("exigido_na_etapa_id", e.target.value ? Number(e.target.value) : null)}>
            <option value="">Não exigir</option>
            {(etapas.data ?? []).map((et) => (
              <option key={et.id} value={et.id}>
                {et.funil_nome} · {et.nome}
              </option>
            ))}
          </NativeSelect>
        </Field>
      )}
      <p className="text-xs text-muted">O campo aparece no cadastro do objeto, nos filtros, nos dashboards e nas automações.</p>
    </form>
  );
}

function DrawerCampo({ aberto, onFechar, campo }: { aberto: boolean; onFechar: () => void; campo: CampoCustom | null }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const invalidar = useInvalidarCadastros();
  const formId = `f-campo-${campo?.id ?? "novo"}`;
  const salvar = useMutation({
    mutationFn: (d: Record<string, unknown>) => (campo ? api.patch<CampoCustom>(`/nucleo/campos/${campo.id}`, d) : api.post<CampoCustom>("/nucleo/campos", d)),
    onSuccess: () => {
      invalidar("campos");
      notificar.sucesso(campo ? "Campo atualizado" : "Campo adicionado ao catálogo");
      onFechar();
    },
  });
  return (
    <Drawer
      aberto={aberto}
      onFechar={onFechar}
      titulo={campo ? `Editar campo · ${campo.nome}` : "Novo campo"}
      rodape={podeEditar ? <RodapeFormulario formId={formId} rotulo={campo ? "Salvar campo" : "Criar campo"} salvando={salvar.isPending} onCancelar={onFechar} /> : undefined}
    >
      <FormularioCampo key={campo?.id ?? "novo"} c={campo ?? undefined} formId={formId} desabilitado={!podeEditar} onEnviar={(d) => salvar.mutate(d)} />
    </Drawer>
  );
}

export function DrawerDependencias({ campoId, onFechar }: { campoId: number | null; onFechar: () => void }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const invalidar = useInvalidarCadastros();
  const [confirmar, setConfirmar] = useState(false);
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "campos", "dependencias", campoId],
    queryFn: () => api.get<DependenciasCampo>(`/nucleo/campos/${campoId}/dependencias`),
    enabled: campoId != null,
  });
  const arquivar = useMutation({
    mutationFn: (confirmado: boolean) => api.post<CampoCustom>(`/nucleo/campos/${campoId}/arquivar`, { confirmar: confirmado }),
    onSuccess: () => {
      invalidar("campos");
      setConfirmar(false);
      notificar("Campo arquivado. Os valores gravados foram preservados.");
      onFechar();
    },
  });
  const restaurar = useMutation({
    mutationFn: () => api.post<CampoCustom>(`/nucleo/campos/${campoId}/restaurar`),
    onSuccess: () => {
      invalidar("campos");
      notificar("Campo restaurado ao catálogo");
      onFechar();
    },
  });
  const c = data?.campo;
  const ativas = (data?.dependencias ?? []).filter((d) => d.ativa);
  return (
    <>
      <Drawer
        aberto={campoId != null}
        onFechar={onFechar}
        titulo="Dependências do campo"
        descricao={c ? `${c.nome} · ${ROTULO_OBJETO[c.objeto]} · ${ROTULO_TIPO_CAMPO[c.tipo]}` : undefined}
        rodape={
          c &&
          podeEditar &&
          (c.arquivado ? (
            <Button onClick={() => restaurar.mutate()} disabled={restaurar.isPending}>
              Restaurar campo
            </Button>
          ) : (
            <Button variant={data?.pode_arquivar ? "default" : "outline"} onClick={() => (data?.pode_arquivar ? arquivar.mutate(false) : setConfirmar(true))} disabled={arquivar.isPending}>
              {data?.pode_arquivar ? "Arquivar campo" : "Arquivar mesmo assim…"}
            </Button>
          ))
        }
      >
        {isPending ? (
          <p className="text-sm text-muted">Verificando usos…</p>
        ) : (
          data && (
            <div className="flex flex-col gap-4">
              <div className="rounded-[10px] border border-electric/20 bg-electric/5 p-4">
                {data.dependencias.length === 0 ? (
                  <p className="text-sm">Nenhum uso encontrado em dashboards, automações ou etapas.</p>
                ) : (
                  <ul className="flex flex-col gap-2.5">
                    {data.dependencias.map((d, i) => (
                      <li key={`${d.tipo}-${d.id ?? i}`} className="text-sm">
                        <span className="font-semibold">{ROTULO_DEP[d.tipo]}:</span> {d.nome}{" "}
                        {d.ativa ? <Etiqueta tom="amber">Ativa</Etiqueta> : <Etiqueta>Informativa</Etiqueta>}
                        <p className="text-xs text-muted">{d.detalhe}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <p className="text-sm text-muted">{c?.arquivado ? "Campo arquivado: fora dos formulários; valores preservados." : data.mensagem}</p>
            </div>
          )
        )}
      </Drawer>
      <ConfirmDialog
        open={confirmar}
        onOpenChange={setConfirmar}
        titulo="Arquivar campo em uso?"
        descricao="Estes usos continuam apontando para o campo e podem parar de funcionar:"
        confirmar="Arquivar mesmo assim"
        destrutivo
        carregando={arquivar.isPending}
        onConfirm={() => arquivar.mutate(true)}
      >
        <ul className="list-disc pl-5 text-sm">
          {ativas.map((d, i) => (
            <li key={i}>
              {ROTULO_DEP[d.tipo]} “{d.nome}”
            </li>
          ))}
        </ul>
      </ConfirmDialog>
    </>
  );
}

const CHIPS_OBJETO = [
  { valor: "", rotulo: "Todos" },
  { valor: "oportunidade", rotulo: "Oportunidade" },
  { valor: "empresa", rotulo: "Empresa" },
  { valor: "pessoa", rotulo: "Pessoa" },
];

export function TelaCampos() {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const [objeto, setObjeto] = useState("");
  const [arquivados, setArquivados] = useState(false);
  const [q, setQ] = useState("");
  const [novo, setNovo] = useState(false);
  const [editar, setEditar] = useState<CampoCustom | null>(null);
  const [deps, setDeps] = useState<number | null>(null);
  useAtalhoNovo(() => podeEditar && setNovo(true));

  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "campos", "lista", objeto, arquivados],
    queryFn: () => api.get<CampoCustom[]>("/nucleo/campos", { objeto, arquivados }),
  });
  const linhas = (data ?? []).filter((c) => !q || c.nome.toLowerCase().includes(q.toLowerCase()));

  const colunas: Coluna<CampoCustom>[] = [
    {
      id: "campo",
      titulo: "Campo / tipo / objeto",
      celula: (c) => (
        <>
          <strong className="text-[13px]">{c.nome}</strong> {c.arquivado && <Etiqueta tom="amber">Arquivado</Etiqueta>} {c.obrigatorio && <Etiqueta tom="azul">Obrigatório</Etiqueta>}
          <p className="text-muted">
            {ROTULO_TIPO_CAMPO[c.tipo]} · {ROTULO_OBJETO[c.objeto]}
            {c.tipo === "lista" && c.opcoes.length > 0 && ` · ${c.opcoes.join(", ")}`}
            {c.etapa_nome && ` · exigido em ${c.etapa_nome}`}
          </p>
        </>
      ),
    },
    {
      id: "usos",
      titulo: "Usos",
      celula: (c) => (
        <>
          Cadastro · filtro · dashboard · automação
          <p className="text-muted">
            {c.registros_preenchidos} registro(s) preenchido(s)
            {c.dependencias_ativas > 0 && ` · ${c.dependencias_ativas} dependência(s) ativa(s)`}
          </p>
        </>
      ),
    },
    {
      id: "deps",
      titulo: "Dependências",
      alinhar: "direita",
      celula: (c) => (
        <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="outline" onClick={() => setDeps(c.id)}>
            Inspecionar
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        titulo="Campos personalizados"
        descricao="Flexibilidade sem duplicar cadastros nem criar novos sistemas."
        acao={podeEditar && <Button onClick={() => setNovo(true)}>+ Campo</Button>}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar campos" }}
        chips={{ opcoes: CHIPS_OBJETO, valor: objeto, onChange: setObjeto }}
        exportar={{
          nome: "campos-personalizados",
          linhas,
          colunas: [
            { titulo: "Campo", valor: (c) => c.nome },
            { titulo: "Tipo", valor: (c) => ROTULO_TIPO_CAMPO[c.tipo] },
            { titulo: "Objeto", valor: (c) => ROTULO_OBJETO[c.objeto] },
            { titulo: "Opções", valor: (c) => c.opcoes.join(" / ") },
            { titulo: "Obrigatório", valor: (c) => (c.obrigatorio ? "Sim" : "Não") },
            { titulo: "Registros preenchidos", valor: (c) => c.registros_preenchidos },
            { titulo: "Arquivado", valor: (c) => (c.arquivado ? "Sim" : "Não") },
          ],
        }}
      >
        <label className="flex items-center gap-2 text-xs text-muted">
          <Checkbox checked={arquivados} onCheckedChange={(v) => setArquivados(v === true)} />
          Mostrar arquivados
        </label>
      </BarraFiltros>
      <DataTable
        colunas={colunas}
        linhas={linhas}
        chave={(c) => c.id}
        onLinha={(c) => (podeEditar && !c.arquivado ? setEditar(c) : setDeps(c.id))}
        carregando={isPending}
        vazio={{ icone: SlidersHorizontal, titulo: "Nenhum campo neste filtro.", descricao: "Crie campos para empresa, pessoa ou oportunidade." }}
      />
      <Painel titulo="Regras recomendadas" className="mt-5">
        <p className="text-sm leading-relaxed text-muted">
          Exigir campos por etapa ou ação. Tipos estáveis e validação compartilhada. Antes de arquivar, verificar automações, modelos e dashboards dependentes.
        </p>
      </Painel>
      <DrawerCampo aberto={novo} onFechar={() => setNovo(false)} campo={null} />
      <DrawerCampo aberto={editar != null} onFechar={() => setEditar(null)} campo={editar} />
      <DrawerDependencias campoId={deps} onFechar={() => setDeps(null)} />
    </>
  );
}
