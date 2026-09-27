import { ImageOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sparkline } from "@/components/radar/Sparkline";
import {
  ARROW_SYMBOLS,
  CATEGORY_LABELS,
  SALE_CHANCE_STYLES,
  formatMedianPrice,
  formatPeakLabel,
} from "@/lib/radar-labels";
import type { Topic } from "@/lib/radar-types";

export function TopicCard({ topic }: { topic: Topic }) {
  const arrow = ARROW_SYMBOLS[topic.momentum_arrow] ?? "→";
  const categoryLabel = CATEGORY_LABELS[topic.category] ?? topic.category;
  const saleChanceClass = SALE_CHANCE_STYLES[topic.sale_chance] ?? "";

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-3">
        {topic.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- thumbnails vêm de domínios arbitrários
          <img
            src={topic.image_url}
            alt={topic.name}
            className="size-12 shrink-0 rounded-md object-cover"
          />
        ) : (
          <div className="flex size-12 shrink-0 items-center justify-center rounded-md bg-muted">
            <ImageOff className="size-5 text-muted-foreground" aria-hidden="true" />
          </div>
        )}
        <div className="flex flex-1 flex-col gap-1">
          <CardTitle>{topic.name}</CardTitle>
          <Badge variant="secondary" className="w-fit">
            {categoryLabel}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-semibold">
            {Math.round(topic.opportunity)}
          </span>
          <span className="text-lg text-muted-foreground" aria-hidden="true">
            {arrow}
          </span>
          <Badge className={saleChanceClass}>
            {topic.sale_chance} (estimativa)
          </Badge>
        </div>
        <Sparkline data={topic.sparkline} />
        <p className="text-sm text-muted-foreground">
          {formatPeakLabel(topic.days_to_peak)}
        </p>
        <p className="text-sm text-muted-foreground">
          Melhor em: {topic.best_platform.name}
        </p>
        <p className="text-sm text-muted-foreground">
          {formatMedianPrice(topic.median_price_usd)}
        </p>
        {topic.reason && <p className="text-sm">{topic.reason}</p>}
      </CardContent>
    </Card>
  );
}
