"use client";

/**
 * Kanban genérico (protótipo `.kanban` / `.column` / `.deal`): colunas com contagem e cartões clicáveis.
 *
 * Props:
 *  - `colunas: { id: string; titulo: string; subtitulo?: string; itens: T[] }[]`
 *        subtitulo ex.: "50% · limite de 10 dias"
 *  - `chave: (item: T) => string | number`
 *  - `cartao: (item: T) => ReactNode`          conteúdo do cartão (use <CartaoKanban> abaixo ou o seu)
 *  - `onCartao?: (item: T) => void`            clique (abre o drawer do registro)
 *  - `onMover?: (item: T, colunaId: string) => void`   arrastar e soltar entre colunas (HTML5). Quem decide se pode
 *                                                       mover (ex.: "Ganha" abre o fechamento) é a tela.
 *  - `vazioColuna?: string`                     texto da coluna sem cartões
 *
 * Ex.:
 *   <Kanban colunas={etapas.map(e => ({ id: String(e.id), titulo: e.nome, subtitulo: `${e.probabilidade}% · limite de ${e.limite_dias} dias`, itens: porEtapa[e.id] ?? [] }))}
 *           chave={(o) => o.id} onCartao={abrir} onMover={mover}
 *           cartao={(o) => <CartaoKanban etiqueta={<Etiqueta tom="green">Alto interesse</Etiqueta>} titulo={o.titulo} subtitulo={o.empresa_nome} valor={<Dinheiro valor={o.valor_unico} />} rodape={`◷ Próxima ação · ${o.responsavel_nome}`} />} />
 */
import { useState } from "react";

import { cn } from "@/lib/utils";

export interface ColunaKanban<T> {
  id: string;
  titulo: string;
  subtitulo?: string;
  itens: T[];
}

export function Kanban<T>({
  colunas,
  chave,
  cartao,
  onCartao,
  onMover,
  vazioColuna = "Nenhum registro nesta etapa.",
  className,
}: {
  colunas: ColunaKanban<T>[];
  chave: (item: T) => string | number;
  cartao: (item: T) => React.ReactNode;
  onCartao?: (item: T) => void;
  onMover?: (item: T, colunaId: string) => void;
  vazioColuna?: string;
  className?: string;
}) {
  const [arrastando, setArrastando] = useState<{ item: T; de: string } | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);

  return (
    <div className={cn("grid grid-cols-1 gap-2 sm:grid-cols-2 md:gap-[15px] min-[1100px]:grid-cols-[repeat(var(--cols),minmax(0,1fr))]", className)} style={{ "--cols": Math.max(colunas.length, 1) } as React.CSSProperties}>
      {colunas.map((c) => (
        <section
          key={c.id}
          aria-label={c.titulo}
          onDragOver={
            onMover
              ? (e) => {
                  e.preventDefault();
                  setSobre(c.id);
                }
              : undefined
          }
          onDragLeave={onMover ? () => setSobre((s) => (s === c.id ? null : s)) : undefined}
          onDrop={
            onMover
              ? (e) => {
                  e.preventDefault();
                  setSobre(null);
                  if (arrastando && arrastando.de !== c.id) onMover(arrastando.item, c.id);
                  setArrastando(null);
                }
              : undefined
          }
          className={cn("min-h-[350px] rounded-[9px] bg-subtle p-[9px] md:p-3.5", sobre === c.id && "ring-2 ring-accent")}
        >
          <h3 className="flex justify-between text-xs font-bold">
            <span>{c.titulo}</span>
            <span className="num text-muted">{c.itens.length}</span>
          </h3>
          {c.subtitulo && <p className="mt-0.5 text-[11px] text-muted">{c.subtitulo}</p>}
          {c.itens.length === 0 && <p className="mt-6 text-center text-[11px] text-muted">{vazioColuna}</p>}
          {c.itens.map((item) => (
            <article
              key={chave(item)}
              draggable={!!onMover}
              onDragStart={onMover ? () => setArrastando({ item, de: c.id }) : undefined}
              onDragEnd={onMover ? () => setArrastando(null) : undefined}
              onClick={onCartao ? () => onCartao(item) : undefined}
              onKeyDown={
                onCartao
                  ? (e) => {
                      if (e.key === "Enter") onCartao(item);
                    }
                  : undefined
              }
              tabIndex={onCartao ? 0 : undefined}
              className={cn(
                "mt-3.5 rounded-[8px] border border-line bg-surface p-2.5 shadow-[0_3px_5px_#00000003] transition hover:border-primary md:p-4",
                onCartao && "cursor-pointer",
              )}
            >
              {cartao(item)}
            </article>
          ))}
        </section>
      ))}
    </div>
  );
}

/** Conteúdo padrão do cartão (`.deal`): etiqueta, título, subtítulo, valor e rodapé. */
export function CartaoKanban({
  etiqueta,
  titulo,
  subtitulo,
  valor,
  rodape,
}: {
  etiqueta?: React.ReactNode;
  titulo: React.ReactNode;
  subtitulo?: React.ReactNode;
  valor?: React.ReactNode;
  rodape?: React.ReactNode;
}) {
  return (
    <>
      {etiqueta}
      <strong className="my-3 block">{titulo}</strong>
      {subtitulo && <p className="text-[11px] text-muted">{subtitulo}</p>}
      {valor && <h4 className="mt-5 text-sm font-bold">{valor}</h4>}
      {rodape && <p className="mt-1.5 text-[11px] text-muted">{rodape}</p>}
    </>
  );
}
