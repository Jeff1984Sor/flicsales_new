"use client";

/**
 * FormTitulo — drawer "Novo/Editar título a receber|a pagar" (protótipo `titleForm/saveTitle`).
 * Campos na ordem do protótipo; aprovação só no a pagar (mudar exige a alçada `financeiro.aprovacoes.editar`).
 */
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Drawer } from "@/components/flic/drawer";
import { notificar } from "@/components/flic/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { hojeISO } from "@/lib/format";
import type { Aprovacao, Direcao, Forma, Titulo, TituloIn } from "@/lib/tipos-financeiro";

import {
  Campo,
  Escolha,
  Limite,
  ROTULO_FORMA,
  Texto,
  TextoLongo,
  deRotulos,
  idOuNulo,
  paraOpcoes,
  textoOuNulo,
  useInvalidarFinanceiro,
  useOpcoes,
  useUsuarios,
} from "./comum";

export function FormTitulo({
  aberto,
  onFechar,
  direcao,
  titulo,
  onSalvo,
}: {
  aberto: boolean;
  onFechar: () => void;
  direcao: Direcao;
  titulo?: Titulo | null;
  onSalvo?: (t: Titulo) => void;
}) {
  const nome = direcao === "receber" ? "a receber" : "a pagar";
  return (
    <Drawer aberto={aberto} onFechar={onFechar} rotulo={`TÍTULO / ${nome.toUpperCase()}`} titulo={`${titulo ? "Editar" : "Novo"} título ${nome}`}>
      <Corpo key={titulo?.id ?? "novo"} direcao={direcao} titulo={titulo ?? null} onFechar={onFechar} onSalvo={onSalvo} />
    </Drawer>
  );
}

function Corpo({ direcao, titulo, onFechar, onSalvo }: { direcao: Direcao; titulo: Titulo | null; onFechar: () => void; onSalvo?: (t: Titulo) => void }) {
  const { usuario, pode } = useAuth();
  const opcoes = useOpcoes();
  const usuarios = useUsuarios();
  const invalidar = useInvalidarFinanceiro();
  const [f, setF] = useState({
    empresa_id: titulo ? String(titulo.empresa_id) : "",
    descricao: titulo?.descricao ?? "",
    documento: titulo?.documento ?? "",
    emissao: titulo?.emissao ?? "",
    competencia: titulo?.competencia ?? "",
    vencimento: titulo?.vencimento ?? hojeISO(),
    valor_original: titulo ? titulo.valor_original : "",
    categoria_id: titulo?.categoria_id ? String(titulo.categoria_id) : "",
    centro_custo_id: titulo?.centro_custo_id ? String(titulo.centro_custo_id) : "",
    conta_prevista_id: titulo?.conta_prevista_id ? String(titulo.conta_prevista_id) : "",
    forma: (titulo?.forma ?? "") as Forma | "",
    responsavel_id: titulo ? String(titulo.responsavel_id) : usuario ? String(usuario.id) : "",
    observacoes: titulo?.observacoes ?? "",
    aprovacao: (titulo?.aprovacao ?? "pendente") as Aprovacao,
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const salvar = useMutation({
    mutationFn: () => {
      const corpo: TituloIn = {
        direcao,
        empresa_id: Number(f.empresa_id),
        descricao: f.descricao,
        documento: textoOuNulo(f.documento),
        emissao: f.emissao || null,
        competencia: f.competencia || null,
        vencimento: f.vencimento,
        valor_original: f.valor_original.replace(",", "."),
        categoria_id: idOuNulo(f.categoria_id),
        centro_custo_id: idOuNulo(f.centro_custo_id),
        conta_prevista_id: idOuNulo(f.conta_prevista_id),
        forma: f.forma || null,
        responsavel_id: Number(f.responsavel_id),
        observacoes: textoOuNulo(f.observacoes),
      };
      if (direcao === "pagar") corpo.aprovacao = f.aprovacao;
      if (!titulo) return api.post<Titulo>("/financeiro/titulos", corpo);
      const { direcao: _d, ...resto } = corpo;
      void _d;
      // só o que mudou de aprovação vai (mudar aprovação exige alçada)
      if (direcao === "pagar" && f.aprovacao === titulo.aprovacao) delete resto.aprovacao;
      return api.patch<Titulo>(`/financeiro/titulos/${titulo.id}`, resto);
    },
    onSuccess: (t) => {
      invalidar();
      notificar.sucesso("Lançamento gerencial salvo");
      onSalvo?.(t);
      onFechar();
    },
  });

  const empresas = (opcoes.data?.empresas ?? []).filter((e) => (direcao === "receber" ? true : e.fornecedor || e.id === titulo?.empresa_id));
  const categorias = (opcoes.data?.categorias ?? []).filter((c) => c.natureza === (direcao === "receber" ? "receita" : "despesa"));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!(Number(f.valor_original.replace(",", ".")) > 0)) {
          notificar.erro("O valor deve ser positivo");
          return;
        }
        salvar.mutate();
      }}
    >
      <Campo rotulo="Cliente / fornecedor" obrigatorio>
        <Escolha valor={f.empresa_id} onChange={(v) => set("empresa_id", v)} opcoes={paraOpcoes(empresas.length ? empresas : opcoes.data?.empresas)} obrigatorio />
      </Campo>
      <Campo rotulo="Descrição" obrigatorio>
        <Texto value={f.descricao} onChange={(e) => set("descricao", e.target.value)} required maxLength={300} />
      </Campo>
      <Campo rotulo="Documento / referência">
        <Texto value={f.documento} onChange={(e) => set("documento", e.target.value)} maxLength={60} />
      </Campo>
      <Campo rotulo="Data de emissão">
        <Texto type="date" value={f.emissao} onChange={(e) => set("emissao", e.target.value)} />
      </Campo>
      <Campo rotulo="Competência">
        <Texto type="month" value={f.competencia} onChange={(e) => set("competencia", e.target.value)} />
      </Campo>
      <Campo rotulo="Vencimento" obrigatorio>
        <Texto type="date" value={f.vencimento} onChange={(e) => set("vencimento", e.target.value)} required />
      </Campo>
      <Campo rotulo="Valor original (R$)" obrigatorio dica={titulo?.tem_baixa_ativa ? "Estorne as baixas antes de alterar o valor." : undefined}>
        <Texto inputMode="decimal" className="num" value={f.valor_original} onChange={(e) => set("valor_original", e.target.value)} required placeholder="0,00" />
      </Campo>
      <Campo rotulo="Categoria">
        <Escolha valor={f.categoria_id} onChange={(v) => set("categoria_id", v)} opcoes={paraOpcoes(categorias)} vazio="—" />
      </Campo>
      <Campo rotulo="Centro de custo">
        <Escolha valor={f.centro_custo_id} onChange={(v) => set("centro_custo_id", v)} opcoes={paraOpcoes(opcoes.data?.centros_custo)} vazio="—" />
      </Campo>
      <Campo rotulo="Conta prevista">
        <Escolha valor={f.conta_prevista_id} onChange={(v) => set("conta_prevista_id", v)} opcoes={paraOpcoes(opcoes.data?.contas)} vazio="—" />
      </Campo>
      <Campo rotulo="Forma de pagamento">
        <Escolha valor={f.forma} onChange={(v) => set("forma", v as Forma | "")} opcoes={deRotulos(ROTULO_FORMA)} vazio="—" />
      </Campo>
      <Campo rotulo="Responsável" obrigatorio>
        <Escolha valor={f.responsavel_id} onChange={(v) => set("responsavel_id", v)} opcoes={paraOpcoes(usuarios.data)} obrigatorio />
      </Campo>
      <Campo rotulo="Observações">
        <TextoLongo value={f.observacoes} onChange={(e) => set("observacoes", e.target.value)} />
      </Campo>
      {direcao === "pagar" && (
        <Campo rotulo="Aprovação" dica={pode("financeiro.aprovacoes.editar") ? undefined : "Aprovar exige alçada (perfil Gestor)."}>
          <Escolha
            valor={f.aprovacao}
            onChange={(v) => set("aprovacao", v as Aprovacao)}
            opcoes={[
              { valor: "pendente", rotulo: "Pendente" },
              { valor: "aprovado", rotulo: "Aprovado" },
            ]}
            vazio={false}
          />
        </Campo>
      )}
      <Limite>Títulos com baixa exigem estorno antes de alterar valor. Pagamentos são registros gerenciais.</Limite>
      <Button type="submit" className="mt-4" disabled={salvar.isPending}>
        Salvar título
      </Button>
    </form>
  );
}
