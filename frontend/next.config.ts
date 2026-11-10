import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // deploy/deploy.sh compila em .next-novo (NEXT_DIST_DIR) com o site no ar e só troca a pasta se o build passar.
  // Em execução (`next start`) a variável não existe: vale a .next.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Cabeçalhos de segurança (o nginx repete os principais; aqui valem também em `next start` direto).
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  // App autenticado e renderizado no cliente: sem cache de componentes no servidor.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
