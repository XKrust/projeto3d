// Formato de GET /api/analyses/{id} (backend/app/analyzer/store.py, spec 3a §8).

export type Criterion = { score: number | null; why: string };

export type Strength = { text: string; image: number | null; area: string; flagged: boolean };

export type Improvement = {
  image: number;
  area: string;
  problem: string;
  fix: string;
  gain: string;
  confidence: "alta" | "media" | "baixa";
  criterion: string | null;
  flagged: boolean;
};

export type Reference = {
  name: string;
  artist: string;
  url: string;
  thumb_url: string | null;
  likes: number;
  source: "auto" | "usuario";
};

export type Analysis = {
  id: number;
  created_at: string;
  input: {
    authorship: "autoral" | "fanart";
    market: "print" | "digital";
    hours: number | null;
    images: string[];
    wireframe: string | null;
  };
  image_urls: string[];
  identified: { theme: string; category: string; style: string; character: string | null; search_query: string };
  references: Reference[];
  references_note: string | null;
  result: {
    criteria: Record<string, Criterion>;
    strengths: Strength[];
    improvements: Improvement[];
    to_check: Improvement[];
    reference_comparison: { reference: number; text: string; flagged: boolean }[];
    top_actions: string[];
    overall: number | null;
  };
  previous: { id: number; overall: number | null } | null;
};

export type AnalysisSummary = {
  id: number;
  created_at: string;
  theme: string;
  overall: number | null;
  thumb: string | null;
};

export const CRITERIA_LABELS: Record<string, string> = {
  anatomia: "Anatomia e proporção",
  silhueta: "Silhueta e forma",
  detalhe: "Detalhe e escultura",
  pose: "Pose e apelo",
  materiais: "Materiais e textura",
  render: "Iluminação e render",
  apresentacao: "Apresentação (capa)",
  topologia: "Topologia",
  imprimibilidade: "Imprimibilidade",
};

/** 6.9 → "6,9" (nota de 0 a 10 com uma casa). */
export function formatScore(value: number | null): string {
  return value === null ? "—" : value.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}
