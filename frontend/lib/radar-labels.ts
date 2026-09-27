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

export const SALE_CHANCE_STYLES: Record<string, string> = {
  Alta: "bg-green-100 text-green-800 dark:bg-green-500/20 dark:text-green-300",
  Média:
    "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-300",
  Baixa: "bg-gray-200 text-gray-700 dark:bg-gray-700/50 dark:text-gray-300",
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
