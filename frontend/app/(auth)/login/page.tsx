"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Eye, EyeOff, Loader2, Lock, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Field } from "@/components/flic/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const schema = z.object({
  identificador: z.string().trim().min(1, "Informe seu login"),
  senha: z.string().min(1, "Informe a senha"),
});

function ComIcone({ icone: I, children }: { icone: React.ComponentType<{ className?: string }>; children: React.ReactNode }) {
  return (
    <div className="relative">
      <I className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      {children}
    </div>
  );
}

function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const [ver, setVer] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { identificador: "", senha: "" } });

  const enviar = form.handleSubmit(async (v) => {
    setErro(null);
    try {
      const u = await login(v.identificador, v.senha);
      toast.success(`Bem-vindo(a), ${u.nome.split(" ")[0]}!`);
      const volta = new URLSearchParams(window.location.search).get("volta");
      router.replace(volta && volta.startsWith("/") && !volta.startsWith("//") ? volta : "/");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível entrar.");
    }
  });

  return (
    <form onSubmit={enviar} className="space-y-4">
      <Field label="Login" erro={form.formState.errors.identificador?.message}>
        <ComIcone icone={UserRound}>
          <Input
            {...form.register("identificador")}
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="seu login"
            className="h-11 pl-9"
            autoFocus
          />
        </ComIcone>
      </Field>
      <Field label="Senha" erro={form.formState.errors.senha?.message}>
        <ComIcone icone={Lock}>
          <Input
            {...form.register("senha")}
            type={ver ? "text" : "password"}
            autoComplete="current-password"
            placeholder="••••••••"
            className="h-11 pr-10 pl-9"
          />
          <button
            type="button"
            onClick={() => setVer((x) => !x)}
            className="absolute top-1/2 right-2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:bg-subtle"
            aria-label={ver ? "Ocultar senha" : "Mostrar senha"}
          >
            {ver ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </ComIcone>
      </Field>
      <AnimatePresence>
        {erro && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="rounded-lg border border-danger/25 bg-danger/8 px-3 py-2 text-sm text-danger"
          >
            {erro}
          </motion.p>
        )}
      </AnimatePresence>
      <div className="flex justify-end">
        <Link href="/esqueci-senha" className="text-sm font-medium text-primary hover:underline">
          Esqueci minha senha
        </Link>
      </div>
      <Button
        type="submit"
        disabled={form.formState.isSubmitting}
        className="group h-11 w-full"
      >
        {form.formState.isSubmitting ? <Loader2 className="animate-spin" /> : null}
        Entrar
        <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
      </Button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Entrar</h1>
        <p className="mt-1 text-sm text-muted-foreground">Acesse com o seu login curto (ex.: marina).</p>
      </div>
      <Login />
    </div>
  );
}
