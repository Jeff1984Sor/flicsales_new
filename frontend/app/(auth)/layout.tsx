"use client";

import { ArrowLeftRight, Sparkles, ShieldCheck, Target } from "lucide-react";
import { motion } from "motion/react";

import { Assinatura, FlicLogo, MarcaLogo } from "@/components/flic/brand";
import { FaixaAmbiente } from "@/components/flic/shell";

const DESTAQUES = [
  { i: Target, t: "Comercial com contexto", d: "Oportunidades, atividades e propostas com a próxima ação sempre visível." },
  { i: ArrowLeftRight, t: "Da venda ao caixa", d: "Venda ≠ recebimento ≠ caixa. Recebíveis nascem em rascunho para revisão." },
  { i: Sparkles, t: "IA unificada", d: "Uma conversa, todos os contextos — com evidência, fonte e limite." },
  { i: ShieldCheck, t: "Seguro por padrão", d: "Acesso por perfil e histórico de cada ação." },
];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh pt-(--faixa) lg:grid-cols-[1.05fr_1fr]">
      <FaixaAmbiente />
      {/* painel da marca: lateral escura do produto */}
      <aside className="relative hidden overflow-hidden bg-sidebar text-white lg:flex lg:flex-col">
        <div className="absolute -top-32 -left-32 size-112 rounded-full bg-primary/30 blur-[110px]" />
        <div className="absolute -right-24 bottom-0 size-96 rounded-full bg-accent/15 blur-[100px]" />
        <div className="relative flex flex-1 flex-col justify-between p-12">
          <FlicLogo claro />

          <div className="max-w-lg">
            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="mb-6 text-[10px] font-bold tracking-[1.6px] text-accent"
            >
              ORQUESTRAÇÃO COMERCIAL + FINANCEIRA
            </motion.p>
            <motion.h1
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.08 }}
              className="text-4xl leading-[1.1] font-bold tracking-tight xl:text-5xl"
            >
              Um contexto. <span className="text-electric">Próxima ação.</span>
            </motion.h1>
            <div className="mt-10 space-y-4">
              {DESTAQUES.map((d, k) => (
                <motion.div
                  key={d.t}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.25 + k * 0.1 }}
                  className="flex gap-3"
                >
                  <div className="grid size-9 shrink-0 place-items-center rounded-[8px] bg-white/8 ring-1 ring-white/10">
                    <d.i className="size-4 text-accent" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{d.t}</p>
                    <p className="text-sm text-sidebar-foreground">{d.d}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
          <p className="text-xs text-sidebar-foreground">Vendas, recebimentos e caixa conectados, sem duplicar cadastro.</p>
        </div>
      </aside>

      {/* formulário */}
      <main className="relative flex flex-col bg-bg">
        <div className="relative flex flex-1 items-center justify-center px-5 py-12">
          <div className="w-full max-w-sm">
            <MarcaLogo className="mb-8 lg:hidden" />
            {children}
          </div>
        </div>
        <footer className="relative flex justify-center pb-6 text-muted">
          <Assinatura />
        </footer>
      </main>
    </div>
  );
}
