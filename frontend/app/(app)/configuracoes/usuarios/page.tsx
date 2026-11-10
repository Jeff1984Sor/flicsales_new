"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, KeyRound, Mail, MoreHorizontal, Pencil, ShieldCheck, UserCheck, UserPlus, Users, UserX } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/flic/confirm-dialog";
import { SearchInput, Segmented, TableCard, TableSkeleton, Toolbar } from "@/components/flic/data-table";
import { EmptyState } from "@/components/flic/empty-state";
import { Field, SwitchRow } from "@/components/flic/form";
import { FormDialog } from "@/components/flic/form-dialog";
import { SenhaInput } from "@/components/flic/senha-input";
import { Pill, StatusBadge } from "@/components/flic/status-badge";
import { UserAvatar } from "@/components/flic/user-avatar";
import { PerfilAcessoSelect, PerfilBadge, PontoCor, usePerfisAcesso } from "@/components/perfis/comum";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { relativo } from "@/lib/format";
import type { UsuarioOut } from "@/lib/types";
import { cn } from "@/lib/utils";

type FiltroAcesso = "todos" | "com" | "sem";

function mascaraTelefone(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

interface Form {
  nome: string;
  email: string;
  login: string;
  telefone: string;
  perfil_acesso_id: number | null;
  acesso_sistema: boolean;
  senha: string;
}

function UsuarioDialog({ usuario, open, onOpenChange, editar }: { usuario: UsuarioOut | null; open: boolean; onOpenChange: (o: boolean) => void; editar: boolean }) {
  const qc = useQueryClient();
  const inicial = (): Form => ({
    nome: usuario?.nome ?? "",
    email: usuario?.email ?? "",
    login: usuario?.login ?? "",
    telefone: usuario?.telefone ? mascaraTelefone(usuario.telefone) : "",
    perfil_acesso_id: usuario?.perfil_acesso_id ?? null,
    acesso_sistema: usuario?.acesso_sistema ?? true,
    senha: "",
  });
  const [f, setF] = useState<Form>(inicial);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((x) => ({ ...x, [k]: v }));
  const salvar = useMutation({
    mutationFn: () => {
      const corpo = {
        nome: f.nome,
        email: f.email,
        login: f.login || null,
        telefone: f.telefone.replace(/\D/g, "") || null,
        perfil_acesso_id: f.perfil_acesso_id,
        acesso_sistema: f.acesso_sistema,
      };
      return usuario
        ? api.patch(`/config/usuarios/${usuario.id}`, corpo)
        : api.post("/config/usuarios", { ...corpo, senha: f.senha || null });
    },
    onSuccess: () => {
      toast.success(usuario ? "Cadastro atualizado" : "Usuário criado");
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      qc.invalidateQueries({ queryKey: ["perfis"] });
      onOpenChange(false);
    },
  });
  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      titulo={usuario ? (editar ? "Editar usuário" : "Usuário") : "Novo usuário"}
      descricao="Quem entra no sistema e o que cada pessoa pode fazer. Profissionais sem login ficam sem acesso."
      rotuloSalvar={usuario ? "Salvar" : "Criar"}
      salvando={salvar.isPending}
      onSubmit={(e) => {
        e.preventDefault();
        if (!editar) return onOpenChange(false);
        if (!f.perfil_acesso_id) return toast.error("Escolha o perfil de acesso.");
        salvar.mutate();
      }}
    >
      <fieldset disabled={!editar} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome" obrigatorio>
            <Input value={f.nome} onChange={(e) => set("nome", e.target.value)} required minLength={2} />
          </Field>
          <Field label="E-mail" obrigatorio>
            <Input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} required />
          </Field>
          <Field label="Usuário (login)" dica="Opcional. Letras minúsculas, números, ponto, hífen ou sublinhado.">
            <Input value={f.login} onChange={(e) => set("login", e.target.value.toLowerCase())} pattern="[a-z0-9._-]{3,60}" autoCapitalize="none" />
          </Field>
          <Field label="WhatsApp" dica="Usado para receber o código de recuperação de senha.">
            <Input value={f.telefone} onChange={(e) => set("telefone", mascaraTelefone(e.target.value))} inputMode="tel" placeholder="(11) 99999-0000" />
          </Field>
        </div>
        <Field label="Perfil de acesso" obrigatorio>
          <PerfilAcessoSelect value={f.perfil_acesso_id} onChange={(v) => set("perfil_acesso_id", v)} disabled={!editar} />
        </Field>
        <SwitchRow titulo="Pode entrar no sistema" descricao="Desligado = pessoa sem login (aparece como responsável, mas não entra no sistema).">
          <Switch checked={f.acesso_sistema} onCheckedChange={(v) => set("acesso_sistema", v)} />
        </SwitchRow>
        {!usuario && f.acesso_sistema && (
          <Field label="Senha inicial" dica="Deixe em branco para enviar um convite por e-mail.">
            <SenhaInput value={f.senha} onChange={(v) => set("senha", v)} autoComplete="new-password" forca />
          </Field>
        )}
      </fieldset>
    </FormDialog>
  );
}

function DefinirSenhaDialog({ usuario, onClose }: { usuario: UsuarioOut | null; onClose: () => void }) {
  const [senha, setSenha] = useState("");
  const definir = useMutation({
    mutationFn: () => api.post(`/config/usuarios/${usuario!.id}/definir-senha`, { senha }),
    onSuccess: () => {
      toast.success(`Senha de ${usuario!.nome} definida`, { description: "As sessões abertas dessa pessoa foram encerradas." });
      setSenha("");
      onClose();
    },
  });
  return (
    <FormDialog
      open={!!usuario}
      onOpenChange={(o) => {
        if (!o) {
          setSenha("");
          onClose();
        }
      }}
      titulo={`Definir senha de ${usuario?.nome ?? ""}`}
      descricao="Combine a senha com a pessoa por um canal seguro. Ela pode trocá-la depois em Minha conta."
      rotuloSalvar="Definir senha"
      salvando={definir.isPending}
      onSubmit={(e) => {
        e.preventDefault();
        if (senha.length >= 8) definir.mutate();
        else toast.error("Mínimo de 8 caracteres.");
      }}
    >
      <Field label="Nova senha" htmlFor="nova-senha-usuario">
        <SenhaInput id="nova-senha-usuario" value={senha} onChange={setSenha} autoComplete="new-password" forca autoFocus />
      </Field>
    </FormDialog>
  );
}

function Kpi({ rotulo, valor, tom }: { rotulo: string; valor: number; tom?: string }) {
  return (
    <div className="card-surface px-4 py-3">
      <p className="text-xs text-muted-foreground">{rotulo}</p>
      <p className={cn("mt-0.5 text-2xl font-semibold tabular-nums", tom)}>{valor}</p>
    </div>
  );
}

export default function UsuariosPage() {
  const qc = useQueryClient();
  const { usuario: eu, pode } = useAuth();
  const editar = pode("nucleo.administracao.editar");
  const [q, setQ] = useState("");
  const [perfilId, setPerfilId] = useState<string>("");
  const [acesso, setAcesso] = useState<FiltroAcesso>("todos");
  const [inativos, setInativos] = useState(false);
  const [dialogo, setDialogo] = useState<{ u: UsuarioOut | null } | null>(null);
  const [senhaDe, setSenhaDe] = useState<UsuarioOut | null>(null);
  const [desativar, setDesativar] = useState<UsuarioOut | null>(null);
  const lista = useQuery({ queryKey: ["usuarios"], queryFn: () => api.get<UsuarioOut[]>("/config/usuarios"), refetchInterval: 60_000 });
  const perfis = usePerfisAcesso(pode("nucleo.administracao.ver"));

  const patch = useMutation({
    mutationFn: ({ id, ...body }: { id: number; ativo?: boolean }) => api.patch(`/config/usuarios/${id}`, body),
    onSuccess: () => {
      toast.success("Cadastro atualizado");
      setDesativar(null);
      qc.invalidateQueries({ queryKey: ["usuarios"] });
    },
  });
  const reset = useMutation({
    mutationFn: (u: UsuarioOut) => api.post(`/config/usuarios/${u.id}/redefinir-senha`),
    onSuccess: (_r, u) => toast.success(`Link enviado para ${u.email}`),
  });

  const todos = lista.data ?? [];
  const termo = q.trim().toLowerCase();
  const usuarios = todos.filter(
    (u) =>
      (inativos || u.ativo) &&
      (!perfilId || (u.acesso_sistema && String(u.perfil_acesso_id) === perfilId)) &&
      (acesso === "todos" || (acesso === "com" ? u.acesso_sistema : !u.acesso_sistema)) &&
      (!termo || u.nome.toLowerCase().includes(termo) || u.email.toLowerCase().includes(termo) || (u.login ?? "").includes(termo)),
  );
  const ativos = todos.filter((u) => u.ativo);
  const online = ativos.filter((u) => u.online);
  const filtrando = !!(termo || perfilId || acesso !== "todos");

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Usuários</h2>
        <p className="text-sm text-muted-foreground">Equipe da organização: quem entra no sistema e com qual perfil (Gestor, Comercial, Financeiro, Somente leitura).</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi rotulo="Ativos" valor={ativos.length} />
        <Kpi rotulo="Com acesso ao sistema" valor={ativos.filter((u) => u.acesso_sistema).length} tom="text-info-ink" />
        <Kpi rotulo="Sem acesso (sem login)" valor={ativos.filter((u) => !u.acesso_sistema).length} />
        <Kpi rotulo="Online agora" valor={online.length} tom="text-success-ink" />
      </div>

      <TableCard>
        <Toolbar>
          <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <SearchInput value={q} onChange={setQ} placeholder="Nome, e-mail ou login" />
            <Segmented<FiltroAcesso>
              value={acesso}
              onChange={setAcesso}
              opcoes={[
                { value: "todos", label: "Todos" },
                { value: "com", label: "Com acesso" },
                { value: "sem", label: "Sem acesso" },
              ]}
            />
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <input type="checkbox" checked={inativos} onChange={(e) => setInativos(e.target.checked)} className="accent-[var(--brand)]" /> Mostrar inativos
            </label>
          </div>
          {editar && (
            <Button onClick={() => setDialogo({ u: null })}>
              <UserPlus /> Novo usuário
            </Button>
          )}
        </Toolbar>
        {lista.isPending ? (
          <TableSkeleton colunas={6} />
        ) : usuarios.length === 0 ? (
          <EmptyState
            icone={Users}
            titulo={filtrando ? "Ninguém com esses filtros" : "Nenhum usuário cadastrado"}
            descricao={filtrando ? "Limpe a busca ou troque o filtro de acesso." : "Cadastre a equipe da organização."}
            acao={
              filtrando ? (
                <Button
                  variant="outline"
                  onClick={() => {
                    setQ("");
                    setPerfilId("");
                    setAcesso("todos");
                  }}
                >
                  Limpar filtros
                </Button>
              ) : (
                editar && (
                  <Button onClick={() => setDialogo({ u: null })}>
                    <UserPlus /> Novo usuário
                  </Button>
                )
              )
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b bg-subtle/40 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Nome</th>
                  <th className="hidden px-3 py-2.5 font-medium md:table-cell">Login</th>
                  <th className="hidden px-3 py-2.5 font-medium lg:table-cell">E-mail</th>
                  <th className="px-3 py-2.5 font-medium">Perfil de acesso</th>
                  <th className="hidden px-3 py-2.5 font-medium md:table-cell">Último acesso</th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                  <th className="w-12 px-3 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {usuarios.map((u) => (
                  <tr
                    key={u.id}
                    tabIndex={0}
                    onClick={() => setDialogo({ u })}
                    onKeyDown={(e) => e.key === "Enter" && setDialogo({ u })}
                    className={cn("cursor-pointer transition-colors hover:bg-subtle/40 focus-visible:bg-subtle/40 focus-visible:outline-none", !u.ativo && "opacity-60")}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <UserAvatar nome={u.nome} fotoUrl={u.foto_url} className="size-9" textoClassName="text-xs" online={u.online} inativo={!u.ativo} />
                        <div className="min-w-0">
                          <p className="flex items-center gap-1.5 font-medium">
                            <span className="truncate">{u.nome}</span>
                            {u.id === eu?.id && <Pill tom="brand">você</Pill>}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">{u.telefone ? mascaraTelefone(u.telefone) : <span className="lg:hidden">{u.email}</span>}</p>
                        </div>
                      </div>
                    </td>
                    <td className="hidden px-3 py-3 md:table-cell">{u.login ? <span className="font-mono text-xs">{u.login}</span> : <span className="text-xs text-muted-foreground">—</span>}</td>
                    <td className="hidden max-w-56 truncate px-3 py-3 text-muted-foreground lg:table-cell">{u.email}</td>
                    <td className="px-3 py-3">
                      {!u.acesso_sistema ? <Pill tom="neutral">Sem acesso</Pill> : <PerfilBadge nome={u.perfil_acesso_nome} cor={u.perfil_acesso_cor} />}
                    </td>
                    <td className="hidden px-3 py-3 text-muted-foreground md:table-cell">
                      {!u.acesso_sistema ? "—" : u.online ? <span className="text-success-ink">agora</span> : relativo(u.ultimo_acesso)}
                    </td>
                    <td className="px-3 py-3">
                      {!u.ativo ? (
                        <StatusBadge status="descartado" label="Inativo" />
                      ) : u.acesso_sistema && u.convite_pendente ? (
                        <StatusBadge tom="warning" label="Convite pendente" />
                      ) : (
                        <StatusBadge status="ativo" label="Ativo" />
                      )}
                    </td>
                    <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label={`Ações de ${u.nome}`} />}>
                          <MoreHorizontal />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56">
                          <DropdownMenuGroup>
                            <DropdownMenuLabel>{u.nome}</DropdownMenuLabel>
                          </DropdownMenuGroup>
                          <DropdownMenuItem onClick={() => setDialogo({ u })}>
                            <Pencil /> {editar ? "Editar cadastro" : "Ver cadastro"}
                          </DropdownMenuItem>
                          {u.id !== eu?.id && editar && (
                            <>
                              {u.acesso_sistema && (
                                <>
                                  <DropdownMenuItem onClick={() => setSenhaDe(u)}>
                                    <KeyRound /> Definir senha
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => reset.mutate(u)}>
                                    <Mail /> {u.convite_pendente ? "Reenviar convite" : "Enviar link de redefinição"}
                                  </DropdownMenuItem>
                                </>
                              )}
                              <DropdownMenuSeparator />
                              {u.ativo ? (
                                <DropdownMenuItem variant="destructive" onClick={() => setDesativar(u)}>
                                  <UserX /> Desativar
                                </DropdownMenuItem>
                              ) : (
                                <DropdownMenuItem onClick={() => patch.mutate({ id: u.id, ativo: true })}>
                                  <UserCheck /> Reativar
                                </DropdownMenuItem>
                              )}
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </TableCard>

      {(perfis.data?.length ?? 0) > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {perfis.data?.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPerfilId(perfilId === String(p.id) ? "" : String(p.id))}
              className={cn("group rounded-2xl border bg-card p-4 text-left transition-colors hover:border-brand/40", perfilId === String(p.id) && "border-brand/60 bg-brand/5")}
              title="Filtrar a lista por este perfil"
            >
              <p className="flex items-center gap-2 text-sm font-semibold">
                <PontoCor cor={p.cor} />
                <span className="truncate">{p.nome}</span>
                {p.administrador && <ShieldCheck className="size-3.5 text-info-ink" aria-label="Acesso total" />}
                <span className="ml-auto text-xs font-normal text-muted-foreground tabular-nums">{p.qtd_usuarios}</span>
              </p>
              {p.descricao && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{p.descricao}</p>}
            </button>
          ))}
          {pode("nucleo.administracao.ver") && (
            <Link href="/configuracoes/perfis" className="flex items-center gap-2 rounded-2xl border border-dashed bg-card p-4 text-sm font-medium text-info-ink transition-colors hover:border-brand/40">
              <ShieldCheck className="size-4" /> Gerenciar perfis de acesso <ChevronRight className="ml-auto size-4" />
            </Link>
          )}
        </div>
      )}

      {dialogo && <UsuarioDialog key={dialogo.u?.id ?? "novo"} open onOpenChange={(o) => !o && setDialogo(null)} usuario={dialogo.u} editar={editar} />}
      <DefinirSenhaDialog usuario={senhaDe} onClose={() => setSenhaDe(null)} />
      <ConfirmDialog
        open={!!desativar}
        onOpenChange={(o) => !o && setDesativar(null)}
        titulo={`Desativar ${desativar?.nome ?? ""}?`}
        descricao="O acesso é bloqueado na hora, as sessões abertas são encerradas e a pessoa sai das listas. O histórico e a auditoria são mantidos."
        confirmar="Desativar"
        destrutivo
        carregando={patch.isPending}
        onConfirm={() => desativar && patch.mutate({ id: desativar.id, ativo: false })}
      />
    </div>
  );
}
