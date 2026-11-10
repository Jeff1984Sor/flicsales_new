"use client";

/**
 * AtividadeForm — drawer "Nova atividade" / "Editar atividade" (protótipo `activityForm`).
 *
 * Props:
 *  - `aberto`, `onFechar`
 *  - `atividade?: Atividade | null`      edição
 *  - `inicial?: Partial<AtividadeEntrada>` valores sugeridos (ex.: tarefa sugerida pela análise, origem "ia")
 *  - `titulo?: string`                     título do drawer (padrão "Nova atividade")
 *  - `aoSalvar?: (a: Atividade) => void`
 *
 * Regra: Reunião exige início e fim no mesmo dia. Atividade agenda trabalho; não envia mensagens nem convites.
 */
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { CampoDrawer, Drawer } from "@/components/flic/drawer";
import { NativeSelect } from "@/components/flic/form";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hojeISO } from "@/lib/format";
import { type Atividade, type AtividadeEntrada, TIPOS_ATIVIDADE, type TipoAtividade } from "@/lib/tipos-comercial";

import { hora, lerForm, nulo, numeroOuNulo, useInvalidarComercial, useOpcoes, useUsuarios } from "./dados";

export function AtividadeForm({
  aberto,
  onFechar,
  atividade,
  inicial,
  titulo,
  aoSalvar,
}: {
  aberto: boolean;
  onFechar: () => void;
  atividade?: Atividade | null;
  inicial?: Partial<AtividadeEntrada>;
  titulo?: string;
  aoSalvar?: (a: Atividade) => void;
}) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} titulo={titulo ?? (atividade ? "Editar atividade" : "Nova atividade")}>
      {aberto && <Corpo key={atividade?.id ?? "nova"} atividade={atividade} inicial={inicial} onFechar={onFechar} aoSalvar={aoSalvar} />}
    </Drawer>
  );
}

function Corpo({
  atividade,
  inicial,
  onFechar,
  aoSalvar,
}: {
  atividade?: Atividade | null;
  inicial?: Partial<AtividadeEntrada>;
  onFechar: () => void;
  aoSalvar?: (a: Atividade) => void;
}) {
  const { usuario } = useAuth();
  const { data: opcoes } = useOpcoes();
  const { data: usuarios } = useUsuarios();
  const invalidar = useInvalidarComercial();
  const base: Partial<AtividadeEntrada> = atividade ?? inicial ?? {};
  const [tipo, setTipo] = useState<TipoAtividade>(base.tipo ?? "tarefa");

  const salvar = useMutation({
    mutationFn: (corpo: AtividadeEntrada) =>
      atividade ? api.patch<Atividade>(`/comercial/atividades/${atividade.id}`, corpo) : api.post<Atividade>("/comercial/atividades", corpo),
    onSuccess: (a) => {
      invalidar();
      notificar(atividade ? "Atividade atualizada" : "Atividade registrada");
      aoSalvar?.(a);
      onFechar();
    },
  });

  function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = lerForm(e.currentTarget);
    if (f.tipo === "reuniao" && (!f.hora_inicio || !f.hora_fim || f.hora_fim <= f.hora_inicio)) {
      notificar("Reunião exige início e fim válido no mesmo dia");
      return;
    }
    salvar.mutate({
      assunto: f.assunto.trim(),
      tipo: f.tipo as TipoAtividade,
      responsavel_id: numeroOuNulo(f.responsavel_id),
      oportunidade_id: numeroOuNulo(f.oportunidade_id),
      empresa_id: numeroOuNulo(f.empresa_id),
      prazo: f.prazo,
      hora_inicio: nulo(f.hora_inicio),
      hora_fim: nulo(f.hora_fim),
      fuso: nulo(f.fuso),
      participantes: nulo(f.participantes),
      canal: nulo(f.canal),
      objetivo: nulo(f.objetivo),
      resultado: nulo(f.resultado),
      ...(atividade ? {} : { origem: inicial?.origem ?? "manual" }),
    });
  }

  return (
    <form id="form-atividade" onSubmit={enviar}>
      <CampoDrawer rotulo="Assunto" obrigatorio>
        <Input name="assunto" required defaultValue={base.assunto ?? ""} maxLength={200} />
      </CampoDrawer>
      <CampoDrawer rotulo="Tipo" obrigatorio>
        <NativeSelect name="tipo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoAtividade)}>
          {TIPOS_ATIVIDADE.map((t) => (
            <option key={t.valor} value={t.valor}>
              {t.rotulo}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Responsável" obrigatorio>
        <NativeSelect name="responsavel_id" defaultValue={String(base.responsavel_id ?? usuario?.id ?? "")}>
          {(usuarios ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Empresa">
        <NativeSelect name="empresa_id" defaultValue={String(base.empresa_id ?? "")}>
          <option value="">Da oportunidade / sem empresa</option>
          {(opcoes?.empresas ?? []).map((e) => (
            <option key={e.id} value={e.id}>
              {e.nome}
            </option>
          ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Oportunidade">
        <NativeSelect name="oportunidade_id" defaultValue={String(base.oportunidade_id ?? "")}>
          <option value="">Sem oportunidade</option>
          {(opcoes?.oportunidades ?? [])
            .filter((o) => o.resultado === "aberta" || o.id === base.oportunidade_id)
            .map((o) => (
              <option key={o.id} value={o.id}>
                {o.nome}
              </option>
            ))}
        </NativeSelect>
      </CampoDrawer>
      <CampoDrawer rotulo="Prazo / data" obrigatorio>
        <Input name="prazo" type="date" required defaultValue={base.prazo ?? hojeISO()} />
      </CampoDrawer>
      <div className="grid grid-cols-2 gap-3">
        <CampoDrawer rotulo="Horário" obrigatorio={tipo === "reuniao"}>
          <Input name="hora_inicio" type="time" defaultValue={hora(base.hora_inicio)} required={tipo === "reuniao"} />
        </CampoDrawer>
        <CampoDrawer rotulo="Horário final · reuniões" obrigatorio={tipo === "reuniao"}>
          <Input name="hora_fim" type="time" defaultValue={hora(base.hora_fim)} required={tipo === "reuniao"} />
        </CampoDrawer>
      </div>
      <CampoDrawer rotulo="Fuso">
        <Input name="fuso" defaultValue={base.fuso ?? "America/Sao_Paulo"} />
      </CampoDrawer>
      <CampoDrawer rotulo="Participantes / destinatário">
        <Input name="participantes" defaultValue={base.participantes ?? ""} />
      </CampoDrawer>
      <CampoDrawer rotulo="Link / telefone / endereço">
        <Input name="canal" defaultValue={base.canal ?? ""} />
      </CampoDrawer>
      <CampoDrawer rotulo="Objetivo / roteiro">
        <Textarea name="objetivo" defaultValue={base.objetivo ?? ""} />
      </CampoDrawer>
      <CampoDrawer rotulo="Resultado / observações">
        <Textarea name="resultado" defaultValue={base.resultado ?? ""} />
      </CampoDrawer>
      <p className="mt-4 text-xs text-muted">Atividade agenda trabalho. Não envia mensagens ou convites.</p>
      <div className="mt-5 flex gap-2">
        <Button type="submit" disabled={salvar.isPending}>
          {salvar.isPending && <Loader2 className="animate-spin" />}
          Salvar atividade
        </Button>
        <Button type="button" variant="outline" onClick={onFechar}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}
