"use client";

import { ArrowLeft, Loader2, MailCheck, MessageCircle, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/flic/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Canal = "email" | "whatsapp";

function forca(s: string) {
  let p = 0;
  if (s.length >= 8) p++;
  if (s.length >= 12) p++;
  if (/[A-Z]/.test(s) && /[a-z]/.test(s)) p++;
  if (/\d/.test(s)) p++;
  return Math.min(4, p);
}

export default function EsqueciSenhaPage() {
  const [canal, setCanal] = useState<Canal>("email");
  const [identificador, setIdentificador] = useState("");
  const [etapa, setEtapa] = useState<"pedido" | "enviado" | "codigo" | "pronto">("pedido");
  const [codigo, setCodigo] = useState("");
  const [senha, setSenha] = useState("");
  const [confirma, setConfirma] = useState("");
  const [carregando, setCarregando] = useState(false);
  const f = forca(senha);

  async function executar(fn: () => Promise<unknown>, depois: () => void) {
    setCarregando(true);
    try {
      await fn();
      depois();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erro ao enviar");
    } finally {
      setCarregando(false);
    }
  }

  const pedir = (e: React.FormEvent) => {
    e.preventDefault();
    void executar(
      () => api.post(canal === "email" ? "/auth/forgot" : "/auth/forgot-codigo", { identificador }, { auth: false }),
      () => setEtapa(canal === "email" ? "enviado" : "codigo"),
    );
  };

  const redefinir = (e: React.FormEvent) => {
    e.preventDefault();
    if (senha !== confirma) return toast.error("As senhas não conferem.");
    void executar(
      () => api.post("/auth/reset-codigo", { identificador, codigo, senha }, { auth: false }),
      () => setEtapa("pronto"),
    );
  };

  if (etapa === "enviado")
    return (
      <div className="space-y-4 text-center">
        <div className="mx-auto grid size-14 place-items-center rounded-2xl bg-success/10">
          <MailCheck className="size-7 text-success" />
        </div>
        <p className="text-sm text-muted-foreground">
          Se a conta existir, você receberá um e-mail com o link para criar uma nova senha. O link vale por 2 horas e só pode ser usado uma vez.
        </p>
        <Button variant="outline" className="w-full" render={<Link href="/login" />}>
          <ArrowLeft /> Voltar ao login
        </Button>
      </div>
    );

  if (etapa === "pronto")
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-2xl font-semibold">Senha definida!</h1>
        <p className="text-sm text-muted-foreground">Agora é só entrar com a nova senha.</p>
        <Button className="h-11 w-full" render={<Link href="/login" />}>
          Ir para o login
        </Button>
      </div>
    );

  if (etapa === "codigo")
    return (
      <form onSubmit={redefinir} className="space-y-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Digite o código</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Se a conta tiver WhatsApp cadastrado, enviamos um código de 6 dígitos (vale por 10 minutos).
          </p>
        </div>
        <Field label="Código">
          <Input
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            className="h-11 text-center font-mono text-lg tracking-[0.4em]"
            required
            minLength={6}
            autoFocus
          />
        </Field>
        <Field label="Nova senha">
          <Input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} className="h-11" required minLength={8} autoComplete="new-password" />
          <div className="mt-1 grid grid-cols-4 gap-1">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className={cn("h-1 rounded-full bg-subtle transition-colors", i < f && (f <= 1 ? "bg-danger" : f === 2 ? "bg-warning" : "bg-success"))} />
            ))}
          </div>
        </Field>
        <Field label="Confirme a senha" erro={confirma && confirma !== senha ? "As senhas não conferem" : undefined}>
          <Input type="password" value={confirma} onChange={(e) => setConfirma(e.target.value)} className="h-11" required autoComplete="new-password" />
        </Field>
        <Button type="submit" disabled={carregando || codigo.length < 6} className="h-11 w-full">
          {carregando && <Loader2 className="animate-spin" />}
          Salvar senha
        </Button>
        <Button type="button" variant="ghost" className="w-full" onClick={() => setEtapa("pedido")}>
          <ArrowLeft /> Pedir outro código
        </Button>
      </form>
    );

  return (
    <form onSubmit={pedir} className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Recuperar acesso</h1>
        <p className="mt-1 text-sm text-muted-foreground">Informe seu login e escolha como receber as instruções.</p>
      </div>
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-subtle p-1 text-sm font-medium" role="tablist">
        {(
          [
            ["email", "Por e-mail", MailCheck],
            ["whatsapp", "Código no WhatsApp", MessageCircle],
          ] as const
        ).map(([id, rotulo, Icone]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={canal === id}
            onClick={() => setCanal(id)}
            className={cn("flex items-center justify-center gap-1.5 rounded-md px-2 py-2 text-muted-foreground transition", canal === id && "bg-card text-foreground shadow-sm")}
          >
            <Icone className="size-4" /> {rotulo}
          </button>
        ))}
      </div>
      <div className="relative">
        <UserRound className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={identificador}
          onChange={(e) => setIdentificador(e.target.value)}
          type="text"
          required
          autoCapitalize="none"
          spellCheck={false}
          placeholder="seu login"
          className="h-11 pl-9"
          autoFocus
        />
      </div>
      <Button type="submit" disabled={carregando} className="h-11 w-full">
        {carregando && <Loader2 className="animate-spin" />}
        {canal === "email" ? "Enviar link" : "Enviar código"}
      </Button>
      <Button type="button" variant="ghost" className="w-full" render={<Link href="/login" />}>
        <ArrowLeft /> Voltar
      </Button>
    </form>
  );
}
