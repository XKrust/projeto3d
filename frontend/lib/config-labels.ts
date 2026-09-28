// Rótulos em PT-BR e formatação usados na tela /config.

export const SOURCE_STATUS_META: Record<string, { emoji: string; label: string }> = {
  ok: { emoji: "🟢", label: "ok" },
  error: { emoji: "🔴", label: "erro" },
  no_key: { emoji: "🟡", label: "sem chave" },
  never: { emoji: "⚪", label: "nunca rodou" },
};

// Datas sem `Z`/offset explícito são tratadas como UTC (formato usado pelo
// backend para `last_run`), evitando que o navegador as leia como hora local.
function parseAsUtc(iso: string): Date {
  const hasOffset = /Z$|[+-]\d{2}:\d{2}$/.test(iso);
  return new Date(hasOffset ? iso : `${iso}Z`);
}

export function formatRelativeTime(
  lastRun: string | null,
  now: Date = new Date()
): string {
  if (!lastRun) {
    return "nunca";
  }

  const diffMs = now.getTime() - parseAsUtc(lastRun).getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  if (diffMin < 1) {
    return "agora mesmo";
  }
  if (diffMin < 60) {
    return `há ${diffMin} min`;
  }
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) {
    return `há ${diffHours} h`;
  }
  const diffDays = Math.floor(diffHours / 24);
  return diffDays === 1 ? "há 1 dia" : `há ${diffDays} dias`;
}
