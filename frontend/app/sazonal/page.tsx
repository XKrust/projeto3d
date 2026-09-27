"use client";

import { Suspense } from "react";
import useSWR from "swr";
import { apiGet, BackendOfflineError } from "@/lib/api";
import { BackendOffline } from "@/components/BackendOffline";
import { useCountry } from "@/lib/country";
import { EventRow } from "@/components/sazonal/EventRow";
import { SeasonHero } from "@/components/sazonal/SeasonHero";
import type { SeasonalResponse } from "@/lib/sazonal-types";

function Loading() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <p className="text-muted-foreground">Carregando…</p>
    </div>
  );
}

function SazonalContent() {
  const country = useCountry();
  const { data, error, isLoading } = useSWR<SeasonalResponse>(
    country ? `/api/seasonal?country=${country}` : null,
    apiGet
  );

  if (error instanceof BackendOfflineError) {
    return <BackendOffline />;
  }
  if (!country || isLoading || !data) {
    return error ? (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="text-destructive">{error.message}</p>
      </div>
    ) : (
      <Loading />
    );
  }

  const leader = data.events.find((e) => e.status !== "atrasado") ?? data.events[0];

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-14 px-4 sm:px-8">
      {leader && (
        <SeasonHero
          event={leader}
          country={country}
          leadDays={data.lead_days}
          modelingDays={data.modeling_days}
        />
      )}

      <section aria-labelledby="calendario-titulo" className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 id="calendario-titulo" className="text-[length:var(--text-xl)] font-bold">
              Calendário
            </h2>
            <p className="text-sm text-muted-foreground">
              Ordenado pelo dia de começar a modelar. Ajuste os prazos em Configurações.
            </p>
          </div>
        </div>
        <ol className="flex flex-col border-b border-border">
          {data.events.map((event) => (
            <EventRow key={event.slug} event={event} />
          ))}
        </ol>
      </section>
    </div>
  );
}

export default function SazonalPage() {
  return (
    <Suspense fallback={<Loading />}>
      <SazonalContent />
    </Suspense>
  );
}
