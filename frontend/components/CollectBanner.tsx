"use client";

import { useRef } from "react";
import useSWR, { useSWRConfig } from "swr";
import { apiGet } from "@/lib/api";

type CollectStatus = {
  running: boolean;
  phase: "coleta" | "notas" | null;
  current: string | null;
  done: number;
  total: number;
};

// Faixa discreta embaixo do menu enquanto a coleta roda (inclusive a automática, que começa
// sozinha ~30 s depois de abrir o app). Quando termina, todas as telas recarregam os dados:
// ninguém precisa adivinhar que tem que apertar F5.
export function CollectBanner() {
  const { mutate } = useSWRConfig();
  const wasRunning = useRef(false);
  const { data } = useSWR<CollectStatus>("/api/collect/status", apiGet, {
    refreshInterval: (latest) => (latest?.running ? 2500 : 10000),
    onSuccess: (status) => {
      if (wasRunning.current && !status.running) {
        mutate((key) => typeof key === "string" && key !== "/api/collect/status");
      }
      wasRunning.current = status.running;
    },
  });

  if (!data?.running) return null;
  const text =
    data.phase === "notas"
      ? "Calculando as notas dos temas…"
      : data.total > 0
        ? `Coletando dados: ${Math.min(data.done + 1, data.total)} de ${data.total} fontes${data.current ? ` (${data.current})` : ""}…`
        : "Começando a coleta…";

  return (
    <div role="status" aria-live="polite" className="mx-auto w-full max-w-6xl px-4 sm:px-8">
      <p className="flex items-center gap-3 rounded-full bg-card px-4 py-2 text-sm text-muted-foreground">
        <span aria-hidden="true" className="size-2 animate-pulse rounded-full bg-primary" />
        <span>
          {text} <span className="hidden sm:inline">As telas se atualizam sozinhas quando terminar.</span>
        </span>
      </p>
    </div>
  );
}
