import { StatusBadge } from "@/components/sazonal/StatusBadge";
import { formatDayMonth, formatDays } from "@/lib/dates";
import type { SeasonEvent } from "@/lib/sazonal-types";

export function EventRow({ event }: { event: SeasonEvent }) {
  return (
    <li className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-start gap-x-4 gap-y-2 border-t border-border py-5 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto] lg:px-2">
      <p className="tnum font-heading text-[length:var(--text-xl)] font-bold leading-none tracking-[-0.03em]">
        {formatDayMonth(event.date)}
      </p>
      <div className="flex min-w-0 flex-col gap-2">
        <h3 className="text-[length:var(--text-md)] font-semibold tracking-[-0.015em]">
          {event.name}
        </h3>
        <p className="text-sm text-muted-foreground">
          Comece até {formatDayMonth(event.start_by)} · evento em {formatDays(event.days_to_event)}
        </p>
        <p className="text-sm text-muted-foreground">{event.themes.join(" · ")}</p>
      </div>
      <div className="col-start-2 sm:col-start-3 sm:row-start-1 sm:justify-self-end">
        <StatusBadge status={event.status} />
      </div>
    </li>
  );
}
