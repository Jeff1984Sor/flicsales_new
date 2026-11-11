"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, CircleUserRound, ImageUp, KeyRound, Loader2, PenLine, Trash2 } from "lucide-react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { useState } from "react";

import { Mono } from "@/components/flic/brand";
import { Field } from "@/components/flic/form";
import { PageHeader } from "@/components/flic/page-header";
import { SenhaInput } from "@/components/flic/senha-input";
import { UserAvatar } from "@/components/flic/user-avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { rotaAusente } from "@/components/cadastros/consultas";
import { useFoto } from "@/hooks/use-foto";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AssinaturaUsuario } from "@/lib/tipos-nucleo";
import type { UsuarioMe } from "@/lib/types";
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

type MeComAssinatura = UsuarioMe & AssinaturaUsuario;

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
      <PageHeader titulo="Minha conta" descricao="Sua foto, seus dados de acesso, sua assinatura de e-mail e sua senha." icone={CircleUserRound} semIA />
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

        <TrocarSenha />
      </div>
    </div>
  );
}
