// Formato do `sale` de POST /api/analyses/{id}/sale (backend/app/sale/build.py, spec 3b §9).

export type SalePrice = {
  suggested: number;
  low: number;
  high: number;
  launch: number;
  net: number | null;
  basis: string;
};

export type SaleChance = { value: number | null; label: "Alta" | "Média" | "Baixa" | null; why: string };

export type SaleStore = {
  platform: string;
  name: string;
  fee_pct: number | null;
  fit: number;
  why: string;
  price: SalePrice | null;
  price_note: string | null;
  chance: SaleChance;
  fanart?: { level: "alto" | "medio" | null; label: string; summary: string; url: string | null } | null;
};

export type Variation = {
  type: string;
  label: string;
  why: string;
  evidence: string | null;
  flagged: boolean;
  source: "ia" | "padrao";
};

export type CoverCheck = { label: string; ok: boolean | null; why: string; fix: string; flagged: boolean };

export type Cover = {
  score: number | null;
  checks: Record<string, CoverCheck>;
  vs_top: { reference: number; text: string; flagged: boolean }[];
  references: { title: string; url: string | null; thumb_url: string; likes: number | null }[];
  scope?: "tema" | "parecidos";
};

export type Listing = {
  platform: string;
  lang: "en" | "pt" | "ja";
  title: string;
  tags: string[];
  description: string;
  trimmed: boolean;
  flagged: boolean;
};

export type Fx = { currency: string; rate: number; day: string };

export type Community = { name: string; url: string; why: string; source: "tema" | "tipo" };

export type Sale = {
  countries: string[];
  topic: { id: number; name: string; slug: string } | null;
  by_country: { country: string; fx?: Fx | null; stores: SaleStore[] }[];
  hours_to_cover: { sales: number; hours: number; hourly_rate_usd: number; price: number } | null;
  listing: { listings: Listing[] } | null;
  listing_note: string | null;
  promotion?: { communities: Community[]; hashtags: string[]; note: string };
  variations?: Variation[];
  cover?: Cover | null;
  cover_note?: string | null;
  fanart_tip?: string | null;
  checklist: string[];
  estimate: true;
};

export type SaleCountries = {
  max: number;
  defaults: string[];
  countries: { code: string; name: string }[];
};

export const LANG_LABELS: Record<Listing["lang"], string> = {
  en: "Inglês",
  pt: "Português",
  ja: "Japonês",
};

/** 7.99 → "US$ 7,99". */
export function formatUsd(value: number): string {
  return `US$ ${value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Vendas para cobrir as horas ao valor/hora (mesma conta do backend). */
export function salesToCover(hours: number, hourlyRate: number, price: number): number | null {
  if (!hours || !price || !hourlyRate || hourlyRate <= 0) return null;
  return Math.ceil((hours * hourlyRate) / price);
}

/** Converte um preço em US$ para a moeda do país: 7.99 × 5.43 → "R$ 43,39". */
export function formatLocal(usd: number, fx: Fx): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: fx.currency }).format(usd * fx.rate);
}
