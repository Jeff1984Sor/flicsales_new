"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Mail, Save, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmailChips } from "@/components/flic/email-chips";
import { Field } from "@/components/flic/form";
import { SenhaInput } from "@/components/flic/senha-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { ConfigEmailOut } from "@/lib/types";

function Formulario({ cfg }: { cfg: ConfigEmailOut }) {
  const qc = useQueryClient();
  const [f, setF] = useState({
    remetente_nome: cfg.remetente_nome,
    remetente_email: cfg.remetente_email,
    smtp_host: cfg.smtp_host ?? "",
    smtp_porta: String(cfg.smtp_porta),
    smtp_usuario: cfg.smtp_usuario ?? "",
    smtp_senha: "",
    copia_padrao: cfg.copia_padrao,
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const salvar = useMutation({
    mutationFn: () =>
      api.put<ConfigEmailOut>("/config/email", {
        ...f,
        smtp_host: f.smtp_host || null,
        smtp_usuario: f.smtp_usuario || null,
        smtp_porta: Number(f.smtp_porta) || 587,
        smtp_senha: f.smtp_senha || null,
      }),
    onSuccess: (novo) => {
      qc.setQueryData(["config-email"], novo);
      set("smtp_senha", "");
      toast.success("Configuração de e-mail salva");
    },
  });
  const testar = useMutation({
    mutationFn: () => api.post<{ mensagem: string }>("/config/email/testar"),
    onSuccess: (r) => toast.success(r.mensagem),
  });
  return (
    <form
      className="card-surface max-w-3xl space-y-4 p-5"
      onSubmit={(e) => {
        e.preventDefault();
        salvar.mutate();
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nome do remetente">
          <Input value={f.remetente_nome} onChange={(e) => set("remetente_nome", e.target.value)} required />
        </Field>
        <Field label="E-mail do remetente">
          <Input type="email" value={f.remetente_email} onChange={(e) => set("remetente_email", e.target.value)} required />
        </Field>
        <Field label="Servidor SMTP" dica="Ex.: smtp.seudominio.com.br">
          <Input value={f.smtp_host} onChange={(e) => set("smtp_host", e.target.value)} placeholder="smtp.seudominio.com.br" />
        </Field>
        <Field label="Porta" dica="465 = SSL direto; 587 = STARTTLS.">
          <Input type="number" value={f.smtp_porta} onChange={(e) => set("smtp_porta", e.target.value)} />
        </Field>
        <Field label="Usuário">
          <Input value={f.smtp_usuario} onChange={(e) => set("smtp_usuario", e.target.value)} autoComplete="off" />
        </Field>
        <Field label="Senha" dica={cfg.smtp_senha_definida ? "Senha salva (cifrada). Preencha só para trocar." : "Fica cifrada no banco."}>
          <SenhaInput value={f.smtp_senha} onChange={(v) => set("smtp_senha", v)} autoComplete="new-password" />
        </Field>
      </div>
      <Field label="Cópia padrão" dica="Estes endereços recebem cópia dos e-mails enviados a clientes e contatos.">
        <EmailChips value={f.copia_padrao} onChange={(v) => set("copia_padrao", v)} />
      </Field>
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" disabled={testar.isPending} onClick={() => testar.mutate()}>
          {testar.isPending ? <Loader2 className="animate-spin" /> : <Send />} Enviar e-mail de teste
        </Button>
        <Button type="submit" disabled={salvar.isPending}>
          {salvar.isPending ? <Loader2 className="animate-spin" /> : <Save />} Salvar
        </Button>
      </div>
    </form>
  );
}

export default function EmailPage() {
  const q = useQuery({ queryKey: ["config-email"], queryFn: () => api.get<ConfigEmailOut>("/config/email") });
  return (
    <div className="space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Mail className="size-5 text-info-ink" /> E-mail
        </h2>
        <p className="text-sm text-muted-foreground">
          SMTP usado para recuperação de senha, convites e envios autorizados a clientes. Sem SMTP em dev, as mensagens vão para a pasta storage/outbox.
        </p>
      </div>
      {q.data ? <Formulario cfg={q.data} /> : <Skeleton className="h-96 max-w-3xl rounded-2xl" />}
    </div>
  );
}
