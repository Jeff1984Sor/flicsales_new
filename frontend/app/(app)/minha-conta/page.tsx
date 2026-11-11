"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CircleUserRound, ImageUp, KeyRound, Loader2, Mail, PenLine, PlugZap, Trash2 } from "lucide-react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { useState } from "react";

import { Mono } from "@/components/flic/brand";
import { ConfirmDialog } from "@/components/flic/confirm-dialog";
import { Field } from "@/components/flic/form";
import { PageHeader } from "@/components/flic/page-header";
import { SenhaInput } from "@/components/flic/senha-input";
import { UserAvatar } from "@/components/flic/user-avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { rotaAusente } from "@/components/cadastros/consultas";
import { useFoto } from "@/hooks/use-foto";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AssinaturaUsuario } from "@/lib/tipos-nucleo";
import type { ConfigEmailUsuarioIn, ConfigEmailUsuarioOut, TesteConexao, UsuarioMe } from "@/lib/types";
import { cn } from "@/lib/utils";

function TrocarSenha() {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirma, setConfirma] = useState("");
  const diferente = confirma.length > 0 && confirma !== nova;
  const trocar = useMutation({
    mutationFn: () => api.post("/auth/trocar-senha", { senha_atual: atual, nova_senha: nova }),
    onSuccess: () => {
      toast.success("Senha alterada", { description: "Os outros aparelhos conectados foram desconectados." });
      setAtual("");
      setNova("");
      setConfirma("");
    },
  });
  return (
    <form
      className="card-surface space-y-4 p-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (!diferente && nova) trocar.mutate();
      }}
    >
      <h3 className="flex items-center gap-2 font-semibold">
        <KeyRound className="size-4 text-info-ink" /> Trocar senha
      </h3>
      <Field label="Senha atual">
        <SenhaInput value={atual} onChange={setAtual} autoComplete="current-password" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nova senha">
          <SenhaInput value={nova} onChange={setNova} autoComplete="new-password" forca />
        </Field>
        <Field label="Confirme a nova senha" erro={diferente ? "As senhas não conferem" : undefined}>
          <SenhaInput value={confirma} onChange={setConfirma} autoComplete="new-password" />
        </Field>
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={trocar.isPending || !atual || !nova || diferente}>
          {trocar.isPending && <Loader2 className="animate-spin" />} Salvar nova senha
        </Button>
      </div>
    </form>
  );
}

const CHAVE_EMAIL = ["auth", "me", "email"] as const;
const MSG_EMAIL_INDISPONIVEL = "E-mail de envio ainda indisponível no servidor. Tente mais tarde.";
const erroEmail = (e: Error) => toast.error(rotaAusente(e) ? MSG_EMAIL_INDISPONIVEL : e.message);

/** "E-mail de envio" (opcional): SMTP próprio do usuário. Sem ele, os e-mails saem pela organização com resposta para você. */
function EmailEnvio() {
  const consulta = useQuery({
    queryKey: CHAVE_EMAIL,
    queryFn: () => api.get<ConfigEmailUsuarioOut>("/auth/me/email"),
    retry: false,
    meta: { silencioso: true },
  });
  return (
    <div className="card-surface space-y-4 p-5">
      <div>
        <h3 className="flex items-center gap-2 font-semibold">
          <Mail className="size-4 text-info-ink" /> E-mail de envio
        </h3>
        <p className="mt-1 text-xs text-muted">Opcional. Sem configurar, seus e-mails saem pelo e-mail da organização com resposta para você.</p>
      </div>
      {consulta.isPending ? (
        <p className="text-sm text-muted">Carregando…</p>
      ) : consulta.isError ? (
        <p className="text-sm text-muted">{rotaAusente(consulta.error) ? MSG_EMAIL_INDISPONIVEL : "Não foi possível carregar o e-mail de envio."}</p>
      ) : (
        <FormEmailEnvio key={String(consulta.dataUpdatedAt)} cfg={consulta.data} />
      )}
    </div>
  );
}

function FormEmailEnvio({ cfg }: { cfg: ConfigEmailUsuarioOut }) {
  const qc = useQueryClient();
  const { usuario } = useAuth();
  const [f, setF] = useState({
    remetente_nome: cfg.remetente_nome ?? usuario?.nome ?? "",
    remetente_email: cfg.remetente_email ?? usuario?.email ?? "",
    smtp_host: cfg.smtp_host ?? "",
    smtp_porta: String(cfg.smtp_porta ?? 587),
    smtp_usuario: cfg.smtp_usuario ?? "",
    smtp_senha: "",
    ativo: cfg.configurado ? cfg.ativo : true,
  });
  const [remover, setRemover] = useState(false);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const atualizar = (novo?: ConfigEmailUsuarioOut) => {
    if (novo) qc.setQueryData(CHAVE_EMAIL, novo);
    else qc.invalidateQueries({ queryKey: CHAVE_EMAIL });
    qc.invalidateQueries({ queryKey: ["auth", "me", "envio"] });
  };

  const corpo = (): ConfigEmailUsuarioIn => ({
    remetente_nome: f.remetente_nome.trim(),
    remetente_email: f.remetente_email.trim(),
    smtp_host: f.smtp_host.trim(),
    smtp_porta: Number(f.smtp_porta) || 587,
    smtp_usuario: f.smtp_usuario.trim() || null,
    ativo: f.ativo,
    ...(f.smtp_senha ? { smtp_senha: f.smtp_senha } : {}),
  });
  const incompleto = !f.remetente_nome.trim() || !f.remetente_email.trim() || !f.smtp_host.trim();
  const mudou =
    f.smtp_senha !== "" ||
    f.remetente_nome !== (cfg.remetente_nome ?? "") ||
    f.remetente_email !== (cfg.remetente_email ?? "") ||
    f.smtp_host !== (cfg.smtp_host ?? "") ||
    f.smtp_porta !== String(cfg.smtp_porta ?? 587) ||
    f.smtp_usuario !== (cfg.smtp_usuario ?? "") ||
    f.ativo !== cfg.ativo;

  const salvar = useMutation({
    mutationFn: () => api.put<ConfigEmailUsuarioOut>("/auth/me/email", corpo()),
    meta: { silencioso: true },
    onSuccess: (novo) => {
      atualizar(novo);
      toast.success("E-mail de envio salvo");
    },
    onError: erroEmail,
  });
  const testar = useMutation({
    // sem mudanças testa o que está salvo; com mudanças testa o formulário antes de salvar (senha vazia = a salva)
    mutationFn: () => api.post<TesteConexao>("/auth/me/email/testar", cfg.configurado && !mudou ? undefined : corpo()),
    meta: { silencioso: true },
    onSuccess: (r) => (r.ok ? toast.success(r.mensagem) : toast.error(r.mensagem)),
    onError: erroEmail,
  });
  const excluir = useMutation({
    mutationFn: () => api.del("/auth/me/email"),
    meta: { silencioso: true },
    onSuccess: () => {
      setRemover(false);
      atualizar({ configurado: false, ativo: false, remetente_nome: null, remetente_email: null, smtp_host: null, smtp_porta: 587, smtp_usuario: null, senha_final: null });
      toast.success("Removido. Seus e-mails voltam a sair pela organização.");
    },
    onError: erroEmail,
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (incompleto) {
          toast.error("Preencha nome, e-mail do remetente e servidor SMTP.");
          return;
        }
        salvar.mutate();
      }}
    >
      {cfg.configurado && (
        <div className="flex items-center justify-between gap-4 rounded-lg border border-line p-3">
          <div>
            <p className="text-sm font-medium">Usar este e-mail nos meus envios</p>
            <p className="text-xs text-muted">{f.ativo ? "Ligado: seus e-mails saem por este servidor." : "Desligado: seus e-mails saem pela organização."}</p>
          </div>
          <Switch checked={f.ativo} onCheckedChange={(v) => set("ativo", v)} />
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nome do remetente" obrigatorio>
          <Input value={f.remetente_nome} onChange={(e) => set("remetente_nome", e.target.value)} maxLength={150} />
        </Field>
        <Field label="E-mail do remetente" obrigatorio>
          <Input type="email" value={f.remetente_email} onChange={(e) => set("remetente_email", e.target.value)} maxLength={200} />
        </Field>
        <Field label="Servidor SMTP" obrigatorio dica="Ex.: smtp.seudominio.com.br">
          <Input value={f.smtp_host} onChange={(e) => set("smtp_host", e.target.value)} placeholder="smtp.seudominio.com.br" maxLength={200} />
        </Field>
        <Field label="Porta" dica="465 = SSL direto; 587 = STARTTLS.">
          <Input type="number" className="font-mono" value={f.smtp_porta} onChange={(e) => set("smtp_porta", e.target.value)} />
        </Field>
        <Field label="Usuário">
          <Input value={f.smtp_usuario} onChange={(e) => set("smtp_usuario", e.target.value)} autoComplete="off" maxLength={200} />
        </Field>
        <Field
          label="Senha"
          dica={
            cfg.senha_final ? (
              <>
                Configurado <Mono>{cfg.senha_final}</Mono>. Preencha só para trocar.
              </>
            ) : (
              "Fica cifrada e não é exibida depois de salva."
            )
          }
        >
          <SenhaInput value={f.smtp_senha} onChange={(v) => set("smtp_senha", v)} autoComplete="new-password" />
        </Field>
      </div>
      <div className="flex flex-wrap justify-end gap-2">
        {cfg.configurado && (
          <Button type="button" variant="ghost" className="text-danger-ink" onClick={() => setRemover(true)} disabled={excluir.isPending}>
            <Trash2 /> Remover
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          disabled={testar.isPending || incompleto}
          onClick={() => testar.mutate()}
          title="Faz login no servidor SMTP. Nada é enviado."
        >
          {testar.isPending ? <Loader2 className="animate-spin" /> : <PlugZap />} Testar conexão
        </Button>
        <Button type="submit" disabled={salvar.isPending || (cfg.configurado && !mudou)}>
          {salvar.isPending && <Loader2 className="animate-spin" />} Salvar
        </Button>
      </div>
      <ConfirmDialog
        open={remover}
        onOpenChange={setRemover}
        titulo="Remover o e-mail de envio?"
        descricao="Seus e-mails voltam a sair pelo e-mail da organização, com resposta para você."
        confirmar="Remover"
        destrutivo
        carregando={excluir.isPending}
        onConfirm={() => excluir.mutate()}
      />
    </form>
  );
}

type MeComAssinatura =UsuarioMe & AssinaturaUsuario;

const MSG_INDISPONIVEL = "Assinatura de e-mail ainda indisponível no servidor. Tente mais tarde.";

function erroAssinatura(e: unknown) {
  toast.error(rotaAusente(e) ? MSG_INDISPONIVEL : e instanceof Error ? e.message : "Não foi possível salvar.");
}

/** "Assinatura de e-mail": texto + imagem (PNG/JPG até 1 MB) + prévia. Sem assinatura, vale a padrão da Identidade. */
function AssinaturaEmail({ usuario, onAtualizado }: { usuario: MeComAssinatura; onAtualizado: (u: UsuarioMe) => void }) {
  const salvo = usuario.assinatura_email ?? "";
  const [texto, setTexto] = useState(salvo);
  // acompanha a assinatura salva quando ela muda no servidor (sem sobrescrever o que está sendo digitado)
  const [base, setBase] = useState(salvo);
  if (base !== salvo) {
    setBase(salvo);
    setTexto(salvo);
  }
  const temImagem = !!(usuario.assinatura_imagem_url || usuario.assinatura_imagem);
  const urlImagem = usuario.assinatura_imagem_url ?? (usuario.assinatura_imagem ? `/auth/me/assinatura-imagem?v=${encodeURIComponent(usuario.assinatura_imagem)}` : null);
  const imagem = useFoto(urlImagem);

  const salvar = useMutation({
    mutationFn: () => api.patch<MeComAssinatura>("/auth/me", { assinatura_email: texto.trim() ? texto : null }),
    meta: { silencioso: true },
    onSuccess: (u) => {
      if (!("assinatura_email" in u)) return toast.error(MSG_INDISPONIVEL);
      onAtualizado(u);
      toast.success("Assinatura salva");
    },
    onError: erroAssinatura,
  });
  const enviar = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("arquivo", f);
      return api.post<MeComAssinatura>("/auth/me/assinatura-imagem", fd);
    },
    meta: { silencioso: true },
    onSuccess: (u) => {
      onAtualizado(u);
      toast.success("Imagem da assinatura atualizada");
    },
    onError: erroAssinatura,
  });
  const remover = useMutation({
    mutationFn: () => api.del<MeComAssinatura>("/auth/me/assinatura-imagem"),
    meta: { silencioso: true },
    onSuccess: (u) => {
      onAtualizado(u);
      toast.success("Imagem da assinatura removida");
    },
    onError: erroAssinatura,
  });
  const dz = useDropzone({
    multiple: false,
    noClick: true,
    noKeyboard: true,
    accept: { "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"] },
    maxSize: 1024 * 1024,
    onDrop: (f) => f[0] && enviar.mutate(f[0]),
    onDropRejected: () => toast.error("Use PNG ou JPG de até 1 MB."),
  });
  const mudou = texto !== salvo;
  const vazia = !texto.trim() && !temImagem;

  return (
    <form
      className="card-surface space-y-4 p-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (mudou) salvar.mutate();
      }}
    >
      <div>
        <h3 className="flex items-center gap-2 font-semibold">
          <PenLine className="size-4 text-info-ink" /> Assinatura de e-mail
        </h3>
        <p className="mt-1 text-xs text-muted">
          Vai no fim dos e-mails que você envia (comunicações, cobranças, propostas). Sem a sua, vale a assinatura padrão da organização.
        </p>
      </div>
      <Field label="Texto da assinatura">
        <Textarea rows={4} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={"Atenciosamente,\nSeu nome · Cargo\n(11) 0000-0000"} />
      </Field>
      <div {...dz.getRootProps()} className="flex flex-wrap items-center gap-2">
        <input {...dz.getInputProps()} />
        <Button type="button" variant="outline" onClick={dz.open} disabled={enviar.isPending}>
          {enviar.isPending ? <Loader2 className="animate-spin" /> : <ImageUp />} {temImagem ? "Trocar imagem" : "Enviar imagem"}
        </Button>
        {temImagem && (
          <Button type="button" variant="ghost" className="text-danger-ink" onClick={() => remover.mutate()} disabled={remover.isPending}>
            <Trash2 /> Remover imagem
          </Button>
        )}
        <span className="text-xs text-muted">PNG ou JPG até 1 MB (logo, selo ou assinatura escaneada).</span>
      </div>
      <div>
        <span className="eyebrow">PRÉVIA</span>
        <div className="mt-2 rounded-[10px] border border-line bg-subtle/40 p-4 text-sm">
          {vazia ? (
            <p className="text-muted">Sem assinatura própria: seus e-mails usam a assinatura padrão da organização.</p>
          ) : (
            <>
              <p className="text-muted">—</p>
              {texto.trim() && <p className="whitespace-pre-line">{texto}</p>}
              {temImagem &&
                (imagem ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={imagem} alt="Imagem da assinatura" className="mt-3 max-h-24 max-w-[260px] object-contain" />
                ) : (
                  <p className="mt-3 text-xs text-muted">Carregando imagem…</p>
                ))}
            </>
          )}
        </div>
      </div>
      <div className="flex justify-end gap-2">
        {mudou && (
          <Button type="button" variant="outline" onClick={() => setTexto(salvo)}>
            Desfazer
          </Button>
        )}
        <Button type="submit" disabled={salvar.isPending || !mudou}>
          {salvar.isPending && <Loader2 className="animate-spin" />} Salvar assinatura
        </Button>
      </div>
    </form>
  );
}

export default function MinhaContaPage() {
  const { usuario } = useAuth();
  const qc = useQueryClient();
  const atualizar = (u: UsuarioMe) => {
    qc.setQueryData(["me"], u);
    qc.invalidateQueries({ queryKey: ["usuarios"] });
  };
  const enviar = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("arquivo", f);
      return api.post<UsuarioMe>("/auth/me/foto", fd);
    },
    onSuccess: (u) => {
      atualizar(u);
      toast.success("Foto atualizada");
    },
  });
  const remover = useMutation({
    mutationFn: () => api.del<UsuarioMe>("/auth/me/foto"),
    onSuccess: (u) => {
      atualizar(u);
      toast.success("Foto removida");
    },
  });
  const dz = useDropzone({
    multiple: false,
    accept: { "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"], "image/webp": [".webp"] },
    maxSize: 4 * 1024 * 1024,
    onDrop: (f) => f[0] && enviar.mutate(f[0]),
    onDropRejected: () => toast.error("Use PNG, JPG ou WEBP de até 4 MB."),
  });
  if (!usuario) return null;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader titulo="Minha conta" descricao="Sua foto, seus dados de acesso, seu e-mail de envio, sua assinatura e sua senha." icone={CircleUserRound} semIA />
      <div className="space-y-5">
        <div className="card-surface relative overflow-hidden">
          <div className="bg-primary h-24" />
          <div className="flex flex-col gap-5 px-5 pb-5 sm:flex-row sm:items-end">
            <div
              {...dz.getRootProps()}
              className={cn(
                "group relative -mt-12 size-28 shrink-0 cursor-pointer rounded-full ring-4 ring-card transition",
                dz.isDragActive && "ring-brand",
              )}
              title="Arraste uma foto ou clique para escolher"
            >
              <input {...dz.getInputProps()} />
              <UserAvatar nome={usuario.nome} fotoUrl={usuario.foto_url} className="size-28" textoClassName="text-3xl" />
              <div className="absolute inset-0 grid place-items-center rounded-full bg-ink/55 text-white opacity-0 transition group-hover:opacity-100">
                {enviar.isPending ? <Loader2 className="size-6 animate-spin" /> : <Camera className="size-6" />}
              </div>
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-semibold">{usuario.nome}</h2>
              <p className="text-sm text-muted-foreground">Seu perfil: {usuario.perfil_acesso_nome ?? "Sem perfil"}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={dz.open} disabled={enviar.isPending}>
                <Camera /> {usuario.foto_url ? "Trocar foto" : "Enviar foto"}
              </Button>
              {usuario.foto_url && (
                <Button variant="ghost" className="text-danger-ink" onClick={() => remover.mutate()} disabled={remover.isPending}>
                  <Trash2 /> Remover
                </Button>
              )}
            </div>
          </div>
          <p className="border-t px-5 py-3 text-xs text-muted-foreground">PNG, JPG ou WEBP até 4 MB. A foto é recortada em círculo automaticamente.</p>
        </div>

        <div className="card-surface grid gap-4 p-5 sm:grid-cols-3">
          <Field label="Nome">
            <Input value={usuario.nome} readOnly className="bg-subtle/50 text-muted-foreground" />
          </Field>
          <Field label="E-mail" dica="Alterado por um administrador.">
            <Input value={usuario.email} readOnly className="bg-subtle/50 text-muted-foreground" />
          </Field>
          <Field label="Usuário (login)" dica="Alterado por um administrador.">
            <div className="flex h-8 items-center rounded-lg border bg-subtle/50 px-2.5 text-sm">
              {usuario.login ? <Mono>{usuario.login}</Mono> : <span className="text-muted-foreground">—</span>}
            </div>
          </Field>
        </div>

        <AssinaturaEmail usuario={usuario} onAtualizado={atualizar} />

        <EmailEnvio />

        <TrocarSenha />
      </div>
    </div>
  );
}
