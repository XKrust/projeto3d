"use client";

import { Suspense } from "react";
import useSWR from "swr";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { apiGet, BackendOfflineError } from "@/lib/api";
import { BackendOffline } from "@/components/BackendOffline";
import { useCountry } from "@/lib/country";
import { HypeHero } from "@/components/hype/HypeHero";
import { ReleaseRow } from "@/components/hype/ReleaseRow";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { KIND_FILTER_LABELS, type HypeResponse } from "@/lib/hype-types";

const ALL_KINDS = "todos";

function Loading() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <p className="text-muted-foreground">Carregando…</p>
    </div>
  );
}

function KindSelect() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const kind = searchParams.get("kind") || ALL_KINDS;

  function change(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === ALL_KINDS) {
      params.delete("kind");
    } else {
      params.set("kind", value);
    }
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <Select items={KIND_FILTER_LABELS} value={kind} onValueChange={(value) => change(String(value))}>
      <SelectTrigger aria-label="Tipo">
        <SelectValue placeholder="Tipo" />
      </SelectTrigger>
      <SelectContent>
        {Object.entries(KIND_FILTER_LABELS).map(([value, label]) => (
          <SelectItem key={value} value={value}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function HypeContent() {
  const searchParams = useSearchParams();
  const country = useCountry();
  const kind = searchParams.get("kind");
  const query = new URLSearchParams({ country: country ?? "" });
  if (kind) {
    query.set("kind", kind);
  }

  const { data, error, isLoading } = useSWR<HypeResponse>(country ? `/api/hype?${query}` : null, apiGet);

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

  const ranked = [...data.releases].sort((a, b) => b.opportunity - a.opportunity);
  const [leader, ...rest] = ranked;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-14 px-4 sm:px-8">
      {leader ? (
        <HypeHero release={leader} />
      ) : (
        <section className="flex flex-col gap-4 py-8">
          <h1 className="text-[length:var(--text-display)] font-bold">Nenhuma estreia ainda.</h1>
          <p className="max-w-[62ch] text-[length:var(--text-md)] text-muted-foreground">
            O AniList não precisa de chave: clique em “Coletar agora” no Radar. Para filmes,
            séries e jogos, cole as chaves do TMDB e do IGDB em Configurações.
          </p>
        </section>
      )}

      <section
        aria-label="Filtros"
        className="flex flex-wrap items-center gap-2 rounded-[var(--radius-card)] bg-card p-3 sm:p-4"
      >
        <KindSelect />
      </section>

      {rest.length > 0 && (
        <section aria-labelledby="estreias-titulo" className="flex flex-col gap-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="estreias-titulo" className="text-[length:var(--text-xl)] font-bold">
              Próximas estreias
            </h2>
            <p className="text-sm text-muted-foreground">
              Nota de oportunidade (estimativa), da maior para a menor
            </p>
          </div>
          <ol className="flex flex-col border-b border-border">
            {rest.map((release, index) => (
              <ReleaseRow key={release.id} release={release} rank={index + 2} />
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

export default function HypePage() {
  return (
    <Suspense fallback={<Loading />}>
      <HypeContent />
    </Suspense>
  );
}
