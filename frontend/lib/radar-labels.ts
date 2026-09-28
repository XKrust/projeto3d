// Rótulos em PT-BR e formatação usados na tela /radar. Os valores em código
// (país, categoria, mercado) são os de `backend/app/constants.py`.

export const CATEGORY_LABELS: Record<string, string> = {
  anime: "Anime",
  games: "Games",
  filmes_series: "Filmes e séries",
  toys_memes: "Toys e memes",
  rpg_miniaturas: "RPG e miniaturas",
  decoracao: "Decoração",
  outros: "Outros",
};

export const COUNTRY_LABELS: Record<string, string> = {
  BR: "Brasil",
  US: "EUA",
  JP: "Japão",
  GB: "Reino Unido",
  DE: "Alemanha",
  FR: "França",
  ES: "Espanha",
  RU: "Rússia",
  BY: "Bielorrússia",
  MX: "México",
  IT: "Itália",
  CA: "Canadá",
  AU: "Austrália",
  PL: "Polônia",
  NL: "Holanda",
};

export const MARKET_LABELS: Record<string, string> = {
  print: "Impressão 3D",
  digital: "Digital",
};

export const ARROW_SYMBOLS: Record<string, string> = {
  up: "↑",
  down: "↓",
  flat: "→",
};

// Cor do ponto ao lado da chance de venda (tokens de sinal em app/tokens.css).
// O texto ("Alta"/"Média"/"Baixa") sempre acompanha a cor.
export const SALE_CHANCE_DOT: Record<string, string> = {
  Alta: "bg-[var(--color-signal-up)]",
  Média: "bg-[var(--color-signal-mid)]",
  Baixa: "bg-[var(--color-neutral)]",
};

export const ARROW_LABELS: Record<string, string> = {
  up: "subindo",
  down: "caindo",
  flat: "estável",
};

export function formatPeakLabel(daysToPeak: number): string {
  if (daysToPeak <= 0) {
    return "Pico agora";
  }
  if (daysToPeak === 1) {
    return "Pico em 1 dia";
  }
  return `Pico em ${daysToPeak} dias`;
}

export function formatMedianPrice(medianPriceUsd: number | null): string {
  if (medianPriceUsd === null) {
    return "Preço mediano: —";
  }
  const formatted = new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(medianPriceUsd);
  return `Preço mediano: US$ ${formatted}`;
}

// País com a preposição certa, para frases como "a maior oportunidade no Brasil".
export const COUNTRY_IN: Record<string, string> = {
  BR: "no Brasil",
  US: "nos EUA",
  JP: "no Japão",
  GB: "no Reino Unido",
  DE: "na Alemanha",
  FR: "na França",
  ES: "na Espanha",
  RU: "na Rússia",
  BY: "na Bielorrússia",
  MX: "no México",
  IT: "na Itália",
  CA: "no Canadá",
  AU: "na Austrália",
  PL: "na Polônia",
  NL: "na Holanda",
};

/** "Onde vender: Cults3D · Mercado Livre · Etsy" (as 3 melhores lojas do tema). */
export function formatWhereToSell(topic: { best_platform: { name: string }; platforms?: { name: string }[] }): string {
  const names = topic.platforms?.length ? topic.platforms.map((p) => p.name) : [topic.best_platform.name];
  return `Onde vender: ${names.join(" · ")}`;
}
