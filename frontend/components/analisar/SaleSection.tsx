"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { LaunchChecklist } from "@/components/analisar/LaunchChecklist";
import { CoverBlock } from "@/components/analisar/CoverBlock";
import { ListingCard } from "@/components/analisar/ListingCard";
import { PromotionBlock } from "@/components/analisar/PromotionBlock";
import { SaleSummary } from "@/components/analisar/SaleSummary";
import { StoreTable } from "@/components/analisar/StoreTable";
import { VariationsBlock } from "@/components/analisar/VariationsBlock";
import { Button } from "@/components/ui/button";
import { formatScore } from "@/lib/analyzer-types";
import { ApiError, apiGet, apiPostJson, apiPut, BackendOfflineError } from "@/lib/api";
import { formatUsd, salesToCover, type Sale, type SaleCountries } from "@/lib/sale-types";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <h4 className="font-heading text-[length:var(--text-md)] font-bold">{title}</h4>
      {children}
    </div>
  );
}

function HoursToCover({ sale }: { sale: Sale }) {
  const info = sale.hours_to_cover;
  const [rate, setRate] = useState(String(info?.hourly_rate_usd ?? 10));
  const [status, setStatus] = useState("");
  const { mutate } = useSWRConfig();
  if (!info) return null;
  const value = Number(rate.replace(",", "."));
  const sales = salesToCover(info.hours, value, info.price);

  async function save() {
    if (!(value >= 1 && value <= 1000)) {
      setStatus("Use um valor entre 1 e 1000.");
      return;
    }
    try {
      await apiPut("/api/settings", { hourly_rate_usd: value });
      // Atualiza o cache de /config, senão um "Salvar" lá devolveria o valor antigo.
      await mutate("/api/settings");
      setStatus("Valor da hora salvo.");
    } catch {
      setStatus("Não consegui salvar o valor da hora.");
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-[var(--radius-card)] bg-card p-5">
      <p>
        {sales === null ? (
          "—"
        ) : (
          <>
            <span className="tnum font-heading text-[length:var(--text-lg)] font-bold">≈ {sales} vendas</span>{" "}
            para cobrir as {info.hours.toLocaleString("pt-BR")} h de trabalho, a {formatUsd(info.price)} por venda
            (estimativa).
          </>
        )}
      </p>
      <label className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        Valor da sua hora (US$)
        <input
          inputMode="decimal"
          value={rate}
          onChange={(event) => setRate(event.target.value)}
          onBlur={save}
          className="tnum h-8 w-20 rounded-md border border-border bg-transparent px-2 text-foreground"
        />
        <span role="status">{status}</span>
      </label>
    </div>
  );
}

// Seção recolhida: o detalhe fica a um clique, para a venda não virar uma parede de texto.
function More({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <details className="group border-t border-border">
      <summary className="flex cursor-pointer list-none items-baseline justify-between gap-3 py-4 [&::-webkit-details-marker]:hidden">
        <span className="font-heading text-[length:var(--text-md)] font-bold">{title}</span>
        <span className="flex items-baseline gap-3 text-sm text-muted-foreground">
          {hint && <span className="hidden sm:inline">{hint}</span>}
          <span aria-hidden="true" className="transition-transform duration-150 group-open:rotate-90">›</span>
        </span>
      </summary>
      <div className="flex flex-col gap-4 pb-6">{children}</div>
    </details>
  );
}

function SaleResult({ sale }: { sale: Sale }) {
  const names = Object.fromEntries(
    sale.by_country.flatMap((c) => c.stores.map((s) => [s.platform, s.name] as const))
  );
  const storeCount = new Set(Object.keys(names)).size;
  return (
    <div className="flex flex-col gap-8">
      <SaleSummary sale={sale} />

      <Block title="Anúncio pronto">
        {sale.listing ? (
          <div className="grid gap-3 md:grid-cols-2">
            {sale.listing.listings.map((listing) => (
              <ListingCard
                key={`${listing.platform}-${listing.lang}`}
                listing={listing}
                storeName={names[listing.platform] ?? listing.platform}
              />
            ))}
          </div>
        ) : (
          <div role="note" className="flex flex-col gap-2 border-l-2 border-[var(--color-signal-mid)] pl-3">
            <p>{sale.listing_note}</p>
            {sale.listing_note?.includes("Configurações") && (
              <Link href="/config" className="text-sm underline underline-offset-4 hover:text-primary">
                Abrir Configurações
              </Link>
            )}
          </div>
        )}
      </Block>

      <div className="flex flex-col">
        <More title="Todas as lojas e preços" hint={`${storeCount} loja${storeCount === 1 ? "" : "s"} · ${sale.by_country.length} ${sale.by_country.length === 1 ? "país" : "países"}`}>
          <p className="text-sm text-muted-foreground">
            {sale.topic
              ? `Tema no radar: ${sale.topic.name}.`
              : "Este tema ainda não está no radar: o preço usa modelos da mesma categoria."}{" "}
            Preço e chance são estimativas a partir do que o app coletou, em dólar (moeda das lojas), com a
            conversão aproximada para a moeda do país quando há câmbio.
          </p>
          <StoreTable sale={sale} />
          {sale.fanart_tip && (
            <p className="border-l-2 border-[var(--color-signal-down)] pl-3 text-sm">{sale.fanart_tip}</p>
          )}
          <HoursToCover sale={sale} />
        </More>

        <More title="Plano de lançamento" hint={`${sale.checklist.length} passos`}>
          <LaunchChecklist steps={sale.checklist} />
        </More>

        {sale.promotion && (
          <More title="Onde divulgar" hint={sale.promotion.communities.map((c) => c.name).slice(0, 2).join(", ")}>
            <PromotionBlock promotion={sale.promotion} />
          </More>
        )}

        <More title="Capa" hint={sale.cover?.score != null ? `${formatScore(sale.cover.score)}/10` : undefined}>
          {sale.cover ? (
            <CoverBlock cover={sale.cover} />
          ) : (
            <p className="text-sm text-muted-foreground">{sale.cover_note ?? "—"}</p>
          )}
        </More>

        {sale.variations && sale.variations.length > 0 && (
          <More title="Variações que vendem" hint={sale.variations.map((v) => v.label).slice(0, 2).join(", ")}>
            <VariationsBlock variations={sale.variations} />
          </More>
        )}
      </div>
    </div>
  );
}

// Seção "Venda" do resultado (Etapa 3b): países → lojas, preço, chance, anúncio e checklist.
export function SaleSection({ analysisId, initialSale }: { analysisId: number; initialSale: Sale | null }) {
  const options = useSWR<SaleCountries>(`/api/analyses/${analysisId}/sale/countries`, apiGet);
  const [sale, setSale] = useState<Sale | null>(initialSale);
  const [selected, setSelected] = useState<string[] | null>(initialSale?.countries ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const max = options.data?.max ?? 5;
  // Sem escolha do usuário, valem os países padrão (ranking do dia + Brasil).
  const chosen = selected ?? options.data?.defaults ?? [];

  function toggle(code: string) {
    setSelected((current) => {
      const list = current ?? options.data?.defaults ?? [];
      if (list.includes(code)) return list.filter((c) => c !== code);
      return list.length >= max ? list : [...list, code];
    });
  }

  async function prepare() {
    setBusy(true);
    setError(null);
    try {
      setSale(await apiPostJson<Sale>(`/api/analyses/${analysisId}/sale`, { countries: chosen }));
    } catch (exc) {
      if (exc instanceof BackendOfflineError) setError("Não consegui falar com o backend.");
      else if (exc instanceof ApiError) setError(exc.message);
      else setError("Algo deu errado. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Venda" className="flex flex-col gap-6 border-t border-border pt-10">
      <div className="flex flex-col gap-2">
        <h3 className="text-[length:var(--text-lg)] font-bold">Venda</h3>
        <p className="max-w-[62ch] text-sm text-muted-foreground">
          Onde vender, por quanto, a chance de venda e o anúncio pronto para colar. Escolha até {max} países.
        </p>
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="sr-only">Países para vender</legend>
        <div className="flex flex-wrap gap-2">
          {(options.data?.countries ?? []).map(({ code, name }) => {
            const on = chosen.includes(code);
            return (
              <button
                key={code}
                type="button"
                aria-pressed={on}
                disabled={!on && chosen.length >= max}
                onClick={() => toggle(code)}
                className="rounded-full border border-border px-3 py-1 text-sm aria-pressed:border-primary aria-pressed:text-primary disabled:opacity-40"
              >
                {name}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" className="h-9 rounded-full px-5" disabled={busy || chosen.length === 0} onClick={prepare}>
          {busy ? "Montando o anúncio…" : sale ? "Gerar de novo" : "Preparar venda"}
        </Button>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>

      {sale && !busy && <SaleResult sale={sale} />}
    </section>
  );
}
