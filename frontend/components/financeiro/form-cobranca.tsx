"use client";

/**
 * FormCobranca — drawer "Novo registro / Editar · Cobranças e acordos" (protótipo `schemas['Cobranças e acordos']`).
 * Ligada a um título A RECEBER confirmado. "Em contestação" suspende a cobrança automática do título.
 * `onEnviarEmail?`: mostra "✉ Enviar e-mail" na cobrança já salva (quem chama confere a permissão de editar).
 * `onEnviarWhatsApp?`: mostra "WhatsApp" (quem chama confere a permissão e o WhatsApp conectado).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Drawer } from "@/components/flic/drawer";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { moeda } from "@/lib/format";
import type { Canal, Cobranca, CobrancaIn, SituacaoCobranca, Titulo } from "@/lib/tipos-financeiro";
import type { Pagina } from "@/lib/types";

import {
  CHAVE,
  Campo,
  Escolha,
  Limite,
  ROTULO_CANAL,
  ROTULO_SIT_COBRANCA,
  Texto,
  TextoLongo,
  deRotulos,
  paraOpcoes,
  textoOuNulo,
  useInvalidarFinanceiro,
  useUsuarios,
} from "./comum";

export function FormCobranca({
  aberto,
  onFechar,
  cobranca,
  tituloId,
  onEnviarEmail,
  onEnviarWhatsApp,
}: {
  aberto: boolean;
  onFechar: () => void;
  cobranca?: Cobranca | null;
  tituloId?: number | null;
  onEnviarEmail?: (c: Cobranca) => void;
  onEnviarWhatsApp?: (c: Cobranca) => void;
}) {
  return (
    <Drawer aberto={aberto} onFechar={onFechar} rotulo="COBRANÇAS E ACORDOS" titulo={cobranca ? "Editar cobrança" : "Novo registro · Cobranças e acordos"}>
      {cobranca && (onEnviarEmail || onEnviarWhatsApp) && (
        <div className="mb-4 flex flex-wrap gap-2">
          {onEnviarEmail && (
            <Button type="button" variant="outline" onClick={() => onEnviarEmail(cobranca)}>
              ✉ Enviar e-mail
            </Button>
          )}
          {onEnviarWhatsApp && (
            <Button type="button" variant="outline" onClick={() => onEnviarWhatsApp(cobranca)}>
              WhatsApp
            </Button>
          )}
        </div>
      )}
      <Corpo key={cobranca?.id ?? "nova"} cobranca={cobranca ?? null} tituloId={tituloId ?? null} onFechar={onFechar} />
    </Drawer>
  );
}

function Corpo({ cobranca, tituloId, onFechar }: { cobranca: Cobranca | null; tituloId: number | null; onFechar: () => void }) {
  const { usuario } = useAuth();
  const usuarios = useUsuarios();
  const invalidar = useInvalidarFinanceiro();
  const titulos = useQuery({
    queryKey: [CHAVE, "titulos-cobraveis"],
    queryFn: () => api.get<Pagina<Titulo>>("/financeiro/titulos", { direcao: "receber", por_pagina: 200 }),
    enabled: !cobranca,
  });
  const [f, setF] = useState({
    assunto: cobranca?.assunto ?? "",
    titulo_id: cobranca ? String(cobranca.titulo_id) : tituloId ? String(tituloId) : "",
    responsavel_id: cobranca ? String(cobranca.responsavel_id) : usuario ? String(usuario.id) : "",
    canal: (cobranca?.canal ?? "email") as Canal,
    situacao: (cobranca?.situacao ?? "em_acompanhamento") as SituacaoCobranca,
    data_prometida: cobranca?.data_prometida ?? "",
    valor_prometido: cobranca?.valor_prometido ?? "",
    proximo_contato: cobranca?.proximo_contato ?? "",
    historico: cobranca?.historico ?? "",
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const salvar = useMutation({
    mutationFn: () => {
      const corpo: CobrancaIn = {
        assunto: f.assunto,
        titulo_id: Number(f.titulo_id),
        responsavel_id: Number(f.responsavel_id),
        canal: f.canal,
        situacao: f.situacao,
        data_prometida: f.data_prometida || null,
        valor_prometido: textoOuNulo(f.valor_prometido.replace(",", ".")),
        proximo_contato: f.proximo_contato || null,
        historico: f.historico,
      };
      if (cobranca) {
        const { titulo_id: _t, ...resto } = corpo;
        void _t;
        return api.patch<Cobranca>(`/financeiro/cobrancas/${cobranca.id}`, resto);
      }
      return api.post<Cobranca>("/financeiro/cobrancas", corpo);
    },
    onSuccess: () => {
      invalidar();
      notificar.sucesso("Registro salvo");
      onFechar();
    },
  });

  // só títulos confirmados com saldo (aberto/parcial, inclusive vencidos)
  const cobraveis = (titulos.data?.itens ?? [])
    .filter((t) => ["aberto", "parcial"].includes(t.status) || String(t.id) === f.titulo_id)
    .map((t) => ({ valor: String(t.id), rotulo: `${t.empresa_nome} · ${t.descricao} · ${moeda(t.saldo)}` }));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (f.situacao === "promessa_pagamento" && !f.data_prometida) {
          notificar.erro("Promessa de pagamento exige a data prometida.");
          return;
        }
        salvar.mutate();
      }}
    >
      <Campo rotulo="Assunto" obrigatorio>
        <Texto value={f.assunto} onChange={(e) => set("assunto", e.target.value)} required maxLength={200} />
      </Campo>
      <Campo rotulo="Título a receber" obrigatorio>
        {cobranca ? (
          <p className="text-sm">
            {cobranca.empresa_nome} · {cobranca.titulo_descricao}
          </p>
        ) : (
          <Escolha valor={f.titulo_id} onChange={(v) => set("titulo_id", v)} opcoes={cobraveis} obrigatorio />
        )}
      </Campo>
      <Campo rotulo="Responsável" obrigatorio>
        <Escolha valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} opcoes={paraOpcoes(usuarios.data)} obrigatorio />
      </Campo>
      <Campo rotulo="Canal" obrigatorio>
        <Escolha valor={f.canal} onChange={(v) => set("canal", v as Canal)} opcoes={deRotulos(ROTULO_CANAL)} vazio={false} />
      </Campo>
      <Campo rotulo="Situação" obrigatorio dica={f.situacao === "em_contestacao" ? "Em contestação: a cobrança automática deste título fica suspensa." : undefined}>
        <Escolha valor={f.situacao} onChange={(v) => set("situacao", v as SituacaoCobranca)} opcoes={deRotulos(ROTULO_SIT_COBRANCA)} vazio={false} />
      </Campo>
      <Campo rotulo="Data prometida" obrigatorio={f.situacao === "promessa_pagamento"}>
        <Texto type="date" value={f.data_prometida} onChange={(e) => set("data_prometida", e.target.value)} />
      </Campo>
      <Campo rotulo="Valor prometido (R$)">
        <Texto inputMode="decimal" className="num" value={f.valor_prometido} onChange={(e) => set("valor_prometido", e.target.value)} placeholder="0,00" />
      </Campo>
      <Campo rotulo="Próximo contato">
        <Texto type="date" value={f.proximo_contato} onChange={(e) => set("proximo_contato", e.target.value)} />
      </Campo>
      <Campo rotulo="Histórico / acordo" obrigatorio>
        <TextoLongo value={f.historico} onChange={(e) => set("historico", e.target.value)} required />
      </Campo>
      <Limite>Registro de acompanhamento. Salvar não envia mensagem; o envio é pelo “Enviar e-mail” e entra no histórico.</Limite>
      <Button type="submit" className="mt-4" disabled={salvar.isPending}>
        Salvar registro
      </Button>
    </form>
  );
}
