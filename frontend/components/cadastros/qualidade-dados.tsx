"use client";

/**
 * QualidadeDados — painel "Qualidade dos dados": empresas prováveis duplicadas (mesmo documento, mesmo nome sem
 * sufixos ou nomes muito parecidos) e mesclagem revisada: o usuário escolhe qual fica; todos os vínculos
 * (contatos, oportunidades, atividades, propostas, títulos, recorrências…) passam para ela e a outra é inativada.
 * Aparece só para quem tem `nucleo.administracao.ver`; mesclar exige `nucleo.administracao.editar`.
 * Sem props. Pode ser usado em Núcleo › Administração.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { useState } from "react";

import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { Painel } from "@/components/flic/painel";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Duplicidade, EmpresaCurta, MesclaResultado } from "@/lib/tipos-nucleo";
import { cn } from "@/lib/utils";

import { useInvalidarCadastros } from "./comum";

function Cartao({ e, escolhida, onEscolher }: { e: EmpresaCurta; escolhida: boolean; onEscolher: () => void }) {
  return (
    <button
      type="button"
      onClick={onEscolher}
      aria-pressed={escolhida}
      className={cn("flex-1 rounded-[10px] border p-4 text-left transition", escolhida ? "border-primary bg-tint" : "border-line bg-surface hover:border-primary")}
    >
      <div className="eyebrow mb-1">{escolhida ? "FICA" : "SERÁ INATIVADA"}</div>
      <strong className="text-sm">{e.nome}</strong>
      <p className="text-xs text-muted">{e.documento ?? "Sem documento"}</p>
      <p className="mt-2 text-xs">
        {e.oportunidades} oportunidade(s) · {e.titulos} título(s)
      </p>
    </button>
  );
}

export function QualidadeDados() {
  const { podeVer, pode } = useAuth();
  const invalidar = useInvalidarCadastros();
  const [par, setPar] = useState<Duplicidade | null>(null);
  const [fica, setFica] = useState<number | null>(null);
  const visivel = podeVer("nucleo.administracao");
  const { data, isPending } = useQuery({
    queryKey: ["nucleo", "empresas", "duplicidades"],
    queryFn: () => api.get<Duplicidade[]>("/nucleo/duplicidades"),
    enabled: visivel,
  });
  const mesclar = useMutation({
    mutationFn: ({ destino, origem }: { destino: number; origem: number }) => api.post<MesclaResultado>(`/nucleo/empresas/${destino}/mesclar`, { duplicada_id: origem }),
    onSuccess: (r) => {
      invalidar("empresas", "pessoas");
      notificar.sucesso(r.mensagem);
      setPar(null);
    },
  });
  if (!visivel) return null;

  const abrir = (p: Duplicidade) => {
    setPar(p);
    // sugestão: fica a que tem mais vínculos
    setFica(p.a.oportunidades + p.a.titulos >= p.b.oportunidades + p.b.titulos ? p.a.id : p.b.id);
  };
  const origem = par && fica != null ? (fica === par.a.id ? par.b : par.a) : null;

  return (
    <>
      <Painel titulo="Qualidade dos dados" acao={<Etiqueta tom={data?.length ? "amber" : "green"}>{isPending ? "Verificando…" : `${data?.length ?? 0} possível(is) duplicidade(s)`}</Etiqueta>}>
        {!isPending && (data?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted">Nenhuma empresa duplicada encontrada. A verificação compara documento, nome sem sufixos (Ltda, S/A…) e nomes parecidos.</p>
        ) : (
          <ul className="divide-y divide-line">
            {(data ?? []).map((p) => (
              <li key={`${p.a.id}-${p.b.id}`} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                <strong>{p.a.nome}</strong>
                <ArrowLeftRight className="size-4 text-muted" aria-hidden />
                <strong>{p.b.nome}</strong>
                <span className="text-xs text-muted">
                  {p.motivo} · {Math.round(p.semelhanca * 100)}%
                </span>
                <Button size="sm" variant="outline" className="ml-auto" onClick={() => abrir(p)}>
                  Revisar e mesclar
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Painel>
      <Drawer
        aberto={!!par}
        onFechar={() => setPar(null)}
        rotulo="QUALIDADE DOS DADOS / MESCLAGEM"
        titulo="Revisar duplicidade"
        descricao={par?.motivo}
        rodape={
          pode("nucleo.administracao.editar") && par && fica != null && origem ? (
            <>
              <Button disabled={mesclar.isPending} onClick={() => mesclar.mutate({ destino: fica, origem: origem.id })}>
                {mesclar.isPending ? "Mesclando…" : "Mesclar empresas"}
              </Button>
              <Button variant="outline" onClick={() => setPar(null)}>
                Cancelar
              </Button>
            </>
          ) : undefined
        }
      >
        {par && (
          <div className="flex flex-col gap-4">
            <p className="text-sm">Escolha a empresa que fica:</p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Cartao e={par.a} escolhida={fica === par.a.id} onEscolher={() => setFica(par.a.id)} />
              <Cartao e={par.b} escolhida={fica === par.b.id} onEscolher={() => setFica(par.b.id)} />
            </div>
            <p className="text-xs leading-relaxed text-muted">
              Todos os vínculos da outra (contatos, oportunidades, atividades, comunicações, propostas, títulos e recorrências) passam para a escolhida. Campos vazios da escolhida são
              completados, os papéis se somam e a outra é inativada. Nada é apagado; a mesclagem fica no histórico de ações.
            </p>
          </div>
        )}
      </Drawer>
    </>
  );
}
