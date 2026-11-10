"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BookOpenCheck, Loader2 } from "lucide-react";
import { useState } from "react";

import { lerForm, nulo, numeroOuNulo, useInvalidarComercial, useOpcoes, useUsuarios } from "@/components/comercial/dados";
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
import type { Playbook } from "@/lib/tipos-comercial";

export default function PlaybooksPage() {
  const { pode } = useAuth();
  const editar = pode("comercial.recursos.editar");
  const [q, setQ] = useState("");
  const [inativos, setInativos] = useState("ativos");
  const [form, setForm] = useState<{ aberto: boolean; p: Playbook | null }>({ aberto: false, p: null });
  useAtalhoNovo(() => editar && setForm({ aberto: true, p: null }));

  const { data: lista, isPending } = useQuery({
    queryKey: ["comercial", "playbooks", q, inativos],
    queryFn: () => api.get<Playbook[]>("/comercial/playbooks", { q, incluir_inativos: inativos === "todos" }),
  });

  const colunas: Coluna<Playbook>[] = [
    {
      id: "nome",
      titulo: "Nome",
      celula: (p) => (
        <>
          <strong>{p.nome}</strong>
          <p className="text-muted">{p.objetivo}</p>
        </>
      ),
    },
    { id: "funil", titulo: "Funil", celula: (p) => p.funil_nome ?? "Todos" },
    { id: "etapa", titulo: "Etapa", celula: (p) => p.etapa_nome ?? "—" },
    { id: "resp", titulo: "Responsável", celula: (p) => p.responsavel_nome ?? "—" },
    { id: "estado", titulo: "Estado", celula: (p) => <Etiqueta tom={p.ativo ? "green" : "neutra"}>{p.ativo ? "Ativo" : "Inativo"}</Etiqueta> },
  ];

  return (
    <>
      <PageHeader
        titulo="Playbooks"
        descricao="Objetivo, perguntas de discovery, critérios para avançar e objeções por etapa."
        acao={editar ? <Button onClick={() => setForm({ aberto: true, p: null })}>+ Novo registro</Button> : undefined}
      />
      <BarraFiltros
        busca={{ valor: q, onChange: setQ, placeholder: "Filtrar registros desta tela" }}
        chips={{ opcoes: [{ valor: "ativos", rotulo: "Ativos" }, { valor: "todos", rotulo: "Todos" }], valor: inativos, onChange: setInativos }}
        exportar={{
          nome: "playbooks",
          linhas: lista ?? [],
          colunas: [
            { titulo: "Nome", valor: (p: Playbook) => p.nome },
            { titulo: "Funil", valor: (p: Playbook) => p.funil_nome ?? "" },
            { titulo: "Etapa", valor: (p: Playbook) => p.etapa_nome ?? "" },
            { titulo: "Objetivo", valor: (p: Playbook) => p.objetivo },
            { titulo: "Critérios para avançar", valor: (p: Playbook) => p.criterios_avanco },
          ],
        }}
      />
      <DataTable
        colunas={colunas}
        linhas={lista}
        chave={(p) => p.id}
        onLinha={(p) => setForm({ aberto: true, p })}
        carregando={isPending}
        vazio={{ icone: BookOpenCheck, titulo: "Nenhum playbook ainda.", descricao: "Use “Novo registro” para começar." }}
      />
      <Drawer aberto={form.aberto} onFechar={() => setForm({ aberto: false, p: null })} titulo={form.p ? "Editar · Playbooks" : "Novo registro · Playbooks"}>
        {form.aberto && <FormPlaybook key={form.p?.id ?? "novo"} p={form.p} editar={editar} onFechar={() => setForm({ aberto: false, p: null })} />}
      </Drawer>
    </>
  );
}

function FormPlaybook({ p, editar, onFechar }: { p: Playbook | null; editar: boolean; onFechar: () => void }) {
  const { data: opcoes } = useOpcoes();
  const { data: usuarios } = useUsuarios();
  const invalidar = useInvalidarComercial();
  const [funilId, setFunilId] = useState(String(p?.funil_id ?? ""));
  const etapas = opcoes?.funis.find((f) => String(f.id) === funilId)?.etapas ?? [];
  const salvar = useMutation({
    mutationFn: (corpo: Record<string, unknown>) => (p ? api.patch<Playbook>(`/comercial/playbooks/${p.id}`, corpo) : api.post<Playbook>("/comercial/playbooks", corpo)),
    onSuccess: () => {
      invalidar();
      notificar("Playbook salvo");
      onFechar();
    },
  });
  const ativar = useMutation({
    mutationFn: (ativo: boolean) => api.patch<Playbook>(`/comercial/playbooks/${p?.id}`, { ativo }),
    onSuccess: (r) => {
      invalidar();
      notificar(r.ativo ? "Playbook reativado" : "Playbook inativado");
      onFechar();
    },
  });

  return (
    <form
      id="form-playbook"
      onSubmit={(e) => {
        e.preventDefault();
        const f = lerForm(e.currentTarget);
        salvar.mutate({
          nome: f.nome.trim(),
          funil_id: numeroOuNulo(f.funil_id),
          etapa_id: numeroOuNulo(f.etapa_id),
          objetivo: f.objetivo.trim(),
          perguntas_discovery: nulo(f.perguntas_discovery),
          criterios_avanco: f.criterios_avanco.trim(),
          objecoes: nulo(f.objecoes),
          proxima_acao_padrao: nulo(f.proxima_acao_padrao),
          responsavel_id: numeroOuNulo(f.responsavel_id),
        });
      }}
    >
      <fieldset disabled={!editar}>
        <CampoDrawer rotulo="Nome" obrigatorio>
          <Input name="nome" required defaultValue={p?.nome ?? ""} maxLength={150} />
        </CampoDrawer>
        <CampoDrawer rotulo="Funil">
          <NativeSelect name="funil_id" value={funilId} onChange={(e) => setFunilId(e.target.value)}>
            <option value="">Todos os funis</option>
            {(opcoes?.funis ?? []).map((f) => (
              <option key={f.id} value={f.id}>
                {f.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Etapa">
          <NativeSelect key={funilId} name="etapa_id" defaultValue={String(p?.etapa_id ?? "")} disabled={!funilId}>
            <option value="">Qualquer etapa</option>
            {etapas.map((e) => (
              <option key={e.id} value={e.id}>
                {e.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
        <CampoDrawer rotulo="Objetivo" obrigatorio>
          <Textarea name="objetivo" required defaultValue={p?.objetivo ?? ""} />
        </CampoDrawer>
        <CampoDrawer rotulo="Perguntas de discovery">
          <Textarea name="perguntas_discovery" defaultValue={p?.perguntas_discovery ?? ""} />
        </CampoDrawer>
        <CampoDrawer rotulo="Critérios para avançar" obrigatorio>
          <Textarea name="criterios_avanco" required defaultValue={p?.criterios_avanco ?? ""} />
        </CampoDrawer>
        <CampoDrawer rotulo="Objeções e orientações">
          <Textarea name="objecoes" defaultValue={p?.objecoes ?? ""} />
        </CampoDrawer>
        <CampoDrawer rotulo="Próxima ação padrão">
          <Input name="proxima_acao_padrao" defaultValue={p?.proxima_acao_padrao ?? ""} />
        </CampoDrawer>
        <CampoDrawer rotulo="Responsável">
          <NativeSelect name="responsavel_id" defaultValue={String(p?.responsavel_id ?? "")}>
            <option value="">Sem responsável</option>
            {(usuarios ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.nome}
              </option>
            ))}
          </NativeSelect>
        </CampoDrawer>
      </fieldset>
      {editar && (
        <div className="mt-5 flex flex-wrap gap-2">
          <Button type="submit" disabled={salvar.isPending}>
            {salvar.isPending && <Loader2 className="animate-spin" />}
            Salvar registro
          </Button>
          {p && (
            <Button type="button" variant="outline" disabled={ativar.isPending} onClick={() => ativar.mutate(!p.ativo)}>
              {p.ativo ? "Inativar" : "Reativar"}
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onFechar}>
            Cancelar
          </Button>
        </div>
      )}
      <p className="mt-4 text-xs text-muted">Nada é excluído: playbooks em uso são inativados e preservam o histórico.</p>
    </form>
  );
}
