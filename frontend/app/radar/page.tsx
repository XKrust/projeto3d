"use client";

import { Suspense, useState } from "react";
import useSWR from "swr";
import { useSearchParams } from "next/navigation";
import { apiGet, apiPost, BackendOfflineError } from "@/lib/api";
import { BackendOffline } from "@/components/BackendOffline";
import { Filters } from "@/components/radar/Filters";
import { RadarHero } from "@/components/radar/RadarHero";
import { TopicCard } from "@/components/radar/TopicCard";
import { Button } from "@/components/ui/button";
import type { CollectResponse, RadarMeta, Topic } from "@/lib/radar-types";

const COLLECT_REFRESH_DELAY_MS = 5000;

function buildRadarQuery(searchParams: URLSearchParams): string {
  const params = new URLSearchParams();
  params.set("country", searchParams.get("country") || "BR");
  for (const key of ["platform", "market", "category"]) {
    const value = searchParams.get(key);
    if (value) {
      params.set(key, value);
    }
  }
  return params.toString();
}

function Loading() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <p className="text-muted-foreground">Carregando…</p>
    </div>
  );
}

function RadarContent() {
  const searchParams = useSearchParams();
  const [collectMessage, setCollectMessage] = useState<string | null>(null);
  const [collecting, setCollecting] = useState(false);

  const {
    data: meta,
    error: metaError,
    isLoading: metaLoading,
  } = useSWR<RadarMeta>("/api/radar/meta", apiGet);

  const radarQuery = buildRadarQuery(searchParams);
  const {
    data: topics,
    error: topicsError,
    isLoading: topicsLoading,
    mutate,
  } = useSWR<Topic[]>(`/api/radar?${radarQuery}`, apiGet);

  if (
    metaError instanceof BackendOfflineError ||
    topicsError instanceof BackendOfflineError
  ) {
    return <BackendOffline />;
  }

  if (metaLoading || topicsLoading) {
    return <Loading />;
  }

  if (metaError || topicsError) {
    const message = (metaError ?? topicsError)?.message ?? "Erro inesperado";
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="text-destructive">{message}</p>
      </div>
    );
  }

  async function handleCollect() {
    setCollecting(true);
    try {
      const result = await apiPost<CollectResponse>("/api/collect");
      setCollectMessage(result.message);
      if (result.started) {
        setTimeout(() => {
          mutate();
        }, COLLECT_REFRESH_DELAY_MS);
      }
    } catch (err) {
      setCollectMessage(
        err instanceof Error ? err.message : "Erro inesperado"
      );
    } finally {
      setCollecting(false);
    }
  }

  const country = searchParams.get("country") || "BR";
  const [leader, ...rest] = topics ?? [];

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-14 px-4 sm:px-8">
      {leader ? (
        <RadarHero topic={leader} country={country} />
      ) : (
        <section className="flex flex-col gap-4 py-8">
          <h1 className="text-[length:var(--text-display)] font-bold">
            O radar ainda está vazio.
          </h1>
          <p className="max-w-[60ch] text-[length:var(--text-md)] text-muted-foreground">
            Nenhum tópico ainda. Clique em &#8220;Coletar agora&#8221; ou
            configure suas chaves em Configurações.
          </p>
        </section>
      )}

      <section
        aria-label="Filtros e coleta"
        className="flex flex-col gap-4 rounded-[var(--radius-card)] bg-card p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4"
      >
        {meta && <Filters meta={meta} />}
        <div className="flex flex-col items-start gap-1 sm:items-end">
          <Button
            onClick={handleCollect}
            disabled={collecting}
            className="h-9 rounded-full px-5"
          >
            {collecting ? "Iniciando…" : "Coletar agora"}
          </Button>
          {collectMessage && (
            <p role="status" className="text-sm text-muted-foreground">
              {collectMessage}
            </p>
          )}
        </div>
      </section>

      {rest.length > 0 && (
        <section aria-labelledby="ranking-titulo" className="flex flex-col gap-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2
              id="ranking-titulo"
              className="text-[length:var(--text-xl)] font-bold"
            >
              Na fila do radar
            </h2>
            <p className="text-sm text-muted-foreground">
              Nota de oportunidade (estimativa), da maior para a menor
            </p>
          </div>
          <ol className="flex flex-col border-b border-border">
            {rest.map((topic, index) => (
              <TopicCard key={topic.topic_id} topic={topic} rank={index + 2} />
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

export default function RadarPage() {
  return (
    <Suspense fallback={<Loading />}>
      <RadarContent />
    </Suspense>
  );
}
