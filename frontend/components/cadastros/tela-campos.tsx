"use client";

/**
 * TelaCampos — "Campos de dados" (antigo "Campos personalizados"; protótipo `fields`/`newField`/`fieldDeps`).
 * Abas por objeto: Oportunidades · Empresas · Contatos · Produtos e serviços. Cada aba tem três blocos:
 *  1. Campos personalizados — ordem (arrastar ou ↑/↓), nome, tipo, obrigatoriedade, preferência "visível", criado em,
 *     ações (Editar · Dependências). Drawer de criação/edição com "Exigir no funil → etapa" e "Exibir na etapa".
 *  2. Sugestão de campos — modelos prontos com "+ Adicionar campo" (cria o campo já configurado).
 *  3. Campos padrões — campos fixos do sistema, com obrigatoriedade e visibilidade no cadastro (lápis abre o ajuste;
 *     campos sempre obrigatórios ficam sem lápis).
 * Também exporta `DrawerDependencias` ({ campoId, onFechar }): dependências e arquivamento revisado.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, GripVertical, Lock, Pencil, SlidersHorizontal } from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data as fmtData } from "@/lib/format";
import {
  ABAS_OBJETO_CAMPO,
  ROTULO_OBJETO,
  ROTULO_TIPO_CAMPO,
  TIPOS_CAMPO_CRIACAO,
  type CampoCustom,
  type CampoPadrao,
  type CampoSugerido,
  type DependenciasCampo,
  type EtapaOpcao,
  type FunilOpcao,
  type ObjetoCampo,
  type TipoCampo,
} from "@/lib/tipos-nucleo";
import { cn } from "@/lib/utils";

import { useCamposPadroesLista } from "./campos-padroes";
import { RodapeFormulario, useInvalidarCadastros } from "./comum";

/** Tipos com lista de opções. */
const COM_OPCOES: TipoCampo[] = ["lista", "multipla"];

interface FunilEscolha {
  chave: string;
  nome: string;
  /** na ordem do funil */
  etapas: { id: number; nome: string }[];
}

/** Funis com etapas: GET /comercial/funis; sem acesso ao Comercial, agrupa GET /nucleo/campos/etapas pelo funil. */
function useFunisParaCampos(ligado: boolean) {
  return useQuery({
    queryKey: ["nucleo", "campos", "funis"],
    enabled: ligado,
    staleTime: 60_000,
    meta: { silencioso: true },
    queryFn: async (): Promise<FunilEscolha[]> => {
      try {
        const funis = await api.get<(FunilOpcao & { etapas: { id: number; nome: string; ordem?: number }[] })[]>("/comercial/funis");
        return funis.map((f) => ({
          chave: String(f.id),
          nome: f.nome,
          etapas: [...f.etapas].sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0)).map((e) => ({ id: e.id, nome: e.nome })),
        }));
      } catch {
        const etapas = await api.get<EtapaOpcao[]>("/nucleo/campos/etapas");
        const grupos = new Map<string, FunilEscolha>();
        for (const e of etapas) {
          const chave = e.funil_id != null ? String(e.funil_id) : `n:${e.funil_nome}`;
          const g = grupos.get(chave) ?? { chave, nome: e.funil_nome, etapas: [] };
          g.etapas.push({ id: e.id, nome: e.nome });
          grupos.set(chave, g);
        }
        return [...grupos.values()];
      }
    },
  });
}

const funilDaEtapa = (funis: FunilEscolha[], etapaId: number | null) =>
  etapaId == null ? undefined : funis.find((g) => g.etapas.some((e) => e.id === etapaId));
const posicao = (funis: FunilEscolha[], etapaId: number | null) => {
  const g = funilDaEtapa(funis, etapaId);
  return g ? g.etapas.findIndex((e) => e.id === etapaId) : -1;
};

const ROTULO_DEP = { dashboard: "Dashboard", automacao: "Automação", etapa: "Etapa", registros: "Cadastro" } as const;

interface FormCampo {
  nome: string;
  tipo: TipoCampo;
  objeto: ObjetoCampo;
  opcoes: string;
  obrigatorio: boolean;
  exigido_na_etapa_id: number | null;
  exibir_funil_id: number | null;
  exibir_etapa_id: number | null;
}

type CorpoCampo = {
  nome: string;
  obrigatorio: boolean;
  tipo?: TipoCampo;
  objeto?: ObjetoCampo;
  opcoes?: string[];
  exigido_na_etapa_id?: number | null;
  exibir_funil_id?: number | null;
  exibir_etapa_id?: number | null;
};

function FormularioCampo({
  c,
  objetoPadrao,
  formId,
  onEnviar,
  desabilitado,
}: {
  c?: CampoCustom;
  objetoPadrao: ObjetoCampo;
  formId: string;
  onEnviar: (d: CorpoCampo) => void;
  desabilitado?: boolean;
}) {
  const [f, setF] = useState<FormCampo>({
    nome: c?.nome ?? "",
    tipo: c?.tipo ?? "texto",
    objeto: c?.objeto ?? objetoPadrao,
    opcoes: (c?.opcoes ?? []).join("\n"),
    obrigatorio: c?.obrigatorio ?? false,
    exigido_na_etapa_id: c?.exigido_na_etapa_id ?? null,
    exibir_funil_id: c?.exibir_funil_id ?? null,
    exibir_etapa_id: c?.exibir_etapa_id ?? null,
  });
  const set = <K extends keyof FormCampo>(k: K, v: FormCampo[K]) => setF((x) => ({ ...x, [k]: v }));
  const oportunidade = f.objeto === "oportunidade";
  const funis = useFunisParaCampos(oportunidade);
  const lista = funis.data ?? [];
  // funil escolhido; null = deduz do campo salvo (funil que contém a etapa exigida)
  const [funilEscolhido, setFunilEscolhido] = useState<string | null>(null);
  const funilAtual = funilEscolhido ?? funilDaEtapa(lista, f.exigido_na_etapa_id)?.chave ?? "";
  const etapasDoFunil = lista.find((g) => g.chave === funilAtual)?.etapas ?? [];
  const funilExibir = f.exibir_funil_id != null ? String(f.exibir_funil_id) : "";
  const etapasExibir = lista.find((g) => g.chave === funilExibir)?.etapas ?? [];
  // campo antigo pode ser sim/não: aparece só para exibir o tipo gravado
  const tipos = c && !TIPOS_CAMPO_CRIACAO.includes(c.tipo) ? [...TIPOS_CAMPO_CRIACAO, c.tipo] : TIPOS_CAMPO_CRIACAO;

  function conflito(): string | null {
    if (!oportunidade || f.exibir_funil_id == null || f.exigido_na_etapa_id == null) return null;
    const exigidoEm = funilDaEtapa(lista, f.exigido_na_etapa_id);
    if (exigidoEm && exigidoEm.chave !== String(f.exibir_funil_id)) return "O campo é exigido numa etapa de outro funil, onde ele não aparece.";
    if (f.exibir_etapa_id != null && posicao(lista, f.exigido_na_etapa_id) < posicao(lista, f.exibir_etapa_id))
      return "O campo é exigido numa etapa anterior à etapa em que ele passa a aparecer.";
    return null;
  }

  return (
    <form
      id={formId}
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const erro = conflito();
        if (erro) {
          notificar.erro(erro);
          return;
        }
        const opcoes = COM_OPCOES.includes(f.tipo) ? f.opcoes.split("\n").map((o) => o.trim()).filter(Boolean) : [];
        const base: CorpoCampo = { nome: f.nome, obrigatorio: f.obrigatorio, exigido_na_etapa_id: oportunidade ? f.exigido_na_etapa_id : null };
        // "Exibir na etapa" só vai quando mudou (servidor anterior ao campo novo segue aceitando o resto)
        const exibirMudou = f.exibir_funil_id !== (c?.exibir_funil_id ?? null) || f.exibir_etapa_id !== (c?.exibir_etapa_id ?? null);
        const exibir = oportunidade && exibirMudou ? { exibir_funil_id: f.exibir_funil_id, exibir_etapa_id: f.exibir_etapa_id } : {};
        onEnviar(
          c
            ? { ...base, ...exibir, ...(COM_OPCOES.includes(c.tipo) ? { opcoes } : {}) }
            : { ...base, ...exibir, tipo: f.tipo, objeto: f.objeto, opcoes },
        );
      }}
    >
      <Field label="Nome" obrigatorio>
        <Input className="h-9" value={f.nome} required autoFocus={!c} disabled={desabilitado} onChange={(e) => set("nome", e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tipo">
          <NativeSelect value={f.tipo} disabled={!!c || desabilitado} onChange={(e) => set("tipo", e.target.value as TipoCampo)}>
            {tipos.map((t) => (
              <option key={t} value={t}>
                {ROTULO_TIPO_CAMPO[t]}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Objeto">
          <NativeSelect value={f.objeto} disabled={!!c || desabilitado} onChange={(e) => set("objeto", e.target.value as ObjetoCampo)}>
            {ABAS_OBJETO_CAMPO.map((o) => (
              <option key={o.valor} value={o.valor}>
                {ROTULO_OBJETO[o.valor]}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      {c && <p className="text-xs text-muted">Tipo e objeto não mudam depois de criado: os valores já gravados dependem deles.</p>}
      {f.tipo === "link" && <p className="text-xs text-muted">Aceita endereço completo, começando com http:// ou https://.</p>}
      {COM_OPCOES.includes(f.tipo) && (
        <Field
          label="Opções"
          obrigatorio
          dica={f.tipo === "multipla" ? "Uma por linha; o registro pode marcar várias. Opção em uso não pode sair da lista." : "Uma por linha. Opção em uso não pode sair da lista."}
        >
          <Textarea value={f.opcoes} disabled={desabilitado} rows={4} onChange={(e) => set("opcoes", e.target.value)} placeholder={"Baixo\nMédio\nAlto"} />
        </Field>
      )}
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={f.obrigatorio} disabled={desabilitado} onCheckedChange={(v) => set("obrigatorio", v === true)} />
        Obrigatório no cadastro
      </label>
      {oportunidade && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Exigir no funil" dica="Opcional. A oportunidade só avança para a etapa com o campo preenchido.">
              <NativeSelect
                value={funilAtual}
                disabled={desabilitado}
                onChange={(e) => {
                  setFunilEscolhido(e.target.value);
                  set("exigido_na_etapa_id", null);
                }}
              >
                <option value="">Não exigir</option>
                {lista.map((g) => (
                  <option key={g.chave} value={g.chave}>
                    {g.nome}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            {funilAtual && (
              <Field label="Escolher na etapa" obrigatorio>
                <NativeSelect
                  value={f.exigido_na_etapa_id ?? ""}
                  disabled={desabilitado}
                  required
                  onChange={(e) => set("exigido_na_etapa_id", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Selecionar</option>
                  {etapasDoFunil.map((et) => (
                    <option key={et.id} value={et.id}>
                      {et.nome}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Exibir no funil" dica="Opcional. Fora deste funil o campo não aparece.">
              <NativeSelect
                value={funilExibir}
                disabled={desabilitado}
                onChange={(e) => setF((x) => ({ ...x, exibir_funil_id: e.target.value && !e.target.value.startsWith("n:") ? Number(e.target.value) : null, exibir_etapa_id: null }))}
              >
                <option value="">Sempre exibir</option>
                {lista
                  .filter((g) => !g.chave.startsWith("n:"))
                  .map((g) => (
                    <option key={g.chave} value={g.chave}>
                      {g.nome}
                    </option>
                  ))}
              </NativeSelect>
            </Field>
            {funilExibir && (
              <Field label="Exibir a partir da etapa" dica="Aparece desta etapa em diante.">
                <NativeSelect value={f.exibir_etapa_id ?? ""} disabled={desabilitado} onChange={(e) => set("exibir_etapa_id", e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Qualquer etapa</option>
                  {etapasExibir.map((et) => (
                    <option key={et.id} value={et.id}>
                      {et.nome}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
            )}
          </div>
        </>
      )}
      {funis.isError && oportunidade && <p className="text-xs text-muted">Não foi possível carregar os funis agora.</p>}
      <p className="text-xs text-muted">O campo aparece no cadastro do objeto, nos filtros, nos dashboards e nas automações.</p>
    </form>
  );
}

function DrawerCampo({ aberto, onFechar, campo, objeto }: { aberto: boolean; onFechar: () => void; campo: CampoCustom | null; objeto: ObjetoCampo }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const invalidar = useInvalidarCadastros();
  const formId = `f-campo-${campo?.id ?? "novo"}`;
  const salvar = useMutation({
    mutationFn: (d: CorpoCampo) => (campo ? api.patch<CampoCustom>(`/nucleo/campos/${campo.id}`, d) : api.post<CampoCustom>("/nucleo/campos", d)),
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
      <FormularioCampo
        key={`${campo?.id ?? "novo"}-${objeto}`}
        c={campo ?? undefined}
        objetoPadrao={objeto}
        formId={formId}
        desabilitado={!podeEditar}
        onEnviar={(d) => salvar.mutate(d)}
      />
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

// ================================================================================================= sugestões
/** Catálogo local usado só enquanto o servidor não publica GET /nucleo/campos/sugestoes. */
const SUGESTOES_LOCAIS: Record<ObjetoCampo, CampoSugerido[]> = {
  pessoa: [
    { chave: "data_de_nascimento", nome: "Data de nascimento", tipo: "data", opcoes: [], descricao: "Para lembrar aniversários e segmentar." },
    { chave: "linkedin", nome: "LinkedIn", tipo: "link", opcoes: [], descricao: "Perfil profissional do contato." },
    { chave: "cpf", nome: "CPF", tipo: "texto", opcoes: [], descricao: "Documento do contato (quando a base legal permitir)." },
    { chave: "departamento", nome: "Departamento", tipo: "texto", opcoes: [], descricao: "Área do contato na empresa." },
  ],
  empresa: [
    { chave: "inscricao_estadual", nome: "Inscrição estadual", tipo: "texto", opcoes: [], descricao: "Para emissão de nota fiscal." },
    { chave: "no_de_funcionarios", nome: "Nº de funcionários", tipo: "numero", opcoes: [], descricao: "Tamanho da operação do cliente." },
    { chave: "faturamento_anual", nome: "Faturamento anual", tipo: "moeda", opcoes: [], descricao: "Faturamento estimado no ano." },
    { chave: "linkedin", nome: "LinkedIn", tipo: "link", opcoes: [], descricao: "Página da empresa no LinkedIn." },
  ],
  oportunidade: [
    { chave: "concorrente", nome: "Concorrente", tipo: "texto", opcoes: [], descricao: "Quem disputa a venda com você." },
    {
      chave: "fonte_do_lead",
      nome: "Fonte do lead",
      tipo: "lista",
      opcoes: ["Indicação", "Site", "Evento", "Prospecção ativa", "Redes sociais"],
      descricao: "De onde veio a oportunidade.",
    },
    { chave: "data_prevista_de_decisao", nome: "Data prevista de decisão", tipo: "data", opcoes: [], descricao: "Quando o cliente decide." },
  ],
  produto: [
    { chave: "sku_externo", nome: "SKU externo", tipo: "texto", opcoes: [], descricao: "Código do item em outro sistema (ERP, loja)." },
    { chave: "ncm", nome: "NCM", tipo: "texto", opcoes: [], descricao: "Nomenclatura Comum do Mercosul (produtos com nota fiscal)." },
    { chave: "garantia", nome: "Garantia", tipo: "texto", opcoes: [], descricao: "Prazo e condições de garantia." },
  ],
};

function BlocoSugestoes({ objeto, existentes }: { objeto: ObjetoCampo; existentes: CampoCustom[] }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const invalidar = useInvalidarCadastros();
  const sugestoes = useQuery({
    queryKey: ["nucleo", "campos", "sugestoes", objeto],
    queryFn: () => api.get<CampoSugerido[]>("/nucleo/campos/sugestoes", { objeto }),
    retry: false,
    meta: { silencioso: true },
  });
  const adicionar = useMutation({
    mutationFn: (s: CampoSugerido) => api.post<CampoCustom>("/nucleo/campos", { nome: s.nome, tipo: s.tipo, objeto, opcoes: s.opcoes, obrigatorio: false }),
    onSuccess: (c) => {
      invalidar("campos");
      notificar.sucesso(`“${c.nome}” adicionado aos campos personalizados`);
    },
  });
  // sem a rota: catálogo local, escondendo o que já virou campo (mesmo slug ou mesmo nome)
  const ja = new Set(existentes.flatMap((c) => [c.slug, c.nome.toLowerCase()]));
  const lista = sugestoes.isError ? SUGESTOES_LOCAIS[objeto].filter((s) => !ja.has(s.chave) && !ja.has(s.nome.toLowerCase())) : (sugestoes.data ?? []);
  return (
    <Painel titulo="Sugestão de campos">
      {sugestoes.isPending ? (
        <p className="text-sm text-muted">Carregando sugestões…</p>
      ) : lista.length === 0 ? (
        <p className="text-sm text-muted">Todas as sugestões deste objeto já viraram campo.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {lista.map((s) => (
            <div key={s.chave} className="flex flex-col gap-2 rounded-[10px] border border-line p-4">
              <div className="flex items-start justify-between gap-2">
                <strong className="text-sm">{s.nome}</strong>
                <Etiqueta>{ROTULO_TIPO_CAMPO[s.tipo] ?? s.tipo}</Etiqueta>
              </div>
              {s.descricao && <p className="text-xs text-muted">{s.descricao}</p>}
              {s.opcoes.length > 0 && <p className="text-xs text-muted">Opções: {s.opcoes.join(", ")}</p>}
              {podeEditar && (
                <Button size="sm" variant="outline" className="mt-auto self-start" disabled={adicionar.isPending} onClick={() => adicionar.mutate(s)}>
                  + Adicionar campo
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </Painel>
  );
}

// ================================================================================================= campos padrões
function DrawerCampoPadrao({ objeto, campo, onFechar }: { objeto: ObjetoCampo; campo: CampoPadrao | null; onFechar: () => void }) {
  const qc = useQueryClient();
  const [visivel, setVisivel] = useState(campo?.visivel ?? true);
  const [obrigatorio, setObrigatorio] = useState(campo?.obrigatorio ?? false);
  const salvar = useMutation({
    mutationFn: () => api.patch<CampoPadrao>(`/nucleo/campos/padroes/${objeto}/${campo?.campo}`, { visivel, obrigatorio }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nucleo", "campos", "padroes", objeto] });
      notificar.sucesso("Campo padrão atualizado");
      onFechar();
    },
  });
  return (
    <Drawer
      aberto={campo != null}
      onFechar={onFechar}
      rotulo="CAMPO PADRÃO"
      titulo={campo?.nome}
      descricao={campo ? `${ROTULO_OBJETO[objeto]} · ${campo.tipo}` : undefined}
      rodape={
        <>
          <Button onClick={() => salvar.mutate()} disabled={salvar.isPending}>
            {salvar.isPending ? "Salvando…" : "Salvar campo"}
          </Button>
          <Button variant="outline" onClick={onFechar}>
            Cancelar
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <label className="flex items-center justify-between gap-4 rounded-[10px] border border-line px-3.5 py-3">
          <span>
            <span className="block text-sm font-medium">Visível no cadastro</span>
            <span className="block text-xs text-muted">Desligado, o campo some do formulário. Os valores gravados continuam.</span>
          </span>
          <Switch
            checked={visivel}
            onCheckedChange={(v) => {
              setVisivel(v);
              if (!v) setObrigatorio(false);
            }}
          />
        </label>
        <label className="flex items-center justify-between gap-4 rounded-[10px] border border-line px-3.5 py-3">
          <span>
            <span className="block text-sm font-medium">Obrigatório</span>
            <span className="block text-xs text-muted">
              {visivel ? "Exigido ao criar; ao editar, não pode ser apagado." : "Só campo visível pode ser obrigatório."}
            </span>
          </span>
          <Switch checked={obrigatorio} disabled={!visivel} onCheckedChange={setObrigatorio} />
        </label>
      </div>
    </Drawer>
  );
}

function BlocoCamposPadroes({ objeto }: { objeto: ObjetoCampo }) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const { data, isPending, isError } = useCamposPadroesLista(objeto);
  const [editar, setEditar] = useState<CampoPadrao | null>(null);
  const colunas: Coluna<CampoPadrao>[] = [
    { id: "nome", titulo: "Nome", celula: (c) => <strong className="text-[13px]">{c.nome}</strong> },
    {
      id: "tipo",
      titulo: "Tipo",
      celula: (c) => (
        <>
          <Etiqueta tom="azul">Campo padrão</Etiqueta>
          <p className="mt-1 text-muted">{c.tipo}</p>
        </>
      ),
    },
    { id: "obr", titulo: "Obrigatoriedade", celula: (c) => (c.obrigatorio ? "Obrigatório" : "Opcional") },
    { id: "vis", titulo: "Visível no cadastro", celula: (c) => (c.visivel ? "Sim" : <span className="text-muted">Não</span>) },
    {
      id: "acoes",
      titulo: "Ações",
      alinhar: "direita",
      celula: (c) =>
        c.fixo ? (
          <span className="inline-flex items-center gap-1 text-xs text-muted" title="Sempre obrigatório e visível">
            <Lock className="size-3.5" />
            Fixo
          </span>
        ) : podeEditar ? (
          <Button size="sm" variant="outline" aria-label={`Ajustar ${c.nome}`} onClick={() => setEditar(c)}>
            <Pencil className="size-3.5" />
          </Button>
        ) : null,
    },
  ];
  return (
    <Painel titulo="Campos padrões">
      {isError ? (
        <p className="text-sm text-muted">A configuração dos campos padrões ainda não está disponível neste servidor.</p>
      ) : (
        <DataTable semCartao colunas={colunas} linhas={data} chave={(c) => c.campo} carregando={isPending} vazio={{ titulo: "Nenhum campo padrão neste objeto." }} />
      )}
      <DrawerCampoPadrao key={editar?.campo ?? "nenhum"} objeto={objeto} campo={editar} onFechar={() => setEditar(null)} />
    </Painel>
  );
}

// ================================================================================================= campos personalizados
function obrigatoriedade(c: CampoCustom) {
  const partes: string[] = [];
  if (c.obrigatorio) partes.push("Obrigatório");
  if (c.etapa_nome) partes.push(`Exigido em ${c.funil_nome ? `${c.funil_nome} › ` : ""}${c.etapa_nome}`);
  return partes.length ? partes.join(" · ") : "Opcional";
}

function BlocoPersonalizados({
  objeto,
  campos,
  carregando,
  arquivados,
  setArquivados,
  onEditar,
  onDeps,
}: {
  objeto: ObjetoCampo;
  campos: CampoCustom[];
  carregando: boolean;
  arquivados: boolean;
  setArquivados: (v: boolean) => void;
  onEditar: (c: CampoCustom) => void;
  onDeps: (id: number) => void;
}) {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const invalidar = useInvalidarCadastros();
  const [q, setQ] = useState("");
  const [arrastando, setArrastando] = useState<number | null>(null);
  // ordem otimista enquanto o servidor grava
  const [ordemLocal, setOrdemLocal] = useState<number[] | null>(null);

  const ativos = campos.filter((c) => !c.arquivado);
  const porId = new Map(ativos.map((c) => [c.id, c]));
  const ordenados = ordemLocal ? ordemLocal.map((id) => porId.get(id)).filter((c): c is CampoCustom => !!c) : ativos;
  const todos = [...ordenados, ...campos.filter((c) => c.arquivado)];
  const linhas = todos.filter((c) => !q || c.nome.toLowerCase().includes(q.toLowerCase()));
  const podeOrdenar = podeEditar && !q;

  const reordenar = useMutation({
    mutationFn: async (ids: number[]) => {
      const atual = new Map(ativos.map((c) => [c.id, c.ordem]));
      await Promise.all(ids.map((id, i) => (atual.get(id) === i + 1 ? null : api.patch<CampoCustom>(`/nucleo/campos/${id}`, { ordem: i + 1 }))));
    },
    onSuccess: () => notificar("Ordem dos campos atualizada"),
    onSettled: () => {
      invalidar("campos");
      setOrdemLocal(null);
    },
  });
  const visivel = useMutation({
    mutationFn: ({ id, valor }: { id: number; valor: boolean }) => api.patch<CampoCustom>(`/nucleo/campos/${id}`, { visivel: valor }),
    onSuccess: (c) => {
      invalidar("campos");
      notificar(c.visivel === false ? "Campo oculto nos cadastros" : "Campo visível nos cadastros");
    },
  });

  function mover(id: number, para: number) {
    const ids = ordenados.map((c) => c.id);
    const de = ids.indexOf(id);
    if (de < 0 || para < 0 || para >= ids.length || de === para) return;
    ids.splice(para, 0, ...ids.splice(de, 1));
    setOrdemLocal(ids);
    reordenar.mutate(ids);
  }

  // alvo de soltar em qualquer célula da linha
  const alvo = (c: CampoCustom, node: React.ReactNode) =>
    podeOrdenar && !c.arquivado ? (
      <div
        onDragOver={(e) => arrastando != null && e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (arrastando != null) mover(arrastando, ordenados.findIndex((x) => x.id === c.id));
          setArrastando(null);
        }}
      >
        {node}
      </div>
    ) : (
      node
    );

  const colunas: Coluna<CampoCustom>[] = [
    {
      id: "ordem",
      titulo: "Ordem",
      className: "w-24",
      celula: (c) => {
        if (c.arquivado) return <span className="text-muted">—</span>;
        const i = ordenados.findIndex((x) => x.id === c.id);
        return alvo(
          c,
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            {podeOrdenar ? (
              <>
                <span
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "move";
                    setArrastando(c.id);
                  }}
                  onDragEnd={() => setArrastando(null)}
                  className={cn("cursor-grab rounded p-1 text-muted hover:text-ink", arrastando === c.id && "opacity-50")}
                  aria-label={`Arrastar ${c.nome}`}
                  title="Arrastar para reordenar"
                >
                  <GripVertical className="size-4" />
                </span>
                <button type="button" className="rounded p-1 text-muted hover:text-ink disabled:opacity-30" disabled={i === 0} aria-label="Subir" onClick={() => mover(c.id, i - 1)}>
                  <ArrowUp className="size-3.5" />
                </button>
                <button
                  type="button"
                  className="rounded p-1 text-muted hover:text-ink disabled:opacity-30"
                  disabled={i === ordenados.length - 1}
                  aria-label="Descer"
                  onClick={() => mover(c.id, i + 1)}
                >
                  <ArrowDown className="size-3.5" />
                </button>
              </>
            ) : (
              <span className="num text-muted">{i + 1}</span>
            )}
          </div>,
        );
      },
    },
    {
      id: "nome",
      titulo: "Nome",
      celula: (c) =>
        alvo(
          c,
          <>
            <strong className="text-[13px]">{c.nome}</strong> {c.arquivado && <Etiqueta tom="amber">Arquivado</Etiqueta>}
            {(COM_OPCOES.includes(c.tipo) && c.opcoes.length > 0) || c.exibir_funil_id != null ? (
              <p className="text-muted">
                {[
                  COM_OPCOES.includes(c.tipo) && c.opcoes.length > 0 ? c.opcoes.join(", ") : null,
                  c.exibir_funil_id != null
                    ? `Exibido em ${c.exibir_funil_nome ?? "um funil"}${c.exibir_etapa_nome ? ` a partir de ${c.exibir_etapa_nome}` : ""}`
                    : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            ) : null}
          </>,
        ),
    },
    { id: "tipo", titulo: "Tipo", celula: (c) => alvo(c, ROTULO_TIPO_CAMPO[c.tipo] ?? c.tipo) },
    { id: "obr", titulo: "Obrigatoriedade", celula: (c) => alvo(c, obrigatoriedade(c)) },
    {
      id: "pref",
      titulo: "Preferências",
      celula: (c) =>
        alvo(
          c,
          c.visivel === undefined ? (
            <span className="text-muted">Visível</span>
          ) : (
            <label className="flex items-center gap-2 text-xs" onClick={(e) => e.stopPropagation()}>
              <Switch checked={c.visivel} disabled={!podeEditar || c.arquivado || visivel.isPending} onCheckedChange={(v) => visivel.mutate({ id: c.id, valor: v })} />
              Visível
            </label>
          ),
        ),
    },
    { id: "criado", titulo: "Criado em", celula: (c) => alvo(c, <span className="num">{c.criado_em ? fmtData(c.criado_em) : "—"}</span>) },
    {
      id: "acoes",
      titulo: "Ações",
      alinhar: "direita",
      celula: (c) => (
        <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          {podeEditar && !c.arquivado && (
            <Button size="sm" variant="outline" aria-label={`Editar ${c.nome}`} onClick={() => onEditar(c)}>
              <Pencil className="size-3.5" />
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => onDeps(c.id)}>
            Dependências
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Painel titulo="Campos personalizados">
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar campos" }}
        exportar={{
          nome: `campos-${objeto}`,
          linhas,
          colunas: [
            { titulo: "Ordem", valor: (c) => (c.arquivado ? "" : ordenados.findIndex((x) => x.id === c.id) + 1) },
            { titulo: "Campo", valor: (c) => c.nome },
            { titulo: "Tipo", valor: (c) => ROTULO_TIPO_CAMPO[c.tipo] },
            { titulo: "Objeto", valor: (c) => ROTULO_OBJETO[c.objeto] },
            { titulo: "Opções", valor: (c) => c.opcoes.join(" / ") },
            { titulo: "Obrigatório", valor: (c) => (c.obrigatorio ? "Sim" : "Não") },
            { titulo: "Exigido no funil", valor: (c) => c.funil_nome ?? "" },
            { titulo: "Exigido na etapa", valor: (c) => c.etapa_nome ?? "" },
            { titulo: "Exibir no funil", valor: (c) => c.exibir_funil_nome ?? "" },
            { titulo: "Exibir a partir da etapa", valor: (c) => c.exibir_etapa_nome ?? "" },
            { titulo: "Visível", valor: (c) => (c.visivel === false ? "Não" : "Sim") },
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
        semCartao
        colunas={colunas}
        linhas={linhas}
        chave={(c) => c.id}
        onLinha={(c) => (podeEditar && !c.arquivado ? onEditar(c) : onDeps(c.id))}
        carregando={carregando}
        vazio={{ icone: SlidersHorizontal, titulo: "Nenhum campo personalizado neste objeto.", descricao: "Crie um campo ou adicione uma das sugestões abaixo." }}
      />
      {podeOrdenar && ordenados.length > 1 && <p className="mt-3 text-xs text-muted">Arraste pela alça (ou use as setas) para mudar a ordem nos formulários.</p>}
    </Painel>
  );
}

export function TelaCampos() {
  const { pode } = useAuth();
  const podeEditar = pode("nucleo.campos.editar");
  const [objeto, setObjeto] = useState<ObjetoCampo>("oportunidade");
  const [arquivados, setArquivados] = useState(false);
  const [novo, setNovo] = useState(false);
  const [editar, setEditar] = useState<CampoCustom | null>(null);
  const [deps, setDeps] = useState<number | null>(null);
  useAtalhoNovo(() => podeEditar && setNovo(true));

  // sempre com arquivados: as sugestões escondem o que já virou campo, mesmo arquivado
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "campos", "lista", objeto, true],
    queryFn: () => api.get<CampoCustom[]>("/nucleo/campos", { objeto, arquivados: true }),
  });
  const todos = [...(data ?? [])].sort((a, b) => a.ordem - b.ordem || a.id - b.id);
  const campos = arquivados ? todos : todos.filter((c) => !c.arquivado);

  return (
    <>
      <PageHeader
        titulo="Campos de dados"
        descricao="Flexibilidade sem duplicar cadastros nem criar novos sistemas."
        acao={podeEditar && <Button onClick={() => setNovo(true)}>+ Campo</Button>}
      />
      <div role="tablist" aria-label="Objeto" className="mb-5 flex flex-wrap gap-2">
        {ABAS_OBJETO_CAMPO.map((a) => (
          <button
            key={a.valor}
            role="tab"
            type="button"
            aria-selected={objeto === a.valor}
            onClick={() => setObjeto(a.valor)}
            className={cn(
              "rounded-[7px] border px-4 py-2 text-sm transition",
              objeto === a.valor ? "border-primary bg-primary font-semibold text-primary-foreground" : "border-line bg-surface hover:border-primary",
            )}
          >
            {a.rotulo}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        <BlocoPersonalizados
          key={objeto}
          objeto={objeto}
          campos={campos}
          carregando={isPending}
          arquivados={arquivados}
          setArquivados={setArquivados}
          onEditar={setEditar}
          onDeps={setDeps}
        />
        <BlocoSugestoes objeto={objeto} existentes={todos} />
        <BlocoCamposPadroes objeto={objeto} />
      </div>
      <DrawerCampo aberto={novo} onFechar={() => setNovo(false)} campo={null} objeto={objeto} />
      <DrawerCampo aberto={editar != null} onFechar={() => setEditar(null)} campo={editar} objeto={objeto} />
      <DrawerDependencias campoId={deps} onFechar={() => setDeps(null)} />
    </>
  );
}
