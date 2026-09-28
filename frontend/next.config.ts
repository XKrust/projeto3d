import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // O proxy de /api corta em 30 s por padrão; a análise (2 chamadas à IA + referências) e a
  // venda (anúncio + capa) passam disso. 3 minutos cobre o pior caso sem deixar pendurado.
  experimental: {
    proxyTimeout: 180_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
