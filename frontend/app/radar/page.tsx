"use client";

import useSWR from "swr";
import { apiGet, BackendOfflineError } from "@/lib/api";
import { BackendOffline } from "@/components/BackendOffline";

type RadarMeta = Record<string, unknown>;

export default function RadarPage() {
  const { data, error, isLoading } = useSWR<RadarMeta>(
    "/api/radar/meta",
    apiGet
  );

  if (error instanceof BackendOfflineError) {
    return <BackendOffline />;
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="text-muted-foreground">Carregando...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="text-destructive">{error.message}</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold">Radar</h1>
      <pre className="mt-4 text-sm text-muted-foreground">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
