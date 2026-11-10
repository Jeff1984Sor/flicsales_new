"use client";

/**
 * DetalheTitulo — drawer do título (protótipo `titleDetail`): dados + origem, Editar, Confirmar título (rascunho),
 * Registrar recebimento/pagamento, Cancelar título (com motivo), Histórico de baixas (Estornar) e Perguntar à IA.
 * Os formulários abrem num drawer por cima (Esc fecha só o de cima).
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Dinheiro } from "@/components/flic/dinheiro";
import { Drawer } from "@/components/flic/drawer";
import { Etiqueta } from "@/components/flic/etiqueta";
import { abrirAssistente } from "@/components/flic/eventos";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { competencia, data } from "@/lib/format";
import type { Baixa, Titulo, TituloDetalhe } from "@/lib/tipos-financeiro";

import { CHAVE, Dados, EtiquetaAprovacao, EtiquetaEstado, LIMITE_BAIXA, Limite, ROTULO_FORMA, ROTULO_SIT_COBRANCA, useInvalidarFinanceiro } from "./comum";
import { FormBaixa, FormMotivo } from "./form-baixa";
import { FormTitulo } from "./form-titulo";

export function DetalheTitulo({ id, onFechar }: { id: number | null; onFechar: () => void }) {
  const { data: t, isPending } = useQuery({
    queryKey: [CHAVE, "titulo", id],
    queryFn: () => api.get<TituloDetalhe>(`/financeiro/titulos/${id}`),
    enabled: id != null,
  });
  const nome = t?.direcao === "pagar" ? "A PAGAR" : "A RECEBER";
  return (
    <Drawer
      aberto={id != null}
      onFechar={onFechar}
      rotulo={t ? `TÍTULO / ${nome}` : undefined}
      titulo={t?.descricao}
      descricao={
        t && (
          <span className="inline-flex flex-wrap items-center gap-2">
            {t.empresa_nome} · <EtiquetaEstado estado={t.estado} />
            {t.direcao === "pagar" && t.status !== "cancelado" && <EtiquetaAprovacao aprovacao={t.aprovacao} />}
            {t.em_contestacao && <Etiqueta tom="amber">Em contestação</Etiqueta>}
          </span>
        )
      }
    >
      {isPending || !t ? (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-9 w-2/3" />
        </div>
      ) : (
        <Conteudo t={t} />
      )}
    </Drawer>
  );
}

function Conteudo({ t }: { t: TituloDetalhe }) {
  const { pode } = useAuth();
  const invalidar = useInvalidarFinanceiro();
  const [editar, setEditar] = useState(false);
  const [baixar, setBaixar] = useState<Titulo | null>(null);
  const [cancelar, setCancelar] = useState(false);
  const [estornar, setEstornar] = useState<Baixa | null>(null);
  const receber = t.direcao === "receber";
  const podeTitulos = pode("financeiro.titulos.editar");
  const podeBaixas = pode("financeiro.baixas.editar");

  const confirmar = useMutation({
    mutationFn: () => api.post<Titulo>(`/financeiro/titulos/${t.id}/confirmar`),
    onSuccess: () => {
      invalidar();
      notificar.sucesso("Recebível confirmado, sem baixa financeira");
    },
  });
  const cancelarM = useMutation({
    mutationFn: (motivo: string) => api.post<Titulo>(`/financeiro/titulos/${t.id}/cancelar`, { motivo }),
    onSuccess: () => {
      invalidar();
      setCancelar(false);
      notificar.sucesso("Título cancelado com motivo registrado");
    },
  });
  const estornarM = useMutation({
    mutationFn: ({ baixa, motivo }: { baixa: Baixa; motivo: string }) => api.post<Baixa>(`/financeiro/baixas/${baixa.id}/estornar`, { motivo }),
    onSuccess: () => {
      invalidar();
      setEstornar(null);
      notificar.sucesso("Estorno registrado com histórico preservado");
    },
  });

  const registrar = () => {
    if (!receber && t.aprovacao !== "aprovado") {
      notificar.erro("Aprove o pagamento no controle de aprovações primeiro");
      return;
    }
    setBaixar(t);
  };
  const pedirCancelamento = () => {
    if (t.tem_baixa_ativa) {
      notificar.erro("Estorne as baixas antes de cancelar");
      return;
    }
    setCancelar(true);
  };
  const pedirEdicao = () => {
    if (t.tem_baixa_ativa) {
      notificar.erro("Estorne as baixas antes de editar o título");
      return;
    }
    setEditar(true);
  };

  const origem =
    t.origem.tipo === "oportunidade" && t.origem.id ? (
      <Link className="text-primary hover:underline" href={`/comercial/oportunidades?oportunidade=${t.origem.id}`}>
        {t.origem.rotulo}
      </Link>
    ) : (
      t.origem.rotulo
    );

  const linhas: [string, React.ReactNode][] = [
    ["Valor original", <Dinheiro key="v" valor={t.valor_original} />],
    ["Saldo aberto", <Dinheiro key="s" valor={t.saldo} />],
    ["Vencimento", `${data(t.vencimento)}${t.dias_atraso ? ` · ${t.dias_atraso} dia(s) em atraso` : ""}`],
    ["Competência", competencia(t.competencia)],
    ["Parcela", t.parcela ? `${t.parcela}/${t.parcelas_total ?? "?"}` : "—"],
    ["Categoria", t.categoria_nome ?? "Não definida"],
    ["Centro de custo", t.centro_custo_nome ?? "Não definido"],
    ["Conta prevista", t.conta_prevista_nome ?? "—"],
    ["Forma", t.forma ? ROTULO_FORMA[t.forma] : "—"],
    ["Responsável", t.responsavel_nome ?? "—"],
    ["Documento", t.documento ?? "—"],
    ["Origem", origem],
  ];
  if (!receber) linhas.push(["Aprovação", t.aprovacao === "aprovado" ? `Aprovado por ${t.aprovado_por_nome ?? "—"}` : "Pendente"]);
  if (t.status === "cancelado") linhas.push(["Motivo do cancelamento", t.motivo_cancelamento ?? "—"]);
  if (t.observacoes) linhas.push(["Observações", t.observacoes]);

  return (
    <>
      <Dados linhas={linhas} />
      <div className="mt-5 flex flex-wrap gap-2">
        {podeTitulos && t.status !== "cancelado" && (
          <Button variant="outline" onClick={pedirEdicao}>
            Editar
          </Button>
        )}
        {t.status === "rascunho" && podeTitulos && (
          <Button onClick={() => confirmar.mutate()} disabled={confirmar.isPending}>
            Confirmar título
          </Button>
        )}
        {t.status !== "rascunho" && t.status !== "cancelado" && Number(t.saldo) > 0 && podeBaixas && (
          <Button onClick={registrar}>{receber ? "Registrar recebimento" : "Registrar pagamento"}</Button>
        )}
        {t.status !== "cancelado" && podeTitulos && (
          <Button variant="outline" onClick={pedirCancelamento}>
            Cancelar título
          </Button>
        )}
      </div>
      {t.status === "rascunho" && <Limite>Confirmar o título não registra baixa nem movimenta o caixa.</Limite>}

      <h3 className="mt-6 mb-2 text-sm font-bold">Histórico de baixas</h3>
      {t.baixas.length === 0 ? (
        <p className="text-sm text-muted">Sem baixas registradas.</p>
      ) : (
        <ul className="divide-y divide-line rounded-[9px] border border-line">
          {t.baixas.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center gap-2 px-3 py-2.5 text-[13px]">
              <span className="num">{data(b.data)}</span>·<Dinheiro valor={b.valor} />·<span className="text-muted">{b.conta_nome}</span>
              <span className="ml-auto flex items-center gap-2">
                {b.estornada ? <Etiqueta>Estornada</Etiqueta> : <Etiqueta tom="green">Confirmada</Etiqueta>}
                {!b.estornada && podeBaixas && (
                  <Button size="sm" variant="outline" onClick={() => setEstornar(b)}>
                    Estornar
                  </Button>
                )}
              </span>
              {b.estornada && b.estorno_motivo && <p className="w-full text-xs text-muted">Motivo do estorno: {b.estorno_motivo}</p>}
            </li>
          ))}
        </ul>
      )}

      {t.cobrancas.length > 0 && (
        <>
          <h3 className="mt-6 mb-2 text-sm font-bold">Cobranças e acordos</h3>
          <ul className="space-y-1.5 text-[13px]">
            {t.cobrancas.map((c) => (
              <li key={c.id}>
                {c.assunto} · <span className="text-muted">{ROTULO_SIT_COBRANCA[c.situacao]}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <Limite>{LIMITE_BAIXA}</Limite>
      <Button
        variant="outline"
        className="mt-4"
        onClick={() => abrirAssistente("Este registro", { tipo: "titulo", id: t.id, rotulo: `${t.empresa_nome} · ${t.descricao}` })}
      >
        ✧ Perguntar à IA
      </Button>

      <FormTitulo aberto={editar} onFechar={() => setEditar(false)} direcao={t.direcao} titulo={t} />
      <FormBaixa titulo={baixar} onFechar={() => setBaixar(null)} />
      <FormMotivo
        aberto={cancelar}
        onFechar={() => setCancelar(false)}
        rotulo="TÍTULO / CANCELAMENTO"
        titulo="Cancelar título"
        descricao={
          <>
            {t.empresa_nome} · <Dinheiro valor={t.saldo} />
          </>
        }
        aviso="Nada é apagado: o título fica cancelado, com motivo, autor e data no histórico."
        botao="Confirmar cancelamento gerencial"
        enviando={cancelarM.isPending}
        onConfirmar={(m) => cancelarM.mutate(m)}
      />
      <FormMotivo
        aberto={!!estornar}
        onFechar={() => setEstornar(null)}
        rotulo="BAIXA / ESTORNO"
        titulo="Estornar baixa"
        descricao={
          estornar && (
            <>
              {t.empresa_nome} · <Dinheiro valor={estornar.valor} />
            </>
          )
        }
        aviso="O título volta a ter saldo e o efeito gerencial da baixa é revertido. O movimento original fica preservado."
        botao="Confirmar estorno"
        enviando={estornarM.isPending}
        onConfirmar={(motivo) => estornar && estornarM.mutate({ baixa: estornar, motivo })}
      />
    </>
  );
}
