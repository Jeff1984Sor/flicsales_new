"use client";

/**
 * Núcleo › Integrações (protótipo `integrations` + `integrationDetail`): cards Google Calendar, Microsoft Outlook,
 * E-mail e WhatsApp com estado, requisitos, segredo somente escrita ("configurado · termina em XXXX"), Testar conexão,
 * Revogar e último erro. Configurar exige `orquestracao.integracoes.editar`.
 * WhatsApp abre o formulário da Evolution API (`whatsapp-evolution.tsx`): URL, API key, instância e QR code.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ConfirmDialog } from "@/components/flic/confirm-dialog";
import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { Etiqueta, type TomEtiqueta } from "@/components/flic/etiqueta";
import { NativeSelect } from "@/components/flic/form";
import { Fonte } from "@/components/flic/fonte";
import { PageHeader } from "@/components/flic/page-header";
import { notificar } from "@/components/flic/toast";
import { SegredoCampo } from "@/components/integracoes/segredo-campo";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dataHora } from "@/lib/format";
import type { Integracao, IntegracaoIn, ResultadoIntegracao, SituacaoIntegracao, UsuarioOpcao } from "@/lib/tipos-orquestracao";

import { DetalheWhatsApp } from "./whatsapp-evolution";

const TOM: Record<SituacaoIntegracao, TomEtiqueta> = {
  conectado: "green",
  erro: "amber",
  aguardando_conector: "azul",
  desconectado: "neutra",
};

const CHAVE = ["orquestracao", "integracoes"];

export function IntegracoesTela() {
  const [aberta, setAberta] = useState<Integracao | null>(null);
  const lista = useQuery({ queryKey: CHAVE, queryFn: () => api.get<Integracao[]>("/orquestracao/integracoes") });

  return (
    <>
      <PageHeader titulo="Integrações" descricao="Conexões explícitas, capacidades claras e histórico de falhas." />
      <div className="grid gap-[18px] sm:grid-cols-2 xl:grid-cols-4">
        {lista.isPending
          ? [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[220px] rounded-[10px]" />)
          : (lista.data ?? []).map((c) => (
              <section key={c.tipo} className="card-surface flex flex-col p-[22px]">
                <span className="eyebrow">{c.grupo}</span>
                <h2 className="mt-[15px] mb-2 text-[17px] font-bold">{c.nome}</h2>
                <div>
                  <Etiqueta tom={TOM[c.situacao]}>{c.situacao_rotulo}</Etiqueta>
                </div>
                <p className="my-[17px] text-sm text-muted">{c.descricao}</p>
                {c.ultimo_erro && <p className="mb-3 text-xs text-amber-ink">Último erro: {c.ultimo_erro}</p>}
                <div className="mt-auto">
                  <Button variant="outline" onClick={() => setAberta(c)}>
                    Ver requisitos
                  </Button>
                </div>
              </section>
            ))}
      </div>
      <Fonte
        className="mt-6"
        limite="Nenhuma conta pessoal é acessada e nada é capturado por Google ou Outlook: o teste confere o formato e a conexão fica aguardando o conector oficial. O WhatsApp sai pela Evolution API da organização, só quando alguém clica em enviar. O e-mail usa o servidor SMTP de Configurações › E-mail."
      />
      {aberta?.tipo === "whatsapp" && (
        <DetalheWhatsApp integracao={lista.data?.find((x) => x.tipo === "whatsapp") ?? aberta} onFechar={() => setAberta(null)} />
      )}
      {aberta && aberta.tipo !== "whatsapp" && (
        <DetalheIntegracao
          key={aberta.tipo}
          inicial={lista.data?.find((x) => x.tipo === aberta.tipo) ?? aberta}
          onFechar={() => setAberta(null)}
        />
      )}
    </>
  );
}

function DetalheIntegracao({ inicial, onFechar }: { inicial: Integracao; onFechar: () => void }) {
  const { pode } = useAuth();
  const qc = useQueryClient();
  const editar = pode("orquestracao.integracoes.editar");
  const [i, setI] = useState<Integracao>(inicial);
  const [conta, setConta] = useState(inicial.conta ?? "");
  const [escopos, setEscopos] = useState<string[]>(inicial.escopos);
  const [responsavel, setResponsavel] = useState<number | null>(inicial.responsavel_id);
  const [segredo, setSegredo] = useState("");
  const [revogar, setRevogar] = useState(false);
  const usuarios = useQuery({
    queryKey: ["config", "usuarios", "opcoes"],
    queryFn: () => api.get<UsuarioOpcao[]>("/config/usuarios/opcoes"),
    meta: { silencioso: true },
    enabled: editar,
  });

  const atualizar = (x: Integracao) => {
    setI(x);
    void qc.invalidateQueries({ queryKey: CHAVE });
  };
  const salvar = useMutation({
    mutationFn: () => {
      const corpo: IntegracaoIn = { conta: conta.trim() || null, escopos, responsavel_id: responsavel };
      if (segredo.trim()) corpo.segredo = segredo.trim();
      return api.put<Integracao>(`/orquestracao/integracoes/${i.tipo}`, corpo);
    },
    onSuccess: (x) => {
      setSegredo("");
      atualizar(x);
      notificar.sucesso("Configuração salva. Teste a conexão para confirmar.");
    },
  });
  const testar = useMutation({
    mutationFn: () => api.post<ResultadoIntegracao>(`/orquestracao/integracoes/${i.tipo}/testar`),
    onSuccess: (r) => {
      atualizar(r.integracao);
      if (r.integracao.situacao === "erro") notificar.erro(r.mensagem);
      else notificar.sucesso(r.mensagem);
    },
  });
  const revogacao = useMutation({
    mutationFn: () => api.post<ResultadoIntegracao>(`/orquestracao/integracoes/${i.tipo}/revogar`),
    onSuccess: (r) => {
      atualizar(r.integracao);
      notificar(r.mensagem);
    },
  });

  const placeholderConta = i.tipo === "whatsapp" ? "+55 11 99999-0000" : "agenda@suaempresa.com.br";

  return (
    <Drawer
      aberto
      onFechar={onFechar}
      rotulo={`INTEGRAÇÃO / ${i.grupo}`}
      titulo={i.nome}
      descricao={<Etiqueta tom={TOM[i.situacao]}>{i.situacao_rotulo}</Etiqueta>}
      rodape={
        editar ? (
          <div className="flex flex-wrap gap-2">
            <Button type="submit" form="f-integracao" disabled={salvar.isPending}>
              Salvar
            </Button>
            <Button variant="outline" onClick={() => testar.mutate()} disabled={testar.isPending}>
              {testar.isPending && <Loader2 className="animate-spin" />}
              Testar conexão
            </Button>
            {(i.segredo_definido || i.estado !== "desconectado" || i.situacao === "aguardando_conector") && (
              <Button variant="destructive" onClick={() => setRevogar(true)}>
                Revogar
              </Button>
            )}
          </div>
        ) : undefined
      }
    >
      <div className="rounded-[9px] bg-subtle p-[18px] text-[13px]">
        <h3 className="mb-2 text-sm font-bold">Antes de conectar</h3>
        <ul className="list-disc space-y-1 pl-5">
          {i.requisitos.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
      {i.ultimo_erro && <p className="mt-4 rounded-[7px] bg-amber/10 p-3 text-sm text-amber-ink">Último erro: {i.ultimo_erro}</p>}
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted">
        <dt>Último teste</dt>
        <dd>{i.testado_em ? dataHora(i.testado_em) : "—"}</dd>
        <dt>Conectado em</dt>
        <dd>{i.conectado_em ? dataHora(i.conectado_em) : "—"}</dd>
        <dt>Fluxos dependentes</dt>
        <dd>{i.fluxos_dependentes.length ? i.fluxos_dependentes.join(" · ") : "Nenhum"}</dd>
      </dl>

      {editar ? (
        <form
          id="f-integracao"
          className="mt-2"
          onSubmit={(e) => {
            e.preventDefault();
            salvar.mutate();
          }}
        >
          <CampoDrawer
            rotulo={i.tipo === "whatsapp" ? "Número (WhatsApp Business)" : "Conta da organização"}
            htmlFor="in-conta"
            dica={i.tipo === "email" ? "Em branco: usa o remetente de Configurações › E-mail." : undefined}
          >
            <Input id="in-conta" value={conta} onChange={(e) => setConta(e.target.value)} placeholder={placeholderConta} maxLength={200} />
          </CampoDrawer>
          <CampoDrawer rotulo="Escopos de leitura/escrita">
            <div className="space-y-2">
              {i.escopos_disponiveis.map((e) => (
                <label key={e} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={escopos.includes(e)}
                    onCheckedChange={(v) => setEscopos((x) => (v === true ? [...x, e] : x.filter((y) => y !== e)))}
                  />
                  {e}
                </label>
              ))}
            </div>
          </CampoDrawer>
          <CampoDrawer rotulo="Responsável" htmlFor="in-resp">
            <NativeSelect id="in-resp" value={responsavel ?? ""} onChange={(e) => setResponsavel(e.target.value ? Number(e.target.value) : null)}>
              <option value="">—</option>
              {(usuarios.data ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nome}
                </option>
              ))}
            </NativeSelect>
          </CampoDrawer>
          {i.segredo_rotulo && (
            <div className="mt-[17px]">
              <SegredoCampo
                id="in-segredo"
                label={i.segredo_rotulo}
                atual={{ definido: i.segredo_definido, final: i.segredo_final }}
                valor={segredo}
                onChange={setSegredo}
                remover={false}
                onRemover={() => setRevogar(true)}
                dica={i.segredo_definido ? "Deixe em branco para manter. Para apagar, use Revogar." : "Fica cifrado e não pode ser lido depois."}
              />
            </div>
          )}
          {i.tipo === "email" && (
            <p className="mt-4 text-xs text-muted">
              Servidor, porta e senha do envio ficam em{" "}
              <Link href="/configuracoes/email" className="text-primary underline-offset-2 hover:underline">
                Configurações › E-mail
              </Link>
              .
            </p>
          )}
        </form>
      ) : (
        <p className="mt-4 text-sm text-muted">Seu perfil vê o estado das conexões; configurar, testar e revogar exigem permissão de edição.</p>
      )}

      <ConfirmDialog
        open={revogar}
        onOpenChange={setRevogar}
        titulo={`Revogar ${i.nome}?`}
        descricao="O segredo é apagado e a conexão volta a desconectada. Automações de envio deste canal são pausadas."
        confirmar="Revogar"
        destrutivo
        carregando={revogacao.isPending}
        onConfirm={() => {
          setRevogar(false);
          revogacao.mutate();
        }}
      />
    </Drawer>
  );
}
