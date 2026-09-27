// Espelha GET /api/hype (backend/app/api/hype.py).

export type HypeKind = "anime" | "filme" | "serie" | "jogo";

export type HypeCharacter = {
  name: string;
  image_url: string | null;
  favourites: number;
  competition: Record<string, number>;
  opportunity: number;
  sale_chance: string;
};

export type HypeRelease = {
  id: number;
  title: string;
  term: string;
  kind: HypeKind;
  source: string;
  release_date: string | null;
  days_to_release: number | null;
  peak: string | null;
  fit_window: number;
  image_url: string | null;
  url: string | null;
  popularity: number;
  competition: Record<string, number>;
  opportunity: number;
  sale_chance: string;
  reason: string;
  characters: HypeCharacter[];
};

export type HypeResponse = {
  country: string;
  releases: HypeRelease[];
};

export const KIND_LABELS: Record<HypeKind, string> = {
  anime: "Anime",
  filme: "Filme",
  serie: "Série",
  jogo: "Jogo",
};

export const KIND_FILTER_LABELS: Record<string, string> = {
  todos: "Todos os tipos",
  anime: "Anime",
  filme: "Filmes",
  serie: "Séries",
  jogo: "Jogos",
};

// "Cults3D 34 · BOOTH 7" — a API já manda do maior para o menor.
export function formatCompetition(competition: Record<string, number>): string | null {
  const entries = Object.entries(competition);
  if (entries.length === 0) {
    return null;
  }
  return entries.map(([platform, count]) => `${platform} ${count}`).join(" · ");
}
