"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, ImageUp, Loader2, RotateCcw, Save, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";

import { rotaAusente } from "@/components/cadastros/consultas";
import { Field } from "@/components/flic/form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useFoto } from "@/hooks/use-foto";
import { api } from "@/lib/api";
import { resolverLogo, useBrand } from "@/lib/brand";
import { iniciais } from "@/lib/format";
import type { IdentidadeOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const PRESETS = [
  { n: "Azul FlicSales", c: "#0057D9" },
  { n: "Navy", c: "#1E2D6B" },
  { n: "Marsala", c: "#B0486B" },
  { n: "Vinho", c: "#4A1A2C" },
  { n: "Teal", c: "#1A8F5E" },
  { n: "Amber", c: "#F5A623" },
  { n: "Red", c: "#C94343" },
];

function Preview({ nome, cor, logo }: { nome: string; cor: string; logo: string | null }) {
  return (
    <div className="overflow-hidden rounded-2xl border shadow-lg" style={{ ["--brand" as string]: cor }}>
      <div className="flex h-56">
        <div className="relative flex w-40 flex-col gap-1.5 overflow-hidden bg-ink p-2.5">
          <div className="absolute -top-10 -left-10 size-28 rounded-full blur-2xl" style={{ background: `${cor}55` }} />
          <div className="relative mb-2 flex items-center gap-2">
            <div className="grid size-7 place-items-center overflow-hidden rounded-lg text-[10px] font-bold text-white bg-primary">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {logo ? <img src={logo} alt="" className="size-full bg-white object-contain p-0.5" /> : iniciais(nome)}
            </div>
            <span className="truncate text-[11px] font-semibold text-white">{nome}</span>
          </div>
          {["Painel", "Nova emissão", "Lotes", "Notas"].map((x, i) => (
            <div
              key={x}
              className={cn("relative rounded-md px-2 py-1.5 text-[10px] text-white/70", i === 1 && "text-white")}
              style={i === 1 ? { background: `linear-gradient(90deg, ${cor}40, ${cor}0d)`, boxShadow: `inset 0 0 0 1px ${cor}55` } : undefined}
            >
              {x}
            </div>
          ))}
        </div>
        <div className="flex flex-1 flex-col bg-background">
          <div className="flex h-9 items-center gap-2 border-b bg-card/70 px-3">
            <div className="flex h-5 flex-1 items-center gap-1 rounded border bg-background px-1.5 text-[9px] text-muted-foreground">
              <Search className="size-2.5" /> Buscar…
            </div>
            <Bell className="size-3 text-muted-foreground" />
            <div className="size-5 rounded-full bg-primary" />
          </div>
          <div className="flex-1 space-y-2 p-3">
            <div className="h-2.5 w-24 rounded bg-foreground/80" />
            <div className="grid grid-cols-3 gap-1.5">
              {[0, 1, 2].map((i) => (
                <div key={i} className="rounded-md border bg-card p-1.5">
                  <div className="h-1.5 w-8 rounded bg-subtle" />
                  <div className="mt-1 h-2.5 w-10 rounded bg-foreground/70" />
                </div>
              ))}
            </div>
            <div className="flex h-14 items-end gap-1 rounded-md border bg-card p-1.5">
              {[30, 55, 40, 70, 60, 85, 75].map((h, i) => (
                <div key={i} className="flex-1 rounded-sm" style={{ height: `${h}%`, background: cor, opacity: 0.4 + i * 0.08 }} />
              ))}
            </div>
            <div className="inline-flex rounded-md px-2 py-1 text-[9px] font-medium text-white bg-primary">Emitir 309 notas</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Saída da identidade com a imagem da assinatura geral (campo novo; ausente enquanto o backend não publicar). */
type IdentidadeComImagem = IdentidadeOut & { assinatura_imagem_url?: string | null };

const MSG_IMAGEM_INDISPONIVEL = "Imagem da assinatura ainda indisponível no servidor. Tente mais tarde.";

function erroImagem(e: unknown) {
  toast.error(rotaAusente(e) ? MSG_IMAGEM_INDISPONIVEL : e instanceof Error ? e.message : "Não foi possível salvar a imagem.");
}

/** Imagem da assinatura geral (PNG/JPG até 1 MB): vai nos e-mails que usam a assinatura padrão da organização. */
function ImagemAssinaturaGeral({ url, texto }: { url: string | null; texto: string }) {
  const qc = useQueryClient();
  const imagem = useFoto(url);
  const atualizar = () => {
    qc.invalidateQueries({ queryKey: ["identidade"] });
  };
  const enviar = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("arquivo", f);
      return api.post<IdentidadeComImagem>("/config/identidade/assinatura-imagem", fd);
    },
    meta: { silencioso: true },
    onSuccess: () => {
      atualizar();
      toast.success("Imagem da assinatura atualizada");
    },
    onError: erroImagem,
  });
  const remover = useMutation({
    mutationFn: () => api.del<IdentidadeComImagem>("/config/identidade/assinatura-imagem"),
    meta: { silencioso: true },
    onSuccess: () => {
      atualizar();
      toast.success("Imagem da assinatura removida");
    },
    onError: erroImagem,
  });
  const dz = useDropzone({
    multiple: false,
    noClick: true,
    noKeyboard: true,
    accept: { "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"] },
    maxSize: 1024 * 1024,
    onDrop: (f) => f[0] && enviar.mutate(f[0]),
    onDropRejected: () => toast.error("Use PNG ou JPG de até 1 MB."),
  });
  const temImagem = !!url;
  return (
    <div className="space-y-3">
      <div {...dz.getRootProps()} className="flex flex-wrap items-center gap-2">
        <input {...dz.getInputProps()} />
        <Button type="button" variant="outline" onClick={dz.open} disabled={enviar.isPending}>
          {enviar.isPending ? <Loader2 className="animate-spin" /> : <ImageUp />} {temImagem ? "Trocar imagem" : "Enviar imagem"}
        </Button>
        {temImagem && (
          <Button type="button" variant="ghost" className="text-danger-ink" onClick={() => remover.mutate()} disabled={remover.isPending}>
            <Trash2 /> Remover imagem
          </Button>
        )}
        <span className="text-xs text-muted">PNG ou JPG até 1 MB (logo, selo ou assinatura escaneada).</span>
      </div>
      <div>
        <span className="eyebrow">PRÉVIA DA ASSINATURA PADRÃO</span>
        <div className="mt-2 rounded-[10px] border border-line bg-subtle/40 p-4 text-sm">
          {!texto.trim() && !temImagem ? (
            <p className="text-muted">Sem assinatura padrão: os e-mails saem só com o texto da mensagem.</p>
          ) : (
            <>
              <p className="text-muted">—</p>
              {texto.trim() && <p className="whitespace-pre-line">{texto}</p>}
              {temImagem &&
                (imagem ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={imagem} alt="Imagem da assinatura geral" className="mt-3 max-h-24 max-w-[260px] object-contain" />
                ) : (
                  <p className="mt-3 text-xs text-muted">Carregando imagem…</p>
                ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function IdentidadePage() {
  const qc = useQueryClient();
  const brand = useBrand();
  const q = useQuery({ queryKey: ["identidade"], queryFn: () => api.get<IdentidadeComImagem>("/config/identidade") });
  const [nome, setNome] = useState("");
  const [cor, setCor] = useState("#7C8FFF");
  const [usarCor, setUsarCor] = useState(false);
  const [assinatura, setAssinatura] = useState("");
  const [logoLocal, setLogoLocal] = useState<string | null>(null);

  /* eslint-disable react-hooks/set-state-in-effect -- carrega o formulário com os dados do servidor */
  useEffect(() => {
    if (!q.data) return;
    setNome(q.data.nome_exibicao);
    setUsarCor(!!q.data.cor_destaque);
    setCor(q.data.cor_destaque ?? "#7C8FFF");
    setAssinatura(q.data.assinatura_email ?? "");
  }, [q.data]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // pré-visualização ao vivo em todo o app; volta ao salvo ao sair da página
  const { preview } = brand;
  useEffect(() => {
    if (q.data) preview(usarCor ? cor : null);
  }, [cor, usarCor, q.data, preview]);
  useEffect(() => () => preview(undefined), [preview]);

  const salvar = useMutation({
    mutationFn: () =>
      api.put<IdentidadeOut>("/config/identidade", {
        nome_exibicao: nome,
        cor_destaque: usarCor ? cor.toLowerCase() : null,
        assinatura_email: assinatura || null,
      }),
    onSuccess: () => {
      toast.success("Identidade salva — já aparece no login e nos e-mails");
      qc.invalidateQueries({ queryKey: ["identidade"] });
      qc.invalidateQueries({ queryKey: ["identidade-publica"] });
    },
  });

  const enviarLogo = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("arquivo", f);
      return api.post("/config/identidade/logo", fd);
    },
    onSuccess: () => {
      toast.success("Logo atualizado");
      qc.invalidateQueries({ queryKey: ["identidade"] });
      qc.invalidateQueries({ queryKey: ["identidade-publica"] });
    },
  });
  const dz = useDropzone({
    multiple: false,
    accept: { "image/png": [".png"], "image/svg+xml": [".svg"] },
    maxSize: 2 * 1024 * 1024,
    onDrop: (fs) => {
      const f = fs[0];
      if (!f) return;
      setLogoLocal(URL.createObjectURL(f));
      enviarLogo.mutate(f);
    },
    onDropRejected: () => toast.error("Use PNG ou SVG de até 2 MB."),
  });

  if (q.isPending) return <Skeleton className="h-96 rounded-2xl" />;
  const logo = logoLocal ?? resolverLogo(q.data?.logo_url);

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_440px]">
      <div className="space-y-6">
        <div className="card-surface p-5">
          <h3 className="font-semibold">Logo</h3>
          <p className="text-sm text-muted-foreground">PNG transparente ou SVG. Pré-visualização em fundo claro e escuro.</p>
          <p className="mt-2 mb-4 flex items-center gap-2 rounded-lg bg-brand/8 px-3 py-2 text-sm">
            <ImageUp className="size-4 shrink-0 text-info-ink" />
            Este logo aparece no sistema, no login, nos e-mails e nos documentos.
          </p>
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <div className="grid h-28 place-items-center rounded-xl border bg-[#F7F8FC] p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {logo ? <img src={logo} alt="Logo no claro" className="max-h-16 max-w-full object-contain" /> : <span className="text-xs text-[#0F1729]/50">sem logo</span>}
            </div>
            <div className="grid h-28 place-items-center rounded-xl border bg-[#0F1729] p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {logo ? <img src={logo} alt="Logo no escuro" className="max-h-16 max-w-full object-contain" /> : <span className="text-xs text-white/50">sem logo</span>}
            </div>
            <div
              {...dz.getRootProps()}
              className={cn(
                "grid h-28 cursor-pointer place-items-center rounded-xl border-2 border-dashed px-6 text-center text-sm transition-colors sm:w-40",
                dz.isDragActive ? "border-brand bg-brand/5" : "hover:border-brand/50",
              )}
            >
              <input {...dz.getInputProps()} />
              {enviarLogo.isPending ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <span className="flex flex-col items-center gap-1 text-muted-foreground">
                  <ImageUp className="size-5" />
                  Enviar logo
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="card-surface space-y-4 p-5">
          <Field label="Nome do cliente" dica="Exibido no sistema, no login e nos e-mails.">
            <Input value={nome} onChange={(e) => setNome(e.target.value)} />
          </Field>
          <Field label="Cor de destaque (opcional)" dica="Sem cor própria, usamos o azul FlicSales.">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setUsarCor(false)}
                className={cn(
                  "h-9 rounded-lg border px-3 text-sm transition",
                  !usarCor ? "border-brand bg-brand/10 font-medium" : "text-muted-foreground hover:bg-subtle",
                )}
              >
                Padrão FlicSales
              </button>
              {PRESETS.map((p) => (
                <button
                  key={p.c}
                  type="button"
                  title={p.n}
                  onClick={() => {
                    setUsarCor(true);
                    setCor(p.c);
                  }}
                  className={cn(
                    "size-9 rounded-lg ring-offset-2 ring-offset-background transition hover:scale-105",
                    usarCor && cor.toLowerCase() === p.c.toLowerCase() && "ring-2 ring-foreground",
                  )}
                  style={{ background: p.c }}
                />
              ))}
              <label className="relative flex h-9 items-center gap-2 rounded-lg border px-2">
                <input
                  type="color"
                  value={cor}
                  onChange={(e) => {
                    setUsarCor(true);
                    setCor(e.target.value);
                  }}
                  className="size-6 cursor-pointer rounded border-0 bg-transparent p-0"
                />
                <span className="font-mono text-xs uppercase">{cor}</span>
              </label>
            </div>
          </Field>
          <Field label="Assinatura padrão (quando o usuário não tem a sua)" dica="Vai no fim dos e-mails do sistema e dos usuários que não cadastraram a própria em Minha conta.">
            <Textarea rows={4} value={assinatura} onChange={(e) => setAssinatura(e.target.value)} placeholder={"Atenciosamente,\nEquipe comercial"} />
          </Field>
          <Field label="Imagem da assinatura geral" dica="Vai junto da assinatura padrão, como a imagem que cada usuário pode cadastrar em Minha conta.">
            <ImagemAssinaturaGeral url={q.data?.assinatura_imagem_url ?? null} texto={assinatura} />
          </Field>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button
              variant="ghost"
              onClick={() => {
                if (!q.data) return;
                setNome(q.data.nome_exibicao);
                setUsarCor(!!q.data.cor_destaque);
                setCor(q.data.cor_destaque ?? "#7C8FFF");
                setAssinatura(q.data.assinatura_email ?? "");
              }}
            >
              <RotateCcw /> Desfazer
            </Button>
            <Button onClick={() => salvar.mutate()} disabled={salvar.isPending || nome.trim().length < 2}>
              {salvar.isPending ? <Loader2 className="animate-spin" /> : <Save />} Salvar identidade
            </Button>
          </div>
        </div>
      </div>

      <div className="space-y-3 xl:sticky xl:top-[calc(var(--tb)+var(--faixa)+24px)] xl:h-fit">
        <p className="text-sm font-medium">Pré-visualização ao vivo</p>
        <Preview nome={nome || "Cliente"} cor={usarCor ? cor : "#7C8FFF"} logo={logo} />
        <p className="text-xs text-muted-foreground">A cor já está aplicada em todo o sistema enquanto você edita. Salve para valer para todos.</p>
      </div>
    </div>
  );
}
