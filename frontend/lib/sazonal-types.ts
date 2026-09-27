// Espelha GET /api/seasonal (backend/app/api/seasonal.py).

export type SeasonStatus = "atrasado" | "agora" | "em_breve";

export type TopModel = {
  name: string;
  query: string;
  opportunity: number | null;
  sale_chance: string | null;
  measured: boolean;
  competition: Record<string, number>;
  signal: number;
};

export type SeasonEvent = {
  slug: string;
  name: string;
  date: string;
  start_by: string;
  days_to_event: number;
  days_to_start: number;
  status: SeasonStatus;
  themes: string[];
  top_models: TopModel[];
};

export type SeasonalResponse = {
  country: string;
  lead_days: number;
  modeling_days: number;
  events: SeasonEvent[];
};
