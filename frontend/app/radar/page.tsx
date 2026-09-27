"use client";

import { Suspense, useState } from "react";
import useSWR from "swr";
import { useSearchParams } from "next/navigation";
import { apiGet, apiPost, BackendOfflineError } from "@/lib/api";
import { BackendOffline } from "@/components/BackendOffline";
import { Filters } from "@/components/radar/Filters";
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
      <p className="text-muted-foreground">Carregando...</p>
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

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Radar</h1>
        <div className="flex flex-col items-end gap-1">
          <Button onClick={handleCollect} disabled={collecting}>
            Coletar agora
          </Button>
          {collectMessage && (
            <p className="text-sm text-muted-foreground">{collectMessage}</p>
          )}
        </div>
      </div>

      {meta && <Filters meta={meta} />}

      {!topics || topics.length === 0 ? (
        <p className="text-muted-foreground">
          Nenhum tópico ainda. Clique em &#8220;Coletar agora&#8221; ou
          configure suas chaves em Configurações.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topics.map((topic) => (
            <TopicCard key={topic.topic_id} topic={topic} />
          ))}
        </div>
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
