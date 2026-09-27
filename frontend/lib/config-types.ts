// Tipos compartilhados pela tela /config e seus componentes, espelhando o
// formato de `GET /api/settings`, `GET /api/sources` e `GET /api/platforms`
// (backend/app/api/settings.py, backend/app/api/sources.py).

export type SourceStatus = "ok" | "error" | "no_key" | "never";

export type SourceHealth = {
  name: string;
  label: string;
  kind: string;
  needs_key: boolean;
  has_key: boolean;
  status: SourceStatus;
  last_run: string | null;
  last_error: string | null;
  items_last_run: number;
};

export type Weights = {
  demand: number;
  momentum: number;
  saturation: number;
};

export type SettingsData = {
  api_keys: Record<string, string>;
  countries: string[];
  modeling_days: number;
  lead_days: number;
  weights: Weights;
  source_weights: Record<string, number>;
  gemini_model: string;
  top_n_saturation: number;
};

export type PlatformConfig = {
  slug: string;
  name: string;
  markets: string[];
  fee_pct: number | null;
  strength: Record<string, number>;
  notes: string;
};
