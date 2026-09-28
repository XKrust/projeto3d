"use client";

import { useState } from "react";
import { COUNTRY_LABELS, SALE_CHANCE_DOT } from "@/lib/radar-labels";
import { formatDayMonth } from "@/lib/dates";
import { formatLocal, formatUsd, type Fx, type Sale, type SaleStore } from "@/lib/sale-types";

function StoreRow({ store, position, fx }: { store: SaleStore; position: number; fx: Fx | null }) {
  const { price, chance } = store;
  return (
    <li className="grid gap-x-6 gap-y-3 border-t border-border py-4 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-1">
        <p className="font-medium">
          <span className="tnum mr-2 text-muted-foreground">{position}.</span>
          {store.name}
        </p>
        <p className="text-sm text-muted-foreground">{store.why}</p>
        {store.fanart && (
          <p className="text-sm">
            <span
              className={
                store.fanart.level === "alto"
                  ? "text-[var(--color-signal-down)]"
                  : store.fanart.level === "medio"
                    ? "text-[var(--color-signal-mid)]"
                    : "text-muted-foreground"
              }
            >
              Fan-art: {store.fanart.label}
            </span>
            <span className="text-muted-foreground"> · {store.fanart.summary}</span>
            {store.fanart.url && (
              <>
                {" "}
                <a href={store.fanart.url} target="_blank" rel="noreferrer" className="underline underline-offset-4 hover:text-primary">
                  política da loja
                </a>
              </>
            )}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Preço (estimativa)</p>
        {price ? (
          <>
            <p className="tnum">
              <span className="text-[length:var(--text-lg)] font-bold">{formatUsd(price.suggested)}</span>
              <span className="ml-2 text-sm text-muted-foreground">
                faixa {formatUsd(price.low)}–{formatUsd(price.high)}
              </span>
            </p>
            <p className="tnum text-sm">
              lançamento {formatUsd(price.launch)} ·{" "}
              {price.net === null ? "taxa: —" : `sobra ${formatUsd(price.net)} (taxa ${store.fee_pct}%)`}
            </p>
            {fx && (
              <p className="tnum text-sm">
                ≈ {formatLocal(price.suggested, fx)} · faixa ≈ {formatLocal(price.low, fx)}–
                {formatLocal(price.high, fx)} · lançamento ≈ {formatLocal(price.launch, fx)}
                <span className="block text-xs text-muted-foreground">câmbio de {formatDayMonth(fx.day)}, estimativa</span>
              </p>
            )}
            <p className="text-xs text-muted-foreground">{price.basis}</p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">{store.price_note ?? "—"}</p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Chance de venda (estimativa)</p>
        {chance.value === null || chance.label === null ? (
          <p className="text-sm text-muted-foreground">— · {chance.why}</p>
        ) : (
          <>
            <p className="flex items-center gap-2">
              <span aria-hidden="true" className={`size-2 rounded-full ${SALE_CHANCE_DOT[chance.label]}`} />
              <span className="font-medium">{chance.label}</span>
              <span className="tnum text-muted-foreground">{chance.value}/100</span>
            </p>
            <p className="text-xs text-muted-foreground">{chance.why}</p>
          </>
        )}
      </div>
    </li>
  );
}

// Lojas por país (spec 3b §11): abas por país, 3 lojas em cada, preço e chance rotulados.
export function StoreTable({ sale }: { sale: Sale }) {
  const [active, setActive] = useState(sale.by_country[0]?.country);
  const current = sale.by_country.find((c) => c.country === active) ?? sale.by_country[0];

  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label="Países" className="flex flex-wrap gap-2">
        {sale.by_country.map(({ country }) => (
          <button
            key={country}
            role="tab"
            type="button"
            aria-selected={country === current?.country}
            onClick={() => setActive(country)}
            className="rounded-full border border-border px-4 py-1.5 text-sm aria-selected:border-primary aria-selected:text-primary"
          >
            {COUNTRY_LABELS[country] ?? country}
          </button>
        ))}
      </div>
      {current && (
        <div role="tabpanel" aria-label={COUNTRY_LABELS[current.country] ?? current.country}>
          {current.stores.length ? (
            <ol className="flex flex-col">
              {current.stores.map((store, index) => (
                <StoreRow key={store.platform} store={store} position={index + 1} fx={current.fx ?? null} />
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted-foreground">
              Nenhuma loja do app vende este tipo de modelo neste país.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
