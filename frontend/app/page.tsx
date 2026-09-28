"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { apiGet, BackendOfflineError } from "@/lib/api";
import { saveCountry, useStoredCountry } from "@/lib/country";
import { BackendOffline } from "@/components/BackendOffline";
import { Flag } from "@/components/Flag";

type CountryCard = {
  code: string;
  name: string;
  active: boolean;
  /** Os 3 melhores temas do país agora (nomes). */
  top_topics: string[];
  /** As lojas que vendem com mais força no país. */
  stores: string[];
  topics: number;
};

// Tela inicial: escolher o país. Cada card mostra o que vende lá: os temas em alta e as
// lojas mais fortes (ver docs/score.md). Sem "% de chance": não diferenciava os países.
export default function Inicio() {
  const router = useRouter();
  const current = useStoredCountry();
  const { data, error, isLoading } = useSWR<CountryCard[]>("/api/countries", apiGet);

  if (error instanceof BackendOfflineError) {
    return <BackendOffline />;
  }

  function choose(code: string) {
    saveCountry(code);
    router.push(`/radar?country=${code}`);
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-4 sm:px-8">
      <header className="flex flex-col gap-3">
        <h1 className="text-[length:var(--text-display)] font-bold">Onde você vai vender?</h1>
        <p className="max-w-[58ch] text-[length:var(--text-md)] leading-snug text-muted-foreground">
          Escolha o país. Radar, Sazonal e Hype passam a mostrar o que vende lá. Em cada
          país: os temas em alta agora e as lojas onde mais se vende.
        </p>
      </header>

      {isLoading || !data ? (
        <p className="text-muted-foreground">{error ? error.message : "Carregando…"}</p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[...data]
            .sort((a, b) => Number(b.active) - Number(a.active) || b.topics - a.topics)
            .map((country) => {
              const selected = country.code === current;
              const card = (
                <>
                  <span className="flex w-full min-w-0 items-center gap-3">
                    <Flag
                      code={country.code}
                      className="h-9 w-13.5 shrink-0 rounded-md shadow-[0_0_0_1px_var(--color-rule)]"
                    />
                    <span className="min-w-0 truncate font-heading text-[length:var(--text-lg)] font-bold tracking-[-0.02em]">
                      {country.name}
                    </span>
                    {selected && (
                      <span className="ml-auto shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                        atual
                      </span>
                    )}
                  </span>
                  <span className="flex w-full flex-col gap-1">
                    <span className="text-xs uppercase tracking-[0.08em] text-muted-foreground">
                      Temas em alta
                    </span>
                    <span className="text-base font-medium leading-snug text-foreground">
                      {!country.active
                        ? "Ative em Configurações"
                        : country.top_topics.length
                          ? country.top_topics.join(" · ")
                          : "Ainda sem temas: clique em Coletar agora no Radar"}
                    </span>
                  </span>
                  {country.stores.length > 0 && (
                    <span className="flex w-full flex-col gap-1">
                      <span className="text-xs uppercase tracking-[0.08em] text-muted-foreground">
                        Onde mais se vende
                      </span>
                      <span className="text-sm text-muted-foreground">{country.stores.join(" · ")}</span>
                    </span>
                  )}
                </>
              );
              const base =
                "flex w-full flex-col items-start gap-3 rounded-[var(--radius-card)] bg-card p-5 text-left transition-colors duration-150";
              return (
                <li key={country.code}>
                  {country.active ? (
                    <button
                      type="button"
                      onClick={() => choose(country.code)}
                      aria-label={`${country.name}: ${country.top_topics.length ? `temas em alta ${country.top_topics.join(", ")}` : "ainda sem temas"}. Onde mais se vende: ${country.stores.join(", ")}`}
                      className={`${base} hover:bg-muted ${selected ? "ring-2 ring-primary" : ""}`}
                    >
                      {card}
                    </button>
                  ) : (
                    <Link
                      href="/config"
                      aria-label={`${country.name}: inativo, ative em Configurações`}
                      className={`${base} opacity-55 hover:opacity-80`}
                    >
                      {card}
                    </Link>
                  )}
                </li>
              );
            })}
        </ul>
      )}
    </div>
  );
}
