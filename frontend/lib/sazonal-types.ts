// Espelha GET /api/seasonal (backend/app/api/seasonal.py).

export type SeasonStatus = "atrasado" | "agora" | "em_breve";

export type SeasonEvent = {
  slug: string;
  name: string;
  date: string;
  start_by: string;
  days_to_event: number;
  days_to_start: number;
  status: SeasonStatus;
  themes: string[];
};

export type SeasonalResponse = {
  country: string;
  lead_days: number;
  modeling_days: number;
  events: SeasonEvent[];
};
