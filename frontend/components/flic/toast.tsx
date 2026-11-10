"use client";

/**
 * Toast — avisos curtos (sonner), no estilo do protótipo: faixa escura centralizada embaixo.
 *  - `notificar("Oportunidade criada")`          aviso neutro
 *  - `notificar.sucesso / .erro / .info(...)`     variações
 *  - `<FlicToaster />`                            já montado em components/providers.tsx
 * Erros de API viram toast sozinhos (QueryCache/MutationCache); use `meta: { silencioso: true }` para tratar na tela.
 */
import { Toaster, toast } from "sonner";

export const notificar = Object.assign((mensagem: string) => toast(mensagem), {
  sucesso: (mensagem: string) => toast.success(mensagem),
  erro: (mensagem: string) => toast.error(mensagem),
  info: (mensagem: string) => toast.info(mensagem),
});

export function FlicToaster() {
  return (
    <Toaster
      position="bottom-center"
      closeButton
      toastOptions={{
        classNames: {
          toast: "rounded-[9px]! border-0! bg-sidebar! text-white! shadow-xl! px-[25px]! py-[15px]!",
          description: "text-sidebar-foreground!",
          closeButton: "bg-sidebar! text-white! border-sidebar-border!",
          success: "[&_[data-icon]]:text-accent!",
          error: "[&_[data-icon]]:text-amber!",
        },
      }}
    />
  );
}
