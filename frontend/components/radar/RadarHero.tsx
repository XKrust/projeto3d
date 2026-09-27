import { ImageOff } from "lucide-react";
import { CountUp } from "@/components/radar/CountUp";
import { SaleChance } from "@/components/radar/SaleChance";
import { Sparkline } from "@/components/radar/Sparkline";
import { ARROW_LABELS, ARROW_SYMBOLS, CATEGORY_LABELS, COUNTRY_IN, formatMedianPrice, formatPeakLabel, formatWhereToSell } from "@/lib/radar-labels";
import type { Topic } from "@/lib/radar-types";

// Destaque do topo (macroestrutura Stat-Led): a nota real do tópico nº 1 é o
// maior elemento da tela, sempre acompanhada de uma frase que diz o que ela é.
export function RadarHero({ topic, country }: { topic: Topic; country: string }) {
  const arrow = ARROW_SYMBOLS[topic.momentum_arrow] ?? "→";
  const arrowLabel = ARROW_LABELS[topic.momentum_arrow] ?? "estável";
  const categoryLabel = CATEGORY_LABELS[topic.category] ?? topic.category;
  const where = COUNTRY_IN[country] ?? `em ${country}`;

  return (
    <section
      aria-labelledby="destaque-titulo"
      className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] lg:items-end lg:gap-16"
    >
      <div className="flex min-w-0 flex-col gap-5">
        <p className="flex items-baseline gap-3 font-heading font-extrabold leading-[0.85] tracking-[-0.045em] text-foreground">
          <CountUp
            value={topic.opportunity}
            className="tnum text-[length:var(--text-figure)]"
          />
          <span className="flex flex-col gap-1 text-[length:var(--text-md)] font-medium leading-tight tracking-normal text-muted-foreground">
            <span className="tnum">/ 100</span>
            <span className="text-primary">
              <span aria-hidden="true">{arrow}</span> {arrowLabel}
            </span>
          </span>
        </p>
        <div className="flex flex-col gap-2">
          <h1
            id="destaque-titulo"
            className="text-[length:var(--text-display)] font-bold text-foreground"
          >
            {topic.name}
          </h1>
          <p className="max-w-[46ch] text-[length:var(--text-md)] leading-snug text-muted-foreground">
            é a maior oportunidade {where} agora, pela nota de 0 a 100 que
            junta procura, ritmo e concorrência.
          </p>
        </div>
        <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <li className="font-medium text-foreground">
            {formatPeakLabel(topic.days_to_peak)}
          </li>
          <li>{formatWhereToSell(topic)}</li>
          <li className="tnum">{formatMedianPrice(topic.median_price_usd)}</li>
          <li>
            <SaleChance chance={topic.sale_chance} />
          </li>
        </ul>
        {topic.reason && (
          <p className="max-w-[60ch] border-l-2 border-primary pl-4 text-base text-foreground/90">
            {topic.reason}
          </p>
        )}
      </div>

      <figure className="flex min-w-0 flex-col gap-4 rounded-[var(--radius-card)] bg-card p-4 sm:p-5">
        <div className="flex items-center gap-4">
          {topic.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- miniaturas vêm de domínios arbitrários
            <img
              src={topic.image_url}
              alt=""
              className="size-20 shrink-0 rounded-xl object-cover sm:size-24"
            />
          ) : (
            <div className="flex size-20 shrink-0 items-center justify-center rounded-xl bg-muted sm:size-24">
              <ImageOff className="size-6 text-muted-foreground" aria-hidden="true" />
            </div>
          )}
          <div className="flex min-w-0 flex-col gap-1">
            <span className="text-sm text-muted-foreground">{categoryLabel}</span>
            <span className="text-sm text-muted-foreground">
              Demanda nos últimos dias
            </span>
          </div>
        </div>
        <Sparkline data={topic.sparkline} height={120} filled />
        <figcaption className="text-xs text-muted-foreground">
          Cada ponto é a demanda do dia, somando Google Trends, YouTube, Reddit e
          as plataformas.
        </figcaption>
      </figure>
    </section>
  );
}
