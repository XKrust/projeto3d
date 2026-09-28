"use client";

import { useRef } from "react";
import useSWR, { useSWRConfig } from "swr";
import { apiGet } from "@/lib/api";

type CollectStatus = {
  running: boolean;
  phase: "coleta" | "notas" | "concorrencia" | null;
  current: string | null;
  done: number;
  total: number;
  quiet?: boolean;
};

function describe(status: CollectStatus): string {
  if (status.phase === "concorrencia") {
    return "Radar atualizado. Agora medindo a concorrência nas lojas para afinar as notas (leva alguns minutos, pode usar o app normalmente).";
  }
  if (status.phase === "notas") return "Calculando as notas dos temas…";
  if (status.total > 0) {
    const n = Math.min(status.done + 1, status.total);
    return `Coletando dados: ${n} de ${status.total} fontes${status.current ? ` (${status.current})` : ""}… As telas se atualizam sozinhas.`;
  }
  return "Começando a coleta…";
}

// Faixa discreta embaixo do menu enquanto a coleta roda (inclusive a automática, que começa
// sozinha ~30 s depois de abrir o app). A cada mudança de fase (e no fim), todas as telas
// recarregam os dados: ninguém precisa adivinhar que tem que apertar F5. Ciclos em que
// nenhuma fonte está no horário (`quiet`) não mostram nada.
export function CollectBanner() {
  const { mutate } = useSWRConfig();
  const last = useRef<string>("");
  const { data } = useSWR<CollectStatus>("/api/collect/status", apiGet, {
    refreshInterval: (latest) => (latest?.running ? 2500 : 10000),
    onSuccess: (status) => {
      const key = status.running ? `${status.phase}` : "parado";
      if (last.current && key !== last.current) {
        mutate((k) => typeof k === "string" && k !== "/api/collect/status");
      }
      last.current = key;
    },
  });

  if (!data?.running || data.quiet) return null;
  const subtle = data.phase === "concorrencia";
  return (
    <div role="status" aria-live="polite" className="mx-auto w-full max-w-6xl px-4 sm:px-8">
      <p className="flex items-center gap-3 rounded-full bg-card px-4 py-2 text-sm text-muted-foreground">
        <span
          aria-hidden="true"
          className={`size-2 shrink-0 rounded-full ${subtle ? "bg-[var(--color-signal-up)]" : "animate-pulse bg-primary"}`}
        />
        <span>{describe(data)}</span>
      </p>
    </div>
  );
}
