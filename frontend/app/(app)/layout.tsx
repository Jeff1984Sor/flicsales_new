"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { ClientLogo } from "@/components/flic/brand";
import { AppShell } from "@/components/flic/shell";
import { useMontado } from "@/hooks/use-montado";
import { useAuth } from "@/lib/auth";

function TelaCarregando() {
  return (
    <div className="grid min-h-dvh place-items-center bg-bg">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-[10px] bg-electric/30" />
          <ClientLogo compacto className="relative size-12" />
        </div>
        <div className="h-1 w-32 overflow-hidden rounded-full bg-subtle">
          <div className="h-full w-full animate-shimmer bg-linear-to-r from-transparent via-electric to-transparent bg-size-[200%_100%]" />
        </div>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const montado = useMontado();
  const { logado, carregando } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // sem sessão (cookie ausente/expirado e não renovável): volta ao login
    if (montado && !carregando && !logado) router.replace(`/login?volta=${encodeURIComponent(pathname)}`);
  }, [montado, carregando, logado, router, pathname]);

  if (!montado || !logado || carregando) return <TelaCarregando />;
  return <AppShell>{children}</AppShell>;
}
