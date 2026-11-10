/**
 * Painel — card de conteúdo (protótipo `.panel` + `.panelhead`).
 * Props:
 *  - `titulo?: ReactNode`   h2 17px no cabeçalho
 *  - `acao?: ReactNode`     à direita do título (Etiqueta, botão "Ver atividades"…)
 *  - `semPadding?: boolean` para tabelas encostadas na borda
 *  - `children`
 * Ex.: <Painel titulo="O que merece sua atenção" acao={<Etiqueta tom="green">Próximas ações</Etiqueta>}>…</Painel>
 * Grade 1.6fr/1fr do protótipo: <GradePaineis>…</GradePaineis>
 */
import { cn } from "@/lib/utils";

export function Painel({
  titulo,
  acao,
  semPadding,
  className,
  children,
}: {
  titulo?: React.ReactNode;
  acao?: React.ReactNode;
  semPadding?: boolean;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <section className={cn("card-surface mb-5", semPadding ? "overflow-hidden" : "p-[17px] md:p-6", className)}>
      {(titulo || acao) && (
        <div className={cn("mb-[17px] flex flex-wrap items-center justify-between gap-3", semPadding && "mb-0 border-b border-line px-6 py-4")}>
          {titulo && <h2 className="text-[17px] font-bold">{titulo}</h2>}
          {acao && <div className="flex flex-wrap items-center gap-2">{acao}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** Grade de duas colunas do protótipo (1.6fr / 1fr; empilha abaixo de 1100px). */
export function GradePaineis({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("grid gap-[22px] min-[1100px]:grid-cols-[1.6fr_1fr]", className)}>{children}</div>;
}
