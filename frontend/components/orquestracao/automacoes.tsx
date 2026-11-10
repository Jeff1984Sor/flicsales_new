"use client";

/**
 * Núcleo › Automações (protótipo `automation` 2ª versão, `autoEditor`, `testAutomation`, `toggleAutomation`).
 * Área Comercial/Financeiro ("Motor compartilhado · configurações independentes"), abas Modelos / Minhas automações /
 * Histórico, editor no drawer, Testar (prévia sem executar) e Ativar/Pausar (envio exige canal conectado).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, History, Workflow } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { DataTable, type Coluna } from "@/components/flic/data-table";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { Etiqueta, type TomEtiqueta } from "@/components/flic/etiqueta";
import { NativeSelect } from "@/components/flic/form";
import { Fonte } from "@/components/flic/fonte";
import { PageHeader } from "@/components/flic/page-header";
import { Painel } from "@/components/flic/painel";
import { Passos } from "@/components/flic/passos";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dataHora } from "@/lib/format";
import type {
  AreaAutomacao,
  Automacao,
  AutomacaoIn,
  CatalogoAutomacoes,
  ExecucaoAutomacao,
  ModeloAutomacao,
  TesteAutomacao,
  UsuarioOpcao,
} from "@/lib/tipos-orquestracao";
import { cn } from "@/lib/utils";

type Aba = "Modelos" | "Minhas automações" | "Histórico";
const ABAS: Aba[] = ["Modelos", "Minhas automações", "Histórico"];
const AREAS: { id: AreaAutomacao; rotulo: string; permissao: string }[] = [
  { id: "comercial", rotulo: "Comercial", permissao: "comercial.atividades.ver" },
  { id: "financeiro", rotulo: "Financeiro", permissao: "financeiro.cobrancas.ver" },
];
const ESTADO: Record<Automacao["estado"], { rotulo: string; tom: TomEtiqueta }> = {
  rascunho: { rotulo: "Rascunho", tom: "amber" },
  ativa: { rotulo: "Ativa", tom: "green" },
  pausada: { rotulo: "Pausada", tom: "neutra" },
};
const RESULTADO: Record<string, { rotulo: string; tom: TomEtiqueta }> = {
  executada: { rotulo: "Executada", tom: "green" },
  notificado: { rotulo: "Responsável notificado", tom: "green" },
  pendente_conector: { rotulo: "Pendente de conector", tom: "amber" },
  falhou: { rotulo: "Falhou", tom: "amber" },
  simulada: { rotulo: "Teste sem execução", tom: "azul" },
  em_execucao: { rotulo: "Em execução", tom: "neutra" },
};

function vazio(area: AreaAutomacao, gatilho: string): AutomacaoIn {
  return {
    area,
    nome: "Nova automação",
    gatilho,
    funil_id: null,
    etapa_destino_id: null,
    campo: null,
    operador: null,
    valor_esperado: null,
    prazo_dias: area === "comercial" ? 2 : 3,
    acao: "criar_atividade",
    tipo_atividade: "tarefa",
    responsavel_regra: "responsavel_do_registro",
    destinatario: null,
    conteudo: "Preparar próxima ação para {{empresa.nome}}",
    revisar_condicoes: true,
  };
}

function doModelo(m: ModeloAutomacao): AutomacaoIn {
  return {
    area: m.area,
    nome: m.nome,
    gatilho: m.gatilho,
    funil_id: null,
    etapa_destino_id: m.etapa_destino_id,
    campo: m.campo,
    operador: m.operador,
    valor_esperado: m.valor_esperado,
    prazo_dias: m.prazo_dias,
    acao: m.acao,
    tipo_atividade: m.tipo_atividade,
    responsavel_regra: m.responsavel_regra,
    destinatario: m.destinatario,
    conteudo: m.conteudo,
    revisar_condicoes: true,
  };
}

function deAutomacao(a: Automacao): AutomacaoIn {
  const { area, nome, gatilho, funil_id, etapa_destino_id, campo, operador, valor_esperado, prazo_dias, acao, tipo_atividade } = a;
  return {
    area,
    nome,
    gatilho,
    funil_id,
    etapa_destino_id,
    campo,
    operador,
    valor_esperado,
    prazo_dias,
    acao,
    tipo_atividade,
    responsavel_regra: a.responsavel_regra,
    destinatario: a.destinatario,
    conteudo: a.conteudo,
    revisar_condicoes: a.revisar_condicoes,
  };
}

export function AutomacoesTela() {
  const { pode } = useAuth();
  const qc = useQueryClient();
  const params = useSearchParams();
  const areasVisiveis = AREAS.filter((a) => pode(a.permissao));
  const pedida = areasVisiveis.find((a) => a.id === params.get("area"))?.id;
  const [area, setArea] = useState<AreaAutomacao>(pedida ?? areasVisiveis[0]?.id ?? "comercial");
  const [aba, setAba] = useState<Aba>("Modelos");
  const [editando, setEditando] = useState<{ id: number | null; dados: AutomacaoIn } | null>(null);
  const [teste, setTeste] = useState<{ automacao: Automacao; resultado: TesteAutomacao } | null>(null);
  const podeEditar = pode("orquestracao.automacoes.editar");

  const catalogo = useQuery({
    queryKey: ["orquestracao", "automacoes", "catalogo"],
    queryFn: () => api.get<CatalogoAutomacoes>("/orquestracao/automacoes/catalogo"),
  });
  const modelos = useQuery({
    queryKey: ["orquestracao", "automacoes", "modelos", area],
    queryFn: () => api.get<ModeloAutomacao[]>("/orquestracao/automacoes/modelos", { area }),
  });
  const lista = useQuery({
    queryKey: ["orquestracao", "automacoes", "lista", area],
    queryFn: () => api.get<Automacao[]>("/orquestracao/automacoes", { area }),
  });
  const historico = useQuery({
    queryKey: ["orquestracao", "automacoes", "execucoes", area],
    queryFn: () => api.get<ExecucaoAutomacao[]>("/orquestracao/automacoes/execucoes", { area }),
    enabled: aba === "Histórico",
  });

  const recarregar = () => void qc.invalidateQueries({ queryKey: ["orquestracao", "automacoes"] });

  const alternar = useMutation({
    mutationFn: (a: Automacao) => api.post<Automacao>(`/orquestracao/automacoes/${a.id}/${a.estado === "ativa" ? "pausar" : "ativar"}`),
    onSuccess: (a) => {
      notificar(a.estado === "ativa" ? "Automação ativa: o motor avalia a cada 5 minutos, sem duplicar." : "Automação pausada.");
      recarregar();
    },
  });
  const testar = useMutation({
    mutationFn: (a: Automacao) => api.post<TesteAutomacao>(`/orquestracao/automacoes/${a.id}/testar`),
    onSuccess: (resultado, automacao) => {
      setTeste({ automacao, resultado });
      recarregar();
    },
  });

  const colunas: Coluna<Automacao>[] = [
    { id: "nome", titulo: "Nome", celula: (a) => <strong>{a.nome}</strong> },
    { id: "gatilho", titulo: "Gatilho", celula: (a) => a.gatilho_rotulo },
    {
      id: "acao",
      titulo: "Ação",
      celula: (a) => `${a.acao_rotulo}${a.acao === "criar_atividade" && a.tipo_atividade ? ` / ${rotuloTipo(catalogo.data, a.tipo_atividade)}` : ""}`,
    },
    { id: "estado", titulo: "Estado", celula: (a) => <Etiqueta tom={ESTADO[a.estado].tom}>{ESTADO[a.estado].rotulo}</Etiqueta> },
    {
      id: "controles",
      titulo: "Controles",
      celula: (a) =>
        podeEditar ? (
          <div className="flex flex-wrap gap-1.5" onClick={(e) => e.stopPropagation()}>
            <Button size="sm" variant="outline" disabled={testar.isPending} onClick={() => testar.mutate(a)}>
              Testar
            </Button>
            <Button size="sm" variant="outline" disabled={alternar.isPending} onClick={() => alternar.mutate(a)}>
              {a.estado === "ativa" ? "Pausar" : "Ativar"}
            </Button>
          </div>
        ) : (
          <span className="text-xs text-muted">Somente leitura</span>
        ),
    },
  ];

  const colunasHistorico: Coluna<ExecucaoAutomacao>[] = [
    { id: "quando", titulo: "Quando", celula: (e) => <span className="font-mono text-xs">{dataHora(e.quando)}</span> },
    { id: "automacao", titulo: "Automação", celula: (e) => <strong>{e.automacao_nome}</strong> },
    { id: "registro", titulo: "Registro", celula: (e) => e.registro ?? "—" },
    {
      id: "resultado",
      titulo: "Resultado",
      celula: (e) => {
        const r = RESULTADO[e.resultado ?? ""] ?? { rotulo: e.resultado ?? "—", tom: "neutra" as const };
        return <Etiqueta tom={r.tom}>{r.rotulo}</Etiqueta>;
      },
    },
    {
      id: "detalhe",
      titulo: "Detalhe",
      celula: (e) => (
        <p className="max-w-[420px] text-xs text-muted">
          {e.erro ?? e.detalhe ?? "—"}
          {e.tentativas > 1 ? ` · ${e.tentativas} tentativas` : ""}
        </p>
      ),
    },
  ];

  if (areasVisiveis.length === 0) {
    return (
      <>
        <PageHeader titulo="Automações" descricao="Ambientes separados por área. Gatilhos, permissões e modelos específicos." />
        <Painel>
          <p className="text-sm text-muted">Seu perfil não acessa as automações do Comercial nem do Financeiro.</p>
        </Painel>
      </>
    );
  }

  const gatilhoPadrao = catalogo.data?.gatilhos[area][0]?.id ?? "";
  const minhas = lista.data ?? [];

  return (
    <>
      <PageHeader
        titulo="Automações"
        descricao="Ambientes separados por área. Gatilhos, permissões e modelos específicos."
        acao={
          podeEditar ? (
            <Button onClick={() => setEditando({ id: null, dados: vazio(area, gatilhoPadrao) })} disabled={!catalogo.data}>
              + Automação
            </Button>
          ) : undefined
        }
      />

      <div className="mb-5 flex flex-wrap items-center gap-2.5">
        {areasVisiveis.map((a) => (
          <Button key={a.id} variant={a.id === area ? "default" : "outline"} onClick={() => setArea(a.id)}>
            {a.rotulo}
          </Button>
        ))}
        <span className="text-sm text-muted">Motor compartilhado · configurações independentes</span>
      </div>
      <div className="mb-[22px] flex flex-wrap gap-1.5 border-b border-line" role="tablist">
        {ABAS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={aba === t}
            onClick={() => setAba(t)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              aba === t ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {t}
            {t === "Minhas automações" && minhas.length > 0 ? ` (${minhas.length})` : ""}
          </button>
        ))}
      </div>

      {aba === "Modelos" && (
        <div className="grid gap-[18px] sm:grid-cols-2 xl:grid-cols-3">
          {(modelos.data ?? []).map((m) => (
            <section key={m.chave} className="card-surface flex flex-col p-[22px]">
              <span className="eyebrow">{area.toUpperCase()}</span>
              <h2 className="mt-3.5 mb-2 text-[17px] font-bold">{m.nome}</h2>
              <div>
                <Etiqueta>{m.gatilho_rotulo}</Etiqueta>
              </div>
              <p className="mt-3 text-sm text-muted">{m.descricao}</p>
              <p className="mt-2 text-sm">
                {m.acao_rotulo}
                {m.tipo_atividade_rotulo ? ` · ${m.tipo_atividade_rotulo}` : ""}
              </p>
              <div className="mt-auto pt-4">
                <Button variant="outline" disabled={!podeEditar} onClick={() => setEditando({ id: null, dados: doModelo(m) })}>
                  Usar modelo
                </Button>
              </div>
            </section>
          ))}
        </div>
      )}

      {aba === "Minhas automações" && (
        <DataTable
          colunas={colunas}
          linhas={minhas}
          chave={(a) => a.id}
          carregando={lista.isPending}
          onLinha={podeEditar ? (a) => setEditando({ id: a.id, dados: deAutomacao(a) }) : undefined}
          vazio={{
            icone: Workflow,
            titulo: "Nenhuma automação criada nesta área.",
            descricao: "Comece por um modelo.",
            acao: (
              <Button variant="outline" onClick={() => setAba("Modelos")}>
                Ver modelos
              </Button>
            ),
          }}
        />
      )}

      {aba === "Histórico" && (
        <DataTable
          colunas={colunasHistorico}
          linhas={historico.data}
          chave={(e) => e.id}
          carregando={historico.isPending}
          vazio={{ icone: History, titulo: "Nenhuma execução nesta área.", descricao: "Testes e execuções do motor aparecem aqui." }}
        />
      )}

      <Painel titulo="Atividade e envio são ações diferentes" className="mt-[22px]">
        <p className="text-sm leading-relaxed">
          “Criar atividade de WhatsApp” agenda o trabalho de uma pessoa. “Enviar mensagem de WhatsApp” usa um conector autorizado. O mesmo vale para
          e-mail. Reunião cria uma atividade; convite depende de agenda conectada.
        </p>
        <Fonte
          limite={[
            "Execução idempotente (identificador por automação, registro e ocorrência), retentativas limitadas, histórico e prevenção de ciclos.",
            "Envios ficam pendentes de conector autorizado: nenhuma mensagem, convite ou pagamento é enviado nesta fase.",
          ]}
        />
      </Painel>

      {editando && catalogo.data && (
        <EditorAutomacao
          key={`${editando.id ?? "nova"}-${editando.dados.nome}`}
          id={editando.id}
          inicial={editando.dados}
          catalogo={catalogo.data}
          onFechar={() => setEditando(null)}
          onSalvo={() => {
            setEditando(null);
            setAba("Minhas automações");
            recarregar();
          }}
        />
      )}

      <Drawer aberto={!!teste} onFechar={() => setTeste(null)} rotulo="AUTOMAÇÃO / TESTE" titulo="Teste sem execução" descricao={teste?.automacao.nome}>
        {teste && (
          <>
            <div className="rounded-[9px] bg-subtle p-[18px] text-[13px]">
              <p className="flex items-center gap-2 font-semibold">
                <FlaskConical className="size-4 text-primary" /> {teste.resultado.resumo}
              </p>
              {teste.resultado.amostra.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5">
                  {teste.resultado.amostra.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              )}
              <p className="mt-3">Ação preparada: {teste.resultado.acao}.</p>
              <p>
                Prazo: {teste.automacao.prazo_dias ?? 0} dia(s) · Responsável:{" "}
                {teste.automacao.responsavel_regra?.startsWith("usuario:") ? "pessoa definida" : "responsável do registro"}
              </p>
            </div>
            <p className="mt-4 text-sm text-muted">{teste.resultado.observacao}</p>
          </>
        )}
      </Drawer>
    </>
  );
}

function rotuloTipo(c: CatalogoAutomacoes | undefined, id: string | null) {
  return c?.tipos_atividade.find((t) => t.id === id)?.rotulo ?? id ?? "";
}

function EditorAutomacao({
  id,
  inicial,
  catalogo,
  onFechar,
  onSalvo,
}: {
  id: number | null;
  inicial: AutomacaoIn;
  catalogo: CatalogoAutomacoes;
  onFechar: () => void;
  onSalvo: () => void;
}) {
  const [f, setF] = useState<AutomacaoIn>(inicial);
  const [revisado, setRevisado] = useState(id !== null);
  const usuarios = useQuery({
    queryKey: ["config", "usuarios", "opcoes"],
    queryFn: () => api.get<UsuarioOpcao[]>("/config/usuarios/opcoes"),
    meta: { silencioso: true },
  });
  const set = <K extends keyof AutomacaoIn>(k: K, v: AutomacaoIn[K]) => setF((x) => ({ ...x, [k]: v }));

  const salvar = useMutation({
    mutationFn: () => {
      if (id === null) return api.post<Automacao>("/orquestracao/automacoes", f);
      const { area: _area, ...resto } = f;
      void _area;
      return api.patch<Automacao>(`/orquestracao/automacoes/${id}`, resto);
    },
    onSuccess: (a) => {
      notificar.sucesso(`Automação salva em ${a.area === "comercial" ? "Comercial" : "Financeiro"} (${a.estado === "ativa" ? "ativa" : "rascunho"}).`);
      onSalvo();
    },
  });

  const etapas = useMemo(() => {
    const funis = f.funil_id ? catalogo.funis.filter((x) => x.id === f.funil_id) : catalogo.funis;
    return funis.flatMap((x) => x.etapas.map((e) => ({ ...e, rotulo: catalogo.funis.length > 1 ? `${x.nome} · ${e.nome}` : e.nome })));
  }, [catalogo.funis, f.funil_id]);
  const campos = [
    ...catalogo.campos.filter((c) => (f.area === "comercial" ? c.objeto === "oportunidade" : false)).map((c) => ({ slug: c.slug, nome: c.nome })),
    ...catalogo.campos_padrao[f.area],
  ];
  const envio = catalogo.acoes.find((a) => a.id === f.acao)?.envio ?? false;
  const canal = f.acao === "enviar_email" ? "email" : f.acao === "enviar_whatsapp" ? "whatsapp" : null;
  const conectado = canal ? catalogo.canais_conectados.includes(canal) : true;
  const dica = envio
    ? `Envio requer conexão autorizada, destinatário válido, modelo e regras de pausa. ${conectado ? "Canal conectado: os envios ficam pendentes do conector oficial." : "Canal desconectado: pode salvar em rascunho, mas não ativar."}`
    : f.acao === "atualizar_campo"
      ? "Escreva no modelo: campo = valor (ex.: interesse = Alto). Não pode alterar o campo que dispara a própria automação."
      : f.acao === "notificar"
        ? "Avisa o responsável dentro do FlicSales. Não envia mensagem externa."
        : "Cria trabalho interno com responsável, prazo, vínculo e tipo. Convites e execução externa permanecem separados.";
  const passos = [
    catalogo.gatilhos[f.area].find((g) => g.id === f.gatilho)?.rotulo ?? "Gatilho",
    f.campo ? `${campos.find((c) => c.slug === f.campo)?.nome ?? f.campo} ${catalogo.operadores.find((o) => o.id === f.operador)?.rotulo.toLowerCase() ?? ""} ${f.valor_esperado ?? ""}`.trim() : "Sem condição adicional",
    catalogo.acoes.find((a) => a.id === f.acao)?.rotulo ?? "Ação",
  ];

  return (
    <Drawer
      aberto
      onFechar={onFechar}
      rotulo={`AUTOMAÇÃO / ${f.area.toUpperCase()}`}
      titulo={`Automação ${f.area}`}
      rodape={
        <Button type="submit" form="f-automacao" disabled={salvar.isPending || !revisado}>
          {id === null ? "Salvar rascunho" : "Salvar"}
        </Button>
      }
    >
      <Passos passos={passos.map((p, i) => `${i + 1} · ${p}`)} />
      <form
        id="f-automacao"
        onSubmit={(e) => {
          e.preventDefault();
          salvar.mutate();
        }}
      >
        <CampoDrawer rotulo="Nome" obrigatorio htmlFor="au-nome">
          <Input id="au-nome" value={f.nome} onChange={(e) => set("nome", e.target.value)} required maxLength={150} />
        </CampoDrawer>
        <CampoDrawer rotulo="Gatilho" obrigatorio htmlFor="au-gatilho">
          <NativeSelect id="au-gatilho" value={f.gatilho} onChange={(e) => set("gatilho", e.target.value)} required>
            {catalogo.gatilhos[f.area].map((g) => (
              <option key={g.id} value={g.id}>
                {g.rotulo}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        {f.area === "comercial" && (
          <>
            <CampoDrawer rotulo="Funil" htmlFor="au-funil">
              <NativeSelect
                id="au-funil"
                value={f.funil_id ?? ""}
                onChange={(e) => setF((x) => ({ ...x, funil_id: e.target.value ? Number(e.target.value) : null, etapa_destino_id: null }))}
              >
                <option value="">Todos os funis</option>
                {catalogo.funis.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.nome}
                  </option>
                ))}
              </NativeSelect>
            </CampoDrawer>
            <CampoDrawer rotulo="Etapa de destino · quando aplicável" htmlFor="au-etapa">
              <NativeSelect
                id="au-etapa"
                value={f.etapa_destino_id ?? ""}
                onChange={(e) => set("etapa_destino_id", e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Qualquer etapa</option>
                {etapas.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.rotulo}
                  </option>
                ))}
              </NativeSelect>
            </CampoDrawer>
          </>
        )}
        <CampoDrawer rotulo="Campo monitorado / condição" htmlFor="au-campo">
          <NativeSelect
            id="au-campo"
            value={f.campo ?? ""}
            onChange={(e) => setF((x) => ({ ...x, campo: e.target.value || null, operador: e.target.value ? (x.operador ?? "igual") : null }))}
          >
            <option value="">Sem condição adicional</option>
            {campos.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Operador" htmlFor="au-operador">
          <NativeSelect id="au-operador" value={f.operador ?? ""} disabled={!f.campo} onChange={(e) => set("operador", e.target.value || null)}>
            {!f.campo && <option value="">—</option>}
            {catalogo.operadores.map((o) => (
              <option key={o.id} value={o.id}>
                {o.rotulo}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer
          rotulo={f.gatilho === "saldo_abaixo_limite" ? "Limite de saldo (R$)" : "Valor esperado"}
          htmlFor="au-valor"
          dica={f.gatilho === "saldo_abaixo_limite" ? "Dispara quando o saldo projetado fica abaixo deste valor." : undefined}
        >
          <Input
            id="au-valor"
            value={f.valor_esperado ?? ""}
            placeholder={f.gatilho === "saldo_abaixo_limite" ? "Ex.: 10.000,00" : "Ex.: Alto"}
            onChange={(e) => set("valor_esperado", e.target.value || null)}
            maxLength={200}
          />
        </CampoDrawer>
        <CampoDrawer
          rotulo="Prazo / período (dias)"
          htmlFor="au-prazo"
          dica={
            catalogo.gatilhos_de_evento.includes(f.gatilho)
              ? "Gatilho de evento: prazo da atividade criada, em dias úteis."
              : "Gatilho de tempo: janela ou atraso que dispara a automação."
          }
        >
          <Input
            id="au-prazo"
            type="number"
            min={0}
            max={365}
            value={f.prazo_dias ?? ""}
            onChange={(e) => set("prazo_dias", e.target.value === "" ? null : Number(e.target.value))}
          />
        </CampoDrawer>
        <CampoDrawer rotulo="Ação" obrigatorio htmlFor="au-acao">
          <NativeSelect id="au-acao" value={f.acao} onChange={(e) => set("acao", e.target.value)}>
            {catalogo.acoes.map((a) => (
              <option key={a.id} value={a.id}>
                {a.rotulo}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Tipo da atividade · para criar atividade" htmlFor="au-tipo">
          <NativeSelect
            id="au-tipo"
            value={f.tipo_atividade ?? "tarefa"}
            disabled={f.acao !== "criar_atividade"}
            onChange={(e) => set("tipo_atividade", e.target.value)}
          >
            {catalogo.tipos_atividade.map((t) => (
              <option key={t.id} value={t.id}>
                {t.rotulo}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Responsável" obrigatorio htmlFor="au-resp">
          <NativeSelect id="au-resp" value={f.responsavel_regra ?? "responsavel_do_registro"} onChange={(e) => set("responsavel_regra", e.target.value)}>
            <option value="responsavel_do_registro">{f.area === "comercial" ? "Responsável da oportunidade" : "Responsável do título"}</option>
            {(usuarios.data ?? []).map((u) => (
              <option key={u.id} value={`usuario:${u.id}`}>
                {u.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Destinatário · para envio" htmlFor="au-dest">
          <NativeSelect id="au-dest" value={f.destinatario ?? ""} disabled={!envio} onChange={(e) => set("destinatario", e.target.value || null)}>
            <option value="">—</option>
            {catalogo.destinatarios.map((d) => (
              <option key={d.id} value={d.id}>
                {d.rotulo}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer
          rotulo="Modelo / instrução"
          obrigatorio
          htmlFor="au-conteudo"
          dica={`Variáveis: ${catalogo.variaveis.join(", ")} e campos personalizados compatíveis com o objeto.`}
        >
          <Textarea id="au-conteudo" value={f.conteudo} onChange={(e) => set("conteudo", e.target.value)} required className="min-h-[90px]" maxLength={4000} />
        </CampoDrawer>
        <div className={cn("mt-4 rounded-[9px] p-3.5 text-[13px]", envio && !conectado ? "bg-amber/10 text-amber-ink" : "bg-subtle")}>{dica}</div>
        <label className="mt-4 flex items-start gap-2 text-sm">
          <Checkbox checked={revisado} onCheckedChange={(v) => setRevisado(v === true)} aria-required />
          <span>Revisar condições antes de executar e impedir duplicação</span>
        </label>
      </form>
    </Drawer>
  );
}
