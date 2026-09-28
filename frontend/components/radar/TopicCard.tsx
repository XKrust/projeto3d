import { TopicThumb } from "@/components/radar/TopicThumb";
import { SaleChance } from "@/components/radar/SaleChance";
import { Sparkline } from "@/components/radar/Sparkline";
import { ARROW_LABELS, ARROW_SYMBOLS, CATEGORY_LABELS, formatMedianPrice, formatPeakLabel, formatWhereToSell } from "@/lib/radar-labels";
import type { Topic } from "@/lib/radar-types";

// Uma linha do ranking, do nº 2 em diante (o nº 1 fica no destaque do topo).
export function TopicCard({ topic, rank }: { topic: Topic; rank: number }) {
  const arrow = ARROW_SYMBOLS[topic.momentum_arrow] ?? "→";
  const arrowLabel = ARROW_LABELS[topic.momentum_arrow] ?? "estável";
  const categoryLabel = CATEGORY_LABELS[topic.category] ?? topic.category;
  const score = Math.round(topic.opportunity);

  return (
    <li className="group grid grid-cols-[2rem_3rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-3 border-t border-border py-5 transition-colors duration-150 hover:bg-card/60 sm:gap-x-4 lg:grid-cols-[2.5rem_3.25rem_minmax(0,1fr)_5.5rem_7.5rem_minmax(0,15rem)] lg:px-2">
      <span className="tnum self-start pt-1 text-sm text-muted-foreground">
        {String(rank).padStart(2, "0")}
      </span>

      <TopicThumb name={topic.name} src={topic.image_url} className="size-12 rounded-lg text-base lg:size-13" />

      <div className="flex min-w-0 flex-col gap-1">
        <h3 className="text-[length:var(--text-md)] font-semibold tracking-[-0.015em] text-foreground">
          {topic.name}
        </h3>
        <p className="text-sm text-muted-foreground">
          {categoryLabel}
          {topic.reason && <span className="hidden sm:inline"> · {topic.reason}</span>}
        </p>
      </div>

      <p className="flex flex-col items-end leading-none lg:items-start">
        <span className="tnum font-heading text-[length:var(--text-xl)] font-bold tracking-[-0.03em] text-foreground">
          {score}
        </span>
        <span className="mt-1 whitespace-nowrap text-xs text-muted-foreground">
          <span aria-hidden="true" className="text-primary">
            {arrow}
          </span>{" "}
          {arrowLabel}
        </span>
      </p>

      <div className="col-span-4 lg:col-span-1">
        <Sparkline data={topic.sparkline} height={36} />
      </div>

      <ul className="col-span-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground lg:col-span-1 lg:flex-col lg:items-start lg:gap-1">
        <li className="text-foreground">{formatPeakLabel(topic.days_to_peak)}</li>
        <li>{formatWhereToSell(topic)}</li>
        <li className="tnum">{formatMedianPrice(topic.median_price_usd)}</li>
        <li>
          <SaleChance chance={topic.sale_chance} />
        </li>
      </ul>
    </li>
  );
}
