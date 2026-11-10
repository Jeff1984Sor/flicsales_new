"use client";

/**
 * EmConstrucao — página provisória de uma rota do menu (título e subtítulo do protótipo + estado vazio).
 * O módulo dono substitui a página inteira quando implementar a tela.
 * Props: `titulo`, `descricao`, `semIA?`
 */
import { Hammer } from "lucide-react";

import { EmptyState } from "./empty-state";
import { PageHeader } from "./page-header";

export function EmConstrucao({ titulo, descricao, semIA }: { titulo: string; descricao: string; semIA?: boolean }) {
  return (
    <>
      <PageHeader titulo={titulo} descricao={descricao} semIA={semIA} />
      <div className="card-surface">
        <EmptyState
          icone={Hammer}
          titulo="Em construção"
          descricao="Esta tela faz parte da fundação do FlicSales OS e será entregue pelo módulo responsável."
        />
      </div>
    </>
  );
}
