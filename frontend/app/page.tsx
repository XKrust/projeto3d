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
  chance: number | null;
  top_topic: string | null;
  topics: number;
};

// Tela inicial: escolher o país. Ao lado de cada um, a chance de venda estimada
// (média da nota de oportunidade dos 5 melhores tópicos — ver docs/score.md).
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
          Escolha o país. Radar, Sazonal e Hype passam a mostrar o que vende lá. A
          porcentagem é a chance de venda estimada dos 5 temas mais fortes de cada país.
        </p>
      </header>

      {isLoading || !data ? (
        <p className="text-muted-foreground">{error ? error.message : "Carregando…"}</p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[...data]
            .sort((a, b) => Number(b.active) - Number(a.active) || (b.chance ?? -1) - (a.chance ?? -1))
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
                  <span className="flex items-baseline gap-2">
                    <span className="tnum font-heading text-[length:var(--text-2xl)] font-extrabold leading-none tracking-[-0.04em]">
                      {country.chance === null ? "—" : `${country.chance}%`}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      chance de venda (estimativa)
                    </span>
                  </span>
                  <span className="w-full truncate text-sm text-muted-foreground">
                    {!country.active
                      ? "Ative em Configurações"
                      : country.top_topic
                        ? `Melhor tema: ${country.top_topic}`
                        : "Ainda sem dados — clique em Coletar agora"}
                  </span>
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
                      aria-label={`${country.name}: ${country.chance === null ? "sem dados" : `${country.chance}% de chance de venda (estimativa)`}`}
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
