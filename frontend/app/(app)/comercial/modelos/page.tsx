"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Mail } from "lucide-react";
import { useState } from "react";

import { lerForm, nulo, useInvalidarComercial, useOpcoes } from "@/components/comercial/dados";
import { BarraFiltros } from "@/components/flic/barra-filtros";
import { DataTable, type Coluna } from "@/components/flic/data-table";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { useAtalhoNovo } from "@/components/flic/eventos";
import { NativeSelect } from "@/components/flic/form";
import { PageHeader } from "@/components/flic/page-header";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CANAIS_MODELO, type CanalModelo, FINALIDADES_MODELO, type FinalidadeModelo, type ModeloComunicacao, type PreviaModelo } from "@/lib/tipos-comercial";

const VARIAVEIS = ["{{empresa.nome}}", "{{contato.nome}}", "{{oportunidade.titulo}}", "{{titulo.valor}}", "{{titulo.vencimento}}"];
const rotuloCanal = (c: string) => CANAIS_MODELO.find((x) => x.valor === c)?.rotulo ?? c;
const rotuloFinalidade = (c: string) => FINALIDADES_MODELO.find((x) => x.valor === c)?.rotulo ?? c;

export default function ModelosPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.recursos.editar");
  const [q, setQ] = useState("");
  const [canal, setCanal] = useState("todos");
  const [form, setForm] = useState<{ aberto: boolean; m: ModeloComunicacao | null }>({ aberto: false, m: null });
  const [previa, setPrevia] = useState<ModeloComunicacao | null>(null);
  useAtalhoNovo(() => editar && setForm({ aberto: true, m: null }));

  const { data: lista, isPending } = useQuery({
    queryKey: ["comercial", "modelos", q, canal],
    queryFn: () => api.get<ModeloComunicacao[]>("/comercial/modelos", { q, canal: canal === "todos" ? undefined : canal, incluir_inativos: true }),
  });

  const colunas: Coluna<ModeloComunicacao>[] = [
    {
      id: "nome",
      titulo: "Nome",
      celula: (m) => (
        <>
          <strong>{m.nome}</strong>
          <p className="text-muted">{m.assunto ?? "Sem assunto"}</p>
        </>
      ),
    },
    { id: "canal", titulo: "Canal", celula: (m) => rotuloCanal(m.canal) },
    { id: "fin", titulo: "Finalidade", celula: (m) => rotuloFinalidade(m.finalidade) },
    {
      id: "status",
      titulo: "Status",
      celula: (m) => (
        <div className="flex gap-1">
          <Etiqueta tom={m.status === "revisado" ? "green" : "neutra"}>{m.status === "revisado" ? "Revisado" : "Rascunho"}</Etiqueta>
          {!m.ativo && <Etiqueta tom="amber">Inativo</Etiqueta>}
        </div>
      ),
    },
    {
      id: "cmd",
      titulo: "Comandos",
      celula: (m) => (
        <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); setPrevia(m); }}>
          Pré-visualizar
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        titulo="Modelos de comunicação"
        descricao="Roteiros e mensagens revisados, com variáveis do registro. Nada é enviado daqui."
        acao={editar ? <Button onClick={() => setForm({ aberto: true, m: null })}>+ Novo registro</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar registros desta tela" }}
        chips={{ opcoes: [{ valor: "todos", rotulo: "Todos" }, ...CANAIS_MODELO.map((c) => ({ valor: c.valor, rotulo: c.rotulo }))], valor: canal, onChange: setCanal }}
        exportar={{
          nome: "modelos-comunicacao",
          linhas: lista ?? [],
          colunas: [
            { titulo: "Nome", valor: (m: ModeloComunicacao) => m.nome },
            { titulo: "Canal", valor: (m: ModeloComunicacao) => rotuloCanal(m.canal) },
            { titulo: "Finalidade", valor: (m: ModeloComunicacao) => rotuloFinalidade(m.finalidade) },
            { titulo: "Assunto", valor: (m: ModeloComunicacao) => m.assunto ?? "" },
            { titulo: "Status", valor: (m: ModeloComunicacao) => m.status },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista}
        chave={(m) => m.id}
        onLinha={(m) => setForm({ aberto: true, m })}
        carregando={isPending}
        vazio={{ icone: Mail, titulo: "Nenhum modelo ainda.", descricao: "Use “Novo registro” para começar." }}
      />
      <Drawer aberto={form.aberto} onFechar={() => setForm({ aberto: false, m: null })} titulo={form.m ? "Editar · Modelos de comunicação" : "Novo registro · Modelos de comunicação"}>
        {form.aberto && <FormModelo key={form.m?.id ?? "novo"} m={form.m} editar={editar} onFechar={() => setForm({ aberto: false, m: null })} />}
      </Drawer>
      <Drawer aberto={!!previa} onFechar={() => setPrevia(null)} titulo={previa ? `Prévia · ${previa.nome}` : undefined}>
        {previa && <Previa key={previa.id} m={previa} />}
      </Drawer>
    </>
  );
}

function FormModelo({ m, editar, onFechar }: { m: ModeloComunicacao | null; editar: boolean; onFechar: () => void }) {
  const invalidar = useInvalidarComercial();
  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) => (m ? api.patch<ModeloComunicacao>(`/comercial/modelos/${m.id}`, corpo) : api.post<ModeloComunicacao>("/comercial/modelos", corpo)),
    onSuccess: () => {
      invalidar();
      notificar("Modelo salvo");
      onFechar();
    },
  });
  const ativar = useMutation({
    mutationFn: (ativo: boolean) => api.patch<ModeloComunicacao>(`/comercial/modelos/${m?.id}`, { ativo }),
    onSuccess: (r) => {
      invalidar();
      notificar(r.ativo ? "Modelo reativado" : "Modelo inativado");
      onFechar();
    },
  });
  return (
    <form
      id="form-modelo"
      onSubmit={(e) => {
        e.preventDefault();
        const f = lerForm(e.currentTarget);
        salvar.mutate({
          nome: f.nome.trim(),
          canal: f.canal as CanalModelo,
          finalidade: f.finalidade as FinalidadeModelo,
          assunto: nulo(f.assunto),
          conteudo: f.conteudo,
          status: f.status,
        });
      }}
    >
      <fieldset disabled={!editar}>
        <CampoDrawer rotulo="Nome" obrigatorio>
          <Input name="nome" required defaultValue={m?.nome ?? ""} maxLength={150} />
        </CampoDrawer>
        <CampoDrawer rotulo="Canal" obrigatorio>
          <NativeSelect name="canal" defaultValue={m?.canal ?? "email"}>
            {CANAIS_MODELO.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.rotulo}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Finalidade" obrigatorio>
          <NativeSelect name="finalidade" defaultValue={m?.finalidade ?? "prospeccao"}>
            {FINALIDADES_MODELO.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.rotulo}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Assunto">
          <Input name="assunto" defaultValue={m?.assunto ?? ""} maxLength={200} />
        </CampoDrawer>
        <CampoDrawer rotulo="Conteúdo / roteiro" obrigatorio dica={`Variáveis: ${VARIAVEIS.join(", ")} e campos personalizados compatíveis com o objeto.`}>
          <Textarea name="conteudo" required rows={7} defaultValue={m?.conteudo ?? "Olá, {{contato.nome}}! "} />
        </CampoDrawer>
        <CampoDrawer rotulo="Status" obrigatorio>
          <NativeSelect name="status" defaultValue={m?.status ?? "rascunho"}>
            <option value="rascunho">Rascunho</option>
            <option value="revisado">Revisado</option>
          </NativeSelect>
        </CampoDrawer>
      </fieldset>
      {m && m.variaveis.length > 0 && (
        <p className="mt-3 text-xs text-muted">Variáveis usadas: {m.variaveis.map((v) => `{{${v}}}`).join(", ")}</p>
      )}
      {editar && (
        <div className="mt-5 flex flex-wrap gap-2">
          <Button type="submit" disabled={salvar.isPending}>
            {salvar.isPending && <Loader2 className="animate-spin" />}
            Salvar registro
          </Button>
          {m && (
            <Button type="button" variant="outline" disabled={ativar.isPending} onClick={() => ativar.mutate(!m.ativo)}>
              {m.ativo ? "Inativar" : "Reativar"}
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onFechar}>
            Cancelar
          </Button>
        </div>
      )}
      <p className="mt-4 text-xs text-muted">Modelo não envia nada: envio exige canal conectado e autorizado em Integrações.</p>
    </form>
  );
}

function Previa({ m }: { m: ModeloComunicacao }) {
  const { data: opcoes } = useOpcoes();
  const [opId, setOpId] = useState("");
  const gerar = useMutation({
    mutationFn: () => api.post<PreviaModelo>(`/comercial/modelos/${m.id}/previa`, { oportunidade_id: opId ? Number(opId) : null }),
  });
  return (
    <>
      <CampoDrawer rotulo="Oportunidade para preencher as variáveis">
        <NativeSelect value={opId} onChange={(e) => setOpId(e.target.value)}>
          <option value="">Sem oportunidade (variáveis ficam visíveis)</option>
          {(opcoes?.oportunidades ?? []).map((o) => (
            <option key={o.id} value={o.id}>
              {o.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <Button className="mt-4" disabled={gerar.isPending} onClick={() => gerar.mutate()}>
        Pré-visualizar
      </Button>
      {gerar.data && (
        <div className="mt-4 rounded-[10px] border border-line bg-subtle p-4 text-sm">
          {gerar.data.assunto && (
            <p className="mb-2">
              <strong>Assunto:</strong> {gerar.data.assunto}
            </p>
          )}
          <p className="whitespace-pre-wrap">{gerar.data.conteudo}</p>
          {gerar.data.faltando.length > 0 && <p className="mt-3 text-xs text-amber-ink">Sem valor no registro: {gerar.data.faltando.map((v) => `{{${v}}}`).join(", ")}</p>}
        </div>
      )}
      <p className="mt-4 text-xs text-muted">Prévia para revisão. Nenhuma mensagem é enviada.</p>
    </>
  );
}
