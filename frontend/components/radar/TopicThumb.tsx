"use client";

import { useState } from "react";

// Miniatura do tema. Sem imagem (ou se a imagem de outro site não carregar), mostra a
// inicial do tema num quadrado nas cores do app, em vez de um ícone de "imagem quebrada".
export function TopicThumb({ name, src, className }: { name: string; src: string | null; className: string }) {
  const [failed, setFailed] = useState(false);
  if (src && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- miniaturas vêm de domínios arbitrários
      <img src={src} alt="" className={`${className} object-cover`} onError={() => setFailed(true)} />
    );
  }
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <div
      aria-hidden="true"
      className={`${className} flex shrink-0 items-center justify-center bg-[radial-gradient(circle_at_30%_20%,var(--color-accent-halo),var(--color-paper-3))] font-heading font-extrabold text-[var(--color-accent-strong)]`}
    >
      <span className="text-[1.6em] leading-none">{initial}</span>
    </div>
  );
}
