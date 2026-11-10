import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Providers } from "@/components/providers";
import { EH_HML } from "@/lib/env";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const jetbrains = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "FlicSales OS",
  description: "Orquestração comercial e financeira com IA unificada. Um contexto. Próxima ação.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f8ff" },
    { media: "(prefers-color-scheme: dark)", color: "#070b16" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${inter.variable} ${jetbrains.variable} h-full antialiased`}>
      {EH_HML && (
        <head>
          {/* faixa de homologação antes da primeira pintura */}
          <script dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('ambiente-hml');" }} />
        </head>
      )}
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
