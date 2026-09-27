// Tipos compartilhados entre a tela /radar e seus componentes, espelhando o
// formato de `GET /api/radar/meta` e `GET /api/radar` (backend/app/api/radar.py).

export type Platform = {
  slug: string;
  name: string;
  markets?: string[];
};

export type RadarMeta = {
  countries: string[];
  country_groups: Record<string, string[]>;
  categories: string[];
  markets: string[];
  platforms: Platform[];
  last_updated: string | null;
};

export type SparklinePoint = {
  day: string;
  value: number;
};

export type MomentumArrow = "up" | "down" | "flat";

export type Topic = {
  topic_id: number;
  slug: string;
  name: string;
  category: string;
  image_url: string | null;
  reason: string | null;
  opportunity: number;
  sale_chance: string;
  estimate: boolean;
  momentum_arrow: MomentumArrow;
  days_to_peak: number;
  best_platform: Platform;
  median_price_usd: number | null;
  sparkline: SparklinePoint[];
};

export type CollectResponse = {
  started: boolean;
  message: string;
};
