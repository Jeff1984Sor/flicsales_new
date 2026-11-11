"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, MessagesSquare } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AtividadeForm } from "@/components/comercial/atividade-form";
import { lerForm, nulo, numeroOuNulo, useInvalidarComercial, useOpcoes } from "@/components/comercial/dados";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { EmptyState } from "@/components/flic/empty-state";
import { EnviarEmailDrawer } from "@/components/flic/enviar-email";
import { EnviarWhatsAppDrawer, usePodeWhatsApp } from "@/components/flic/enviar-whatsapp";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { Fonte } from "@/components/flic/fonte";
import { NativeSelect } from "@/components/flic/form";
import { PageHeader } from "@/components/flic/page-header";
import { GradePaineis, Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { data, dataHora, hojeISO } from "@/lib/format";
import {
  type AnaliseComunicacao,
  type AtividadeEntrada,
  CANAIS_COMUNICACAO,
  type CanalComunicacao,
  type Comunicacao,
  rotuloCanal,
} from "@/lib/tipos-comercial";

interface RascunhoResposta {
  rascunho: string;
  aviso: string;
}

const AVISO_IA = "A análise por IA ainda não está disponível neste ambiente.";

/** A Orquestração pode devolver `{analise}`, a comunicação inteira ou a própria análise. */
function extrairAnalise(r: unknown): AnaliseComunicacao | null {
  if (!r || typeof r !== "object") return null;
  const o = r as Record<string, unknown>;
  const cand = (o.analise && typeof o.analise === "object" ? o.analise : o) as Record<string, unknown>;
  if (["necessidades", "objecoes", "compromissos", "citacoes"].some((k) => Array.isArray(cand[k]))) {
    return cand as unknown as AnaliseComunicacao;
  }
  return null;
}

export default function ComunicacoesPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.comunicacoes.editar");
  const [q, setQ] = useState("");
  const [canal, setCanal] = useState("todos");
  const [importar, setImportar] = useState(false);
  const [sel, setSel] = useState<Comunicacao | null>(null);
  const [autoAnalisar, setAutoAnalisar] = useState(false);
  const podeWhats = usePodeWhatsApp();
  const [email, setEmail] = useState<Envio | null>(null);
  useAtalhoNovo(() => editar && setImportar(true));

  const { data: lista, isPending } = useQuery({
    queryKey: ["comercial", "comunicacoes", q, canal],
    queryFn: () => api.get<Comunicacao[]>("/comercial/comunicacoes", { q, canal: canal === "todos" ? undefined : canal }),
  });

  return (
    <>
      <PageHeader
        titulo="Comunicações"
        descricao="Reuniões, e-mails e mensagens com contexto de negócio."
        acoes={
          editar ? (
            <>
              <Button variant="outline" onClick={() => setEmail({ canal: "email", empresaId: null, oportunidadeId: null })}>
                ✉ Enviar e-mail
              </Button>
              {podeWhats && (
                <Button variant="outline" onClick={() => setEmail({ canal: "whatsapp", empresaId: null, oportunidadeId: null })}>
                  WhatsApp
                </Button>
              )}
            </>
          ) : undefined
        }
        acao={editar ? <Button onClick={() => setImportar(true)}>+ Importar conteúdo</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Buscar assunto ou conteúdo" }}
        chips={{ opcoes: [{ valor: "todos", rotulo: "Todos" }, ...CANAIS_COMUNICACAO.map((c) => ({ valor: c.valor, rotulo: c.rotulo }))], valor: canal, onChange: setCanal }}
        exportar={{
          nome: "comunicacoes",
          linhas: lista ?? [],
          colunas: [
            { titulo: "Canal", valor: (c: Comunicacao) => rotuloCanal(c.canal) },
            { titulo: "Assunto", valor: (c: Comunicacao) => c.titulo ?? "" },
            { titulo: "Data", valor: (c: Comunicacao) => data(c.data) },
            { titulo: "Empresa", valor: (c: Comunicacao) => c.empresa_nome ?? "" },
            { titulo: "Oportunidade", valor: (c: Comunicacao) => c.oportunidade_titulo ?? "" },
            { titulo: "Analisada", valor: (c: Comunicacao) => (c.analise ? "Sim" : "Não") },
          ],
        }}
      />
      <GradePaineis>
        <Painel titulo="Conversas vinculadas">
          {isPending ? (
            <p className="text-sm text-muted">Carregando…</p>
          ) : (lista ?? []).length === 0 ? (
            <EmptyState icone={MessagesSquare} titulo="Nenhuma conversa vinculada." descricao="Importe notas, e-mails ou mensagens autorizadas." />
          ) : (
            (lista ?? []).map((c) => (
              <div key={c.id} className="flex items-start justify-between gap-3 border-b border-line py-4 last:border-0">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-1.5">
                    <Etiqueta>{rotuloCanal(c.canal)}</Etiqueta>
                    {c.analise && <Etiqueta tom="green">Analisada</Etiqueta>}
                  </div>
                  <h3 className="mt-2.5 mb-1 font-bold">{c.titulo ?? "Sem título"}</h3>
                  <p className="text-xs text-muted">
                    {data(c.data)}
                    {c.empresa_nome ? ` · ${c.empresa_nome}` : ""}
                    {c.oportunidade_titulo ? ` · ${c.oportunidade_titulo}` : ""}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setAutoAnalisar(false);
                    setSel(c);
                  }}
                >
                  Analisar
                </Button>
              </div>
            ))
          )}
        </Painel>
        <Painel>
          <span className="eyebrow">ANÁLISE COM EVIDÊNCIAS</span>
          <h2 className="mt-4 text-[17px] font-bold">Da conversa à ação.</h2>
          <p className="mt-2 text-sm text-muted">Objetivo, necessidades declaradas, objeções e compromissos. Respostas e tarefas ficam em revisão.</p>
          <Fonte>
            <p>Canais desconectados: nenhuma conta pessoal é acessada. O texto importado é tratado como dado, nunca como instrução.</p>
            <p>Sem transcrição de áudio nem análise de emoções.</p>
          </Fonte>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => {
              const primeira = (lista ?? [])[0];
              if (!primeira) {
                notificar("Nenhuma conversa vinculada para analisar. Importe notas, e-mails ou mensagens autorizadas.");
                return;
              }
              setAutoAnalisar(true);
              setSel(primeira);
            }}
          >
            Analisar exemplo
          </Button>
        </Painel>
      </GradePaineis>

      <Drawer aberto={importar} onFechar={() => setImportar(false)} titulo="Importar comunicação">
        {importar && <FormImportar onFechar={() => setImportar(false)} aoImportar={setSel} />}
      </Drawer>
      <Drawer aberto={!!sel} onFechar={() => setSel(null)} titulo={sel ? `Análise de ${rotuloCanal(sel.canal)}` : undefined} descricao={sel?.titulo ?? undefined}>
        {sel && (
          <PainelAnalise
            key={sel.id}
            c={sel}
            editar={editar}
            autoAnalisar={autoAnalisar}
            onEmail={() => setEmail({ canal: "email", empresaId: sel.empresa_id, oportunidadeId: sel.oportunidade_id, assunto: sel.titulo ? `Re: ${sel.titulo}` : undefined })}
            onWhatsApp={podeWhats ? () => setEmail({ canal: "whatsapp", empresaId: sel.empresa_id, oportunidadeId: sel.oportunidade_id }) : undefined}
          />
        )}
      </Drawer>
      {email && <EnviarComunicacao key={`${email.canal}-${email.empresaId}-${email.oportunidadeId}`} inicial={email} onFechar={() => setEmail(null)} />}
    </>
  );
}

function FormImportar({ onFechar, aoImportar }: { onFechar: () => void; aoImportar: (c: Comunicacao) => void }) {
  const { data: opcoes } = useOpcoes();
  const invalidar = useInvalidarComercial();
  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) => api.post<Comunicacao>("/comercial/comunicacoes", corpo),
    onSuccess: (c) => {
      invalidar();
      notificar("Comunicação importada");
      onFechar();
      aoImportar(c);
    },
  });
  return (
    <form
      id="form-comunicacao"
      onSubmit={(e) => {
        e.preventDefault();
        const f = lerForm(e.currentTarget);
        if (!f.conteudo.trim()) {
          notificar("Cole o conteúdo da conversa para importar.");
          return;
        }
        salvar.mutate({
          canal: f.canal as CanalComunicacao,
          titulo: nulo(f.titulo),
          data: nulo(f.data),
          oportunidade_id: numeroOuNulo(f.oportunidade_id),
          empresa_id: numeroOuNulo(f.empresa_id),
          conteudo: f.conteudo,
        });
      }}
    >
      <CampoDrawer rotulo="Canal" obrigatorio>
        <NativeSelect name="canal" defaultValue="notas">
          {CANAIS_COMUNICACAO.map((c) => (
            <option key={c.valor} value={c.valor}>
              {c.rotulo}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Assunto">
        <Input name="titulo" maxLength={200} placeholder="Ex.: Discovery · Aurora" />
      </CampoDrawer>
      <CampoDrawer rotulo="Data">
        <Input name="data" type="date" defaultValue={hojeISO()} />
      </CampoDrawer>
      <CampoDrawer rotulo="Oportunidade">
        <NativeSelect name="oportunidade_id" defaultValue="">
          <option value="">Sem oportunidade</option>
          {(opcoes?.oportunidades ?? []).map((o) => (
            <option key={o.id} value={o.id}>
              {o.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Empresa" dica="Em branco: a empresa da oportunidade.">
        <NativeSelect name="empresa_id" defaultValue="">
          <option value="">Da oportunidade / sem empresa</option>
          {(opcoes?.empresas ?? []).map((e) => (
            <option key={e.id} value={e.id}>
              {e.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Conteúdo fornecido" obrigatorio>
        <Textarea name="conteudo" rows={8} placeholder="Cole notas ou uma mensagem autorizada" />
      </CampoDrawer>
      <p className="mt-4 text-xs text-muted">O texto importado é dado, nunca instrução. A análise só acontece quando você pedir.</p>
      <div className="mt-5 flex gap-2">
        <Button type="submit" disabled={salvar.isPending}>
          {salvar.isPending && <Loader2 className="animate-spin" />}
          Importar
        </Button>
        <Button type="button" variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}

/** "✉ Enviar e-mail" em Comunicações: escolhe a oportunidade/empresa (sugere as pessoas dela) e envia; vira comunicação. */
/** Envio a partir de Comunicações: e-mail ou WhatsApp, com a oportunidade/empresa escolhida. */
interface Envio {
  canal: "email" | "whatsapp";
  empresaId: number | null;
  oportunidadeId: number | null;
  assunto?: string;
}

/** "✉ Enviar e-mail" / "WhatsApp" em Comunicações: escolhe a oportunidade/empresa (sugere as pessoas dela) e envia; vira comunicação. */
function EnviarComunicacao({ inicial, onFechar }: { inicial: Envio; onFechar: () => void }) {
  const { data: opcoes } = useOpcoes();
  const [opId, setOpId] = useState(inicial.oportunidadeId != null ? String(inicial.oportunidadeId) : "");
  const [empId, setEmpId] = useState(inicial.empresaId != null ? String(inicial.empresaId) : "");
  const op = (opcoes?.oportunidades ?? []).find((o) => String(o.id) === opId);
  const empresaId = empId ? Number(empId) : (op?.empresa_id ?? null);
  const vinculo = (
        <>
          <CampoDrawer rotulo="Oportunidade">
            <NativeSelect value={opId} onChange={(e) => setOpId(e.target.value)}>
              <option value="">Sem oportunidade</option>
              {(opcoes?.oportunidades ?? []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.nome}
                </option>
              ))}
            </NativeSelect>
          </CampoDrawer>
          <CampoDrawer rotulo="Empresa" dica="Em branco: a empresa da oportunidade.">
            <NativeSelect value={empId} onChange={(e) => setEmpId(e.target.value)}>
              <option value="">Da oportunidade / sem empresa</option>
              {(opcoes?.empresas ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.nome}
                </option>
              ))}
            </NativeSelect>
          </CampoDrawer>
        </>
  );
  const oportunidadeId = opId ? Number(opId) : null;
  if (inicial.canal === "whatsapp") {
    return (
      <EnviarWhatsAppDrawer
        aberto
        onFechar={onFechar}
        destino={{ tipo: "comunicacao" }}
        empresaId={empresaId}
        oportunidadeId={oportunidadeId}
        modelos="comercial"
        contexto="A mensagem enviada fica registrada como comunicação de WhatsApp."
        vinculo={vinculo}
      />
    );
  }
  return (
    <EnviarEmailDrawer
      aberto
      onFechar={onFechar}
      destino={{ tipo: "comunicacao" }}
      empresaId={empresaId}
      oportunidadeId={oportunidadeId}
      modelos="comercial"
      contexto="A mensagem enviada fica registrada como comunicação de e-mail."
      assuntoInicial={inicial.assunto}
      vinculo={vinculo}
    />
  );
}

function PainelAnalise({
  c,
  editar,
  autoAnalisar = false,
  onEmail,
  onWhatsApp,
}: {
  c: Comunicacao;
  editar: boolean;
  autoAnalisar?: boolean;
  onEmail: () => void;
  /** presente só com o WhatsApp conectado */
  onWhatsApp?: () => void;
}) {
  const invalidar = useInvalidarComercial();
  const [analise, setAnalise] = useState<AnaliseComunicacao | null>(c.analise);
  const [aviso, setAviso] = useState<string | null>(null);
  const [rascunho, setRascunho] = useState<RascunhoResposta | null>(null);
  const [tarefa, setTarefa] = useState<Partial<AtividadeEntrada> | null>(null);

  const analisar = useMutation({
    mutationFn: () => api.post<unknown>(`/orquestracao/ia/comunicacoes/${c.id}/analisar`),
    meta: { silencioso: true },
    onSuccess: async (r) => {
      const a = extrairAnalise(r);
      if (!a) {
        setAviso(AVISO_IA);
        return;
      }
      setAviso(null);
      try {
        const salva = await api.put<Comunicacao>(`/comercial/comunicacoes/${c.id}/analise`, { analise: a });
        setAnalise(salva.analise);
      } catch {
        setAnalise(a);
      }
      invalidar();
    },
    onError: () => setAviso(AVISO_IA),
  });
  // "Analisar exemplo": analisa a comunicação assim que o drawer abre (se ainda não tiver análise)
  const disparou = useRef(false);
  const { mutate: analisarAgora } = analisar;
  useEffect(() => {
    if (!autoAnalisar || !editar || c.analise || disparou.current) return;
    disparou.current = true;
    analisarAgora();
  }, [autoAnalisar, editar, c.analise, analisarAgora]);

  const responder = useMutation({
    mutationFn: () => api.post<RascunhoResposta>(`/comercial/comunicacoes/${c.id}/resposta`),
    onSuccess: setRascunho,
  });

  const base: Partial<AtividadeEntrada> = { oportunidade_id: c.oportunidade_id, empresa_id: c.empresa_id, origem: "ia", prazo: hojeISO() };
  const sugerida = analise?.compromissos[0] ?? analise?.necessidades[0];

  return (
    <>
      <div className="flex flex-wrap gap-1.5">
        <Etiqueta>{rotuloCanal(c.canal)}</Etiqueta>
        {c.analisada_em && <Etiqueta tom="green">Analisada em {dataHora(c.analisada_em)}</Etiqueta>}
      </div>
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer font-medium">Conteúdo fornecido</summary>
        <p className="mt-2 rounded-[8px] bg-subtle p-3 whitespace-pre-wrap">{c.conteudo}</p>
      </details>

      {aviso && <p className="mt-4 rounded-[8px] bg-amber/15 p-3 text-sm text-amber-ink">{aviso}</p>}

      {analise ? (
        <div className="mt-4 rounded-[10px] border border-line bg-subtle p-4">
          <Bloco titulo="Necessidade declarada" itens={analise.necessidades} />
          <Bloco titulo="Objeção" itens={analise.objecoes} />
          <Bloco titulo="Compromisso identificado" itens={analise.compromissos} />
          <Fonte
            fonte={`${rotuloCanal(c.canal)} · ${c.titulo ?? "Comunicação"} · ${data(c.data)}`}
            limite={[...(analise.limites ?? []), "Sem transcrição de áudio nem análise de emoções."]}
          >
            {analise.citacoes.map((ci, i) => (
              <p key={i}>
                “{ci.trecho}”{ci.fonte ? ` — ${ci.fonte}` : ""}
              </p>
            ))}
          </Fonte>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted">Ainda sem análise. Peça a análise para extrair necessidades, objeções e compromissos com citação literal.</p>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        <Button variant={analise ? "outline" : "default"} disabled={analisar.isPending} onClick={() => analisar.mutate()}>
          {analisar.isPending && <Loader2 className="animate-spin" />}
          {analise ? "Analisar de novo" : "Analisar"}
        </Button>
        {editar && analise && (
          <Button onClick={() => setTarefa({ ...base, tipo: "tarefa", assunto: sugerida ? sugerida.slice(0, 200) : `Retomar ${c.titulo ?? "conversa"}` })}>
            Criar tarefa sugerida
          </Button>
        )}
        <Button variant="outline" disabled={responder.isPending} onClick={() => responder.mutate()}>
          Preparar resposta
        </Button>
        {editar && (
          <Button variant="outline" onClick={onEmail}>
            ✉ Enviar e-mail
          </Button>
        )}
        {editar && onWhatsApp && (
          <Button variant="outline" onClick={onWhatsApp}>
            WhatsApp
          </Button>
        )}
      </div>

      {rascunho && (
        <div className="mt-5">
          <h3 className="text-sm font-bold">Resposta em rascunho</h3>
          <Textarea className="mt-2" rows={6} defaultValue={rascunho.rascunho} />
          <p className="mt-2 text-xs text-muted">Rascunho. Nenhum envio é feito. {rascunho.aviso}</p>
          {editar && (
            <Button
              className="mt-3"
              variant="outline"
              onClick={() =>
                setTarefa({
                  ...base,
                  tipo: c.canal === "whatsapp" ? "whatsapp" : "email",
                  assunto: `Revisar e enviar resposta${c.empresa_nome ? ` à ${c.empresa_nome}` : ""}`,
                  objetivo: rascunho.rascunho,
                })
              }
            >
              Usar como próxima atividade
            </Button>
          )}
        </div>
      )}

      <AtividadeForm aberto={!!tarefa} onFechar={() => setTarefa(null)} titulo="Tarefa sugerida · revise antes de salvar" inicial={tarefa ?? undefined} />
    </>
  );
}

function Bloco({ titulo, itens }: { titulo: string; itens: string[] }) {
  return (
    <div className="mb-3">
      <h3 className="text-sm font-bold">{titulo}</h3>
      {itens.length === 0 ? (
        <p className="text-sm text-muted">Nada identificado.</p>
      ) : (
        itens.map((t) => (
          <p key={t} className="text-sm">
            {t}
          </p>
        ))
      )}
    </div>
  );
}
