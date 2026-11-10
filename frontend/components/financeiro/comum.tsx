"use client";

/**
 * Peças comuns das telas do Financeiro: rótulos, etiquetas de estado, opções dos formulários (empresas, categorias,
 * centros de custo, contas, usuários), invalidação das consultas e campos de formulário no padrão do drawer.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Etiqueta, type TomEtiqueta } from "@/components/flic/etiqueta";
import { NativeSelect } from "@/components/flic/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type {
  Aprovacao,
  Canal,
  EstadoTitulo,
  Forma,
  Frequencia,
  OpcoesFinanceiro,
  SituacaoCobranca,
  SituacaoRecorrencia,
  UsuarioOpcao,
} from "@/lib/tipos-financeiro";
import { cn } from "@/lib/utils";

export const ROTULO_ESTADO: Record<EstadoTitulo, string> = {
  rascunho: "Rascunho",
  aberto: "Aberto",
  parcial: "Parcial",
  liquidado: "Liquidado",
  cancelado: "Cancelado",
  vencido: "Vencido",
};

const TOM_ESTADO: Record<EstadoTitulo, TomEtiqueta> = {
  rascunho: "neutra",
  aberto: "azul",
  parcial: "azul",
  liquidado: "green",
  cancelado: "neutra",
  vencido: "amber",
};

export const ROTULO_FORMA: Record<Forma, string> = {
  pix: "Pix",
  boleto: "Boleto",
  transferencia: "Transferência",
  cartao: "Cartão",
  dinheiro: "Dinheiro",
  outra: "Outra",
};

export const ROTULO_FREQUENCIA: Record<Frequencia, string> = { mensal: "Mensal", trimestral: "Trimestral", anual: "Anual" };
export const ROTULO_SIT_RECORRENCIA: Record<SituacaoRecorrencia, string> = { ativa: "Ativa", pausada: "Pausada", cancelada: "Cancelada" };
export const ROTULO_SIT_COBRANCA: Record<SituacaoCobranca, string> = {
  em_acompanhamento: "Em acompanhamento",
  promessa_pagamento: "Promessa de pagamento",
  em_contestacao: "Em contestação",
  resolvida: "Resolvida",
};
export const ROTULO_CANAL: Record<Canal, string> = { email: "E-mail", ligacao: "Ligação", whatsapp: "WhatsApp" };

export const LIMITE_BAIXA = "Baixas são gerenciais. Nenhuma operação bancária é executada.";

export function EtiquetaEstado({ estado }: { estado: EstadoTitulo }) {
  return <Etiqueta tom={TOM_ESTADO[estado]}>{ROTULO_ESTADO[estado]}</Etiqueta>;
}

export function EtiquetaAprovacao({ aprovacao }: { aprovacao: Aprovacao | null }) {
  return aprovacao === "aprovado" ? <Etiqueta tom="green">Aprovado</Etiqueta> : <Etiqueta tom="amber">Pendente</Etiqueta>;
}

/** Prefixo de todas as consultas do Financeiro: mutações invalidam tudo de uma vez (listas, caixa, hoje…). */
export const CHAVE = "financeiro";

export function useInvalidarFinanceiro() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: [CHAVE] });
}

export function useOpcoes() {
  return useQuery({
    queryKey: [CHAVE, "opcoes"],
    queryFn: () => api.get<OpcoesFinanceiro>("/financeiro/titulos/opcoes"),
    staleTime: 60_000,
  });
}

export function useUsuarios() {
  return useQuery({
    queryKey: ["usuarios-opcoes"],
    queryFn: () => api.get<UsuarioOpcao[]>("/config/usuarios/opcoes"),
    staleTime: 60_000,
  });
}

/** Campo do drawer (rótulo 12px, `*` nos obrigatórios), no padrão `CampoDrawer` do kit. */
export function Campo({ rotulo, obrigatorio, dica, className, children }: { rotulo: string; obrigatorio?: boolean; dica?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <label className={cn("mt-[17px] block first:mt-0", className)}>
      <span className="mb-[7px] block text-xs">
        {rotulo}
        {obrigatorio && " *"}
      </span>
      {children}
      {dica && <span className="mt-1 block text-xs text-muted">{dica}</span>}
    </label>
  );
}

export function Texto(props: React.ComponentProps<typeof Input>) {
  return <Input {...props} className={cn("h-9", props.className)} />;
}

export function TextoLongo(props: React.ComponentProps<typeof Textarea>) {
  return <Textarea {...props} />;
}

/** Select com opção vazia ("—") e lista de {valor, rotulo}. */
export function Escolha({
  valor,
  onChange,
  opcoes,
  vazio = "Selecione",
  obrigatorio,
}: {
  valor: string;
  onChange: (v: string) => void;
  opcoes: { valor: string; rotulo: string }[];
  vazio?: string | false;
  obrigatorio?: boolean;
}) {
  return (
    <NativeSelect value={valor} onChange={(e) => onChange(e.target.value)} required={obrigatorio}>
      {vazio !== false && <option value="">{vazio}</option>}
      {opcoes.map((o) => (
        <option key={o.valor} value={o.valor}>
          {o.rotulo}
        </option>
      ))}
    </NativeSelect>
  );
}

export const paraOpcoes = <T extends { id: number; nome: string }>(lista: T[] | undefined) =>
  (lista ?? []).map((o) => ({ valor: String(o.id), rotulo: o.nome }));

export const deRotulos = <K extends string>(r: Record<K, string>) =>
  (Object.entries(r) as [K, string][]).map(([valor, rotulo]) => ({ valor, rotulo }));

/** "" → null; número inteiro do id. */
export const idOuNulo = (v: string) => (v ? Number(v) : null);
export const textoOuNulo = (v: string) => (v.trim() ? v.trim() : null);

/** Linhas chave: valor do bloco "answer" do protótipo (detalhe do título). */
export function Dados({ linhas }: { linhas: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 rounded-[9px] bg-subtle p-4 text-[13px]">
      {linhas.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Limite({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("mt-4 text-xs leading-relaxed text-muted", className)}>{children}</p>;
}
