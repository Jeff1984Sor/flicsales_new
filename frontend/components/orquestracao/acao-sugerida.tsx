"use client";

/**
 * AcaoSugerida — botão de uma ação sugerida pela IA/regras. Ações nascem PROPOSTAS:
 *  - `criar_atividade`: abre uma revisão curta (assunto e prazo editáveis) e só cria após "Criar tarefa após revisão"
 *    (POST /orquestracao/acoes/executar — o servidor aceita só tipos permitidos e checa a permissão de atividades).
 *  - `abrir_registro`: atalho para a tela do registro.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CampoDrawer } from "@/components/flic/drawer";
import { notificar } from "@/components/flic/toast";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hojeISO } from "@/lib/format";
import type { AcaoExecutada } from "@/lib/tipos-orquestracao";
import type { AcaoSugeridaIA } from "@/lib/types";

import { rotaDoRegistro } from "./eventos-ia";

function texto(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function registroDe(payload: Record<string, unknown>): { tipo?: string; id?: number; direcao?: string } {
  const r = payload.registro;
  if (r && typeof r === "object" && "tipo" in r && "id" in r) {
    const x = r as { tipo: unknown; id: unknown; direcao?: unknown };
    const direcao = x.direcao ?? payload.direcao;
    return { tipo: String(x.tipo), id: Number(x.id), direcao: typeof direcao === "string" ? direcao : undefined };
  }
  return {};
}

export function AcaoSugerida({ acao }: { acao: AcaoSugeridaIA }) {
  const { pode } = useAuth();
  const qc = useQueryClient();
  const [revisando, setRevisando] = useState(false);
  const [assunto, setAssunto] = useState(texto(acao.payload.assunto) || acao.rotulo);
  const [prazo, setPrazo] = useState(texto(acao.payload.prazo) || hojeISO());
  const [feito, setFeito] = useState(false);

  const criar = useMutation({
    mutationFn: () =>
      api.post<AcaoExecutada>("/orquestracao/acoes/executar", {
        tipo: "criar_atividade",
        payload: { ...acao.payload, assunto: assunto.trim(), prazo: prazo || null },
      }),
    onSuccess: (r) => {
      setFeito(true);
      setRevisando(false);
      notificar.sucesso(r.mensagem);
      void qc.invalidateQueries({ queryKey: ["atividades"] });
    },
  });

  if (acao.tipo === "abrir_registro") {
    const reg = registroDe(acao.payload);
    const rota = rotaDoRegistro(reg.tipo, reg.direcao);
    if (!rota) return null;
    return (
      <Link className={buttonVariants({ variant: "outline", size: "sm" })} href={reg.id ? `${rota}?id=${reg.id}` : rota}>
        {acao.rotulo}
      </Link>
    );
  }
  if (acao.tipo !== "criar_atividade") return null;
  if (!pode("comercial.atividades.editar")) {
    return <p className="text-xs text-muted">Sugestão: {acao.rotulo} (seu perfil não cria atividades).</p>;
  }
  if (feito) return <p className="text-xs font-medium text-primary">✓ Atividade criada após sua revisão.</p>;
  if (!revisando) {
    return (
      <Button type="button" variant="outline" size="sm" onClick={() => setRevisando(true)} title={acao.rotulo}>
        Criar tarefa após revisão
      </Button>
    );
  }
  return (
    <div className="w-full rounded-[9px] border border-line bg-surface p-3">
      <p className="text-xs text-muted">Revise antes de criar. Criar atividade não envia mensagem.</p>
      <CampoDrawer rotulo="Assunto" obrigatorio htmlFor={`acao-assunto-${acao.rotulo}`}>
        <Input id={`acao-assunto-${acao.rotulo}`} value={assunto} onChange={(e) => setAssunto(e.target.value)} maxLength={200} />
      </CampoDrawer>
      <CampoDrawer rotulo="Prazo" obrigatorio htmlFor={`acao-prazo-${acao.rotulo}`}>
        <Input id={`acao-prazo-${acao.rotulo}`} type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)} />
      </CampoDrawer>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" size="sm" disabled={!assunto.trim() || !prazo || criar.isPending} onClick={() => criar.mutate()}>
          {criar.isPending && <Loader2 className="animate-spin" />}
          Criar tarefa
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setRevisando(false)}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
