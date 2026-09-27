// Datas da API chegam em ISO ("2026-10-31"). Formata sem passar por Date, para o
// fuso horário não empurrar o dia para trás.
export function formatDayMonth(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  const [, month, day] = iso.split("-");
  return `${day}/${month}`;
}

export function formatDays(days: number): string {
  return days === 1 ? "1 dia" : `${days} dias`;
}
