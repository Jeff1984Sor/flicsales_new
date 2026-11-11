"use client";

/**
 * Drawer — painel lateral direito (protótipo `.drawer`), usado para DETALHE de registro e FORMULÁRIOS.
 * Não abre página nova: a lista continua visível à esquerda.
 *
 * Props:
 *  - `aberto: boolean`             controla a exibição
 *  - `onFechar: () => void`        chamado no ✕, no Esc (só o drawer do topo fecha) e por quem usa
 *  - `titulo?: ReactNode`          título grande (h2 23px)
 *  - `descricao?: ReactNode`       linha cinza abaixo do título
 *  - `rotulo?: string`             eyebrow do registro acima do título (ex.: "OPORTUNIDADE / NEGOCIAÇÃO")
 *  - `eyebrow?: string`            cabeçalho fixo do painel (padrão vazio: não renderiza)
 *  - `rodape?: ReactNode`          barra fixa no fim (botões Salvar/Cancelar)
 *  - `largura?: number | "padrao" | "metade"`   px (padrão 470) ou "metade" = metade da tela, mínimo 640px
 *                                  (abaixo de 1024px ocupa a largura toda) — usado por empresa e fornecedor
 *  - `children`                    conteúdo (rolável)
 *
 * Exemplo:
 *   <Drawer aberto={!!sel} onFechar={() => setSel(null)} rotulo="OPORTUNIDADE / PROPOSTA" titulo={sel?.titulo}>
 *     …
 *   </Drawer>
 *
 * Formulário no drawer: envolva em <form id="f-x"> e ponha <Button type="submit" form="f-x"> no `rodape`.
 */
import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

// pilha de drawers abertos: Esc fecha só o de cima
const pilha: string[] = [];
// camadas que já tratam o próprio Esc (modal, confirmação, menus, paleta)
const SOBREPOSTOS = [
  "dialog-content",
  "alert-dialog-content",
  "dropdown-menu-content",
  "select-content",
  "popover-content",
]
  .map((s) => `[data-slot="${s}"]`)
  .join(",");

const nada = () => () => {};

export function Drawer({
  aberto,
  onFechar,
  titulo,
  descricao,
  rotulo,
  eyebrow,
  rodape,
  largura = 470,
  className,
  children,
}: {
  aberto: boolean;
  onFechar: () => void;
  titulo?: React.ReactNode;
  descricao?: React.ReactNode;
  rotulo?: string;
  eyebrow?: string;
  rodape?: React.ReactNode;
  largura?: number | "padrao" | "metade";
  className?: string;
  children?: React.ReactNode;
}) {
  const metade = largura === "metade";
  const px = typeof largura === "number" ? largura : 470;
  const id = useId();
  const noCliente = useSyncExternalStore(
    nada,
    () => true,
    () => false,
  );

  useEffect(() => {
    if (!aberto) return;
    pilha.push(id);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && pilha[pilha.length - 1] === id && !e.defaultPrevented) {
        // diálogos/menus abertos por cima (base-ui) tratam o próprio Esc
        if (document.querySelector(SOBREPOSTOS)) return;
        e.preventDefault();
        onFechar();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      const i = pilha.lastIndexOf(id);
      if (i >= 0) pilha.splice(i, 1);
    };
  }, [aberto, id, onFechar]);

  if (!noCliente) return null;

  return createPortal(
    <AnimatePresence>
      {aberto && (
        <motion.section
          key="drawer"
          role="dialog"
          aria-modal="false"
          aria-label={typeof titulo === "string" ? titulo : "Painel contextual"}
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", stiffness: 420, damping: 40 }}
          style={metade ? undefined : { width: `min(100%, ${px}px)` }}
          className={cn(
            metade && "w-full lg:w-[max(640px,50vw)]",
            "fixed top-0 right-0 bottom-0 z-50 flex flex-col bg-surface text-ink shadow-[-10px_0_50px_color-mix(in_oklab,var(--ink)_14%,transparent)] md:top-[calc(var(--tb)+var(--faixa))] md:z-40",
            className,
          )}
        >
          <div className="flex-1 overflow-y-auto p-[26px]">
            <div className={cn("mb-[17px] flex items-center", eyebrow ? "justify-between" : "justify-end")}>
              {eyebrow && <span className="eyebrow">{eyebrow}</span>}
              <button
                type="button"
                onClick={onFechar}
                aria-label="Fechar painel"
                className="grid size-9 place-items-center rounded-[7px] border border-line bg-surface text-ink transition hover:border-primary"
              >
                <X className="size-4" />
              </button>
            </div>
            {rotulo && <div className="eyebrow mb-3">{rotulo}</div>}
            {titulo && <h2 className="text-[23px] leading-tight font-bold tracking-tight">{titulo}</h2>}
            {descricao && <p className="mt-1.5 text-sm text-muted">{descricao}</p>}
            <div className={cn((titulo || descricao) && "mt-5")}>{children}</div>
          </div>
          {rodape && <div className="flex flex-wrap items-center gap-2 border-t border-line bg-surface px-[26px] py-4">{rodape}</div>}
        </motion.section>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Rótulo de campo no estilo do protótipo (12px, espaço acima). Use com <Input>/<NativeSelect>/<Textarea>. */
export function CampoDrawer({
  rotulo,
  obrigatorio,
  dica,
  erro,
  htmlFor,
  children,
}: {
  rotulo: string;
  obrigatorio?: boolean;
  dica?: React.ReactNode;
  erro?: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-[17px] first:mt-0">
      <label htmlFor={htmlFor} className="mb-[7px] block text-xs">
        {rotulo}
        {obrigatorio && " *"}
      </label>
      {children}
      {erro ? <p className="mt-1 text-xs text-danger-ink">{erro}</p> : dica ? <p className="mt-1 text-xs text-muted">{dica}</p> : null}
    </div>
  );
}
