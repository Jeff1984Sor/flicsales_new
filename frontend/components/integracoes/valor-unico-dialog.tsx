"use client";

import { Check, Copy, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

/**
 * Mostra um segredo recém-gerado (token de API, token do webhook) UMA ÚNICA VEZ.
 * Depois de fechar não há como ver o valor de novo: só gerar outro.
 */
export function ValorUnicoDialog({
  valor,
  titulo,
  descricao,
  onClose,
}: {
  valor: string | null;
  titulo: string;
  descricao: React.ReactNode;
  onClose: () => void;
}) {
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    if (!valor) return;
    try {
      await navigator.clipboard.writeText(valor);
      setCopiado(true);
      toast.success("Copiado para a área de transferência");
    } catch {
      toast.error("Não foi possível copiar. Selecione o texto e copie manualmente.");
    }
  };
  return (
    <Dialog
      open={!!valor}
      onOpenChange={(o) => {
        if (!o) {
          setCopiado(false);
          onClose();
        }
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{titulo}</DialogTitle>
          <DialogDescription>{descricao}</DialogDescription>
        </DialogHeader>
        <div className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3.5 py-2.5 text-sm text-warning-ink">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <span>Copie agora. Por segurança este valor não é guardado e não poderá ser visto de novo.</span>
        </div>
        <div className="flex items-center gap-2">
          <code className="min-w-0 flex-1 rounded-lg border bg-subtle/50 px-3 py-2 font-mono text-xs break-all select-all">{valor}</code>
          <Button type="button" variant="outline" onClick={copiar} aria-label="Copiar valor">
            {copiado ? <Check /> : <Copy />} {copiado ? "Copiado" : "Copiar"}
          </Button>
        </div>
        <DialogFooter>
          <Button onClick={onClose}>Já copiei, fechar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
