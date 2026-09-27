import { CountUp } from "@/components/radar/CountUp";
import { TopModels } from "@/components/sazonal/TopModels";
import { formatDayMonth, formatDays } from "@/lib/dates";
import { COUNTRY_IN } from "@/lib/radar-labels";
import type { SeasonEvent } from "@/lib/sazonal-types";

// Destaque (Stat-Led): quantos dias faltam para começar a modelar para o próximo
// evento que ainda dá tempo.
export function SeasonHero({
  event,
  country,
  leadDays,
  modelingDays,
}: {
  event: SeasonEvent;
  country: string;
  leadDays: number;
  modelingDays: number;
}) {
  const days = Math.max(0, event.days_to_start);
  const where = COUNTRY_IN[country] ?? `em ${country}`;

  return (
    <section aria-labelledby="evento-titulo" className="flex flex-col gap-6">
      <p className="flex items-baseline gap-3 font-heading font-extrabold leading-[0.85] tracking-[-0.045em]">
        <CountUp value={days} className="tnum text-[length:var(--text-figure)]" />
        <span className="max-w-[16ch] text-[length:var(--text-md)] font-medium leading-tight tracking-normal text-muted-foreground">
          {days === 0 ? "comece hoje" : `${days === 1 ? "dia" : "dias"} para começar a modelar`}
        </span>
      </p>
      <div className="flex flex-col gap-2">
        <h1 id="evento-titulo" className="text-[length:var(--text-display)] font-bold">
          {event.name}
        </h1>
        <p className="max-w-[52ch] text-[length:var(--text-md)] leading-snug text-muted-foreground">
          é a próxima data que vende {where} em que ainda dá tempo de modelar. Faltam{" "}
          {formatDays(event.days_to_event)} para o evento.
        </p>
      </div>
      <ul className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <li className="font-medium text-primary">Comece a modelar até {formatDayMonth(event.start_by)}</li>
        <li className="text-muted-foreground">Evento em {formatDayMonth(event.date)}</li>
        <li className="text-muted-foreground">
          Conta: evento − {leadDays} dias de antecedência de compra − {modelingDays} de modelagem
        </li>
      </ul>
      <div className="flex max-w-2xl flex-col gap-2">
        <h2 className="text-[length:var(--text-lg)] font-bold">
          O que modelar para vender mais
        </h2>
        <TopModels models={event.top_models} label={`Top 5 modelos para ${event.name}`} variant="hero" />
      </div>
    </section>
  );
}
