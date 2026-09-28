import { formatDayMonth } from "@/lib/dates";
import { COUNTRY_LABELS, SALE_CHANCE_DOT } from "@/lib/radar-labels";
import { formatLocal, formatUsd, inCountry, type Sale } from "@/lib/sale-types";

// Resumo da venda: a decisão em 3–4 linhas (loja, preço, chance, prazo). O detalhe fica nas
// seções recolhidas abaixo.
export function SaleSummary({ sale }: { sale: Sale }) {
  const country = sale.by_country.find((c) => c.stores.length > 0);
  const store = country?.stores[0];
  if (!country || !store) {
    return <p className="text-sm text-muted-foreground">Nenhuma loja do app vende este tipo de modelo nos países escolhidos.</p>;
  }
  const fx = country.fx ?? null;
  const { price, chance } = store;
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

  return (
    <section aria-label="Resumo da venda" className="flex flex-col gap-3 rounded-[var(--radius-card)] bg-card p-5">
      <p className="text-[length:var(--text-md)]">
        Publique primeiro no <span className="font-bold">{store.name}</span>
        <span className="text-muted-foreground">
          {" "}
          · melhor encaixe {inCountry(country.country, COUNTRY_LABELS[country.country] ?? country.country)}
        </span>
      </p>
      <p>
        {price ? (
          <>
            <span className="tnum font-heading text-[length:var(--text-lg)] font-bold">{formatUsd(price.suggested)}</span>
            {fx && <span className="tnum text-muted-foreground"> (≈ {formatLocal(price.suggested, fx)})</span>}
            <span className="tnum text-sm text-muted-foreground">
              {" "}
              · {formatUsd(price.launch)} nas primeiras 48 h · estimativa
            </span>
          </>
        ) : (
          <span className="text-sm text-muted-foreground">Preço: {store.price_note ?? "—"}</span>
        )}
      </p>
      <p className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground">Chance de venda:</span>
        {chance.label ? (
          <>
            <span aria-hidden="true" className={`size-2 rounded-full ${SALE_CHANCE_DOT[chance.label]}`} />
            <span className="font-medium">{chance.label}</span>
            <span className="tnum text-sm text-muted-foreground">{chance.value}/100 (estimativa)</span>
          </>
        ) : (
          <span className="text-sm text-muted-foreground">— · {chance.why}</span>
        )}
      </p>
      {sale.peak_day && (
        <p className="text-sm">
          {sale.peak_day >= today
            ? `Publique antes de ${formatDayMonth(sale.peak_day)}: é quando o tema deve estar no pico.`
            : `O pico previsto do tema já passou (${formatDayMonth(sale.peak_day)}): publique o quanto antes.`}
        </p>
      )}
      {store.fanart?.level === "alto" && (
        <p className="text-sm text-[var(--color-signal-down)]">
          Fan-art: {store.name} tem risco alto de remoção. Veja “Todas as lojas e preços”.
        </p>
      )}
    </section>
  );
}
