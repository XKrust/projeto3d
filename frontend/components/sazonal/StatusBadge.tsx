import type { SeasonStatus } from "@/lib/sazonal-types";

const STATUS: Record<SeasonStatus, { label: string; dot: string }> = {
  atrasado: { label: "Atrasado", dot: "bg-[var(--color-signal-down)]" },
  agora: { label: "Comece agora", dot: "bg-primary" },
  em_breve: { label: "Em breve", dot: "bg-[var(--color-neutral)]" },
};

// A cor sempre vem com o texto (nunca só a cor como sinal).
export function StatusBadge({ status }: { status: SeasonStatus }) {
  const meta = STATUS[status];
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-border px-2.5 py-0.5 text-xs text-foreground">
      <span aria-hidden="true" className={`size-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}
