import { CountUp } from "@/components/radar/CountUp";
import { SaleChance } from "@/components/radar/SaleChance";
import { Poster } from "@/components/hype/Poster";
import { formatDayMonth } from "@/lib/dates";
import { KIND_LABELS, formatCompetition, type HypeRelease } from "@/lib/hype-types";

// Destaque (Stat-Led): o lançamento de maior oportunidade. O número é quantos dias
// faltam para a estreia; sem data (ou já estreado), vira a nota de oportunidade.
export function HypeHero({ release }: { release: HypeRelease }) {
  const days = release.days_to_release;
  const hasDate = days !== null && days >= 0;
  const figure = hasDate ? days : release.opportunity;
  const competition = formatCompetition(release.competition);

  let figureLabel = "de oportunidade, estreia sem data confirmada";
  if (days !== null && days < 0) {
    figureLabel = "de oportunidade, já estreou";
  } else if (hasDate) {
    figureLabel = days === 1 ? "dia para a estreia" : "dias para a estreia";
  }

  return (
    <section
      aria-labelledby="hype-titulo"
      className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-end lg:gap-16"
    >
      <div className="flex min-w-0 flex-col gap-5">
        <p className="flex items-baseline gap-3 font-heading font-extrabold leading-[0.85] tracking-[-0.045em]">
          <CountUp value={figure} className="tnum text-[length:var(--text-figure)]" />
          <span className="max-w-[14ch] text-[length:var(--text-md)] font-medium leading-tight tracking-normal text-muted-foreground">
            {figureLabel}
          </span>
        </p>
        <div className="flex flex-col gap-2">
          <h1 id="hype-titulo" className="text-[length:var(--text-display)] font-bold">
            {release.title}
          </h1>
          <p className="max-w-[52ch] text-[length:var(--text-md)] leading-snug text-muted-foreground">
            {KIND_LABELS[release.kind]} com a maior oportunidade entre as estreias: nota{" "}
            {Math.round(release.opportunity)} de 100.
          </p>
        </div>
        <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
          <li className="font-medium text-foreground">{release.reason}</li>
          {release.release_date && <li>Estreia em {formatDayMonth(release.release_date)}</li>}
          <li>
            <SaleChance chance={release.sale_chance} />
          </li>
        </ul>
        <p className="text-sm text-muted-foreground">
          {competition
            ? `Concorrência hoje: ${competition}`
            : "Concorrência ainda não medida nas plataformas."}
        </p>
      </div>

      <figure className="flex min-w-0 items-center gap-4 rounded-[var(--radius-card)] bg-card p-4 sm:p-5">
        <Poster src={release.image_url} className="h-36 w-24 sm:h-44 sm:w-30" />
        <figcaption className="flex min-w-0 flex-col gap-2 text-sm text-muted-foreground">
          <span>
            Pico de procura previsto:{" "}
            <span className="text-foreground">
              {release.peak ? formatDayMonth(release.peak) : "—"}
            </span>
          </span>
          <span>O pico é a estreia menos a antecedência de compra.</span>
          {release.url && (
            <a
              href={release.url}
              target="_blank"
              rel="noreferrer"
              className="text-foreground underline underline-offset-4 hover:text-primary"
            >
              Ver na fonte
            </a>
          )}
        </figcaption>
      </figure>
    </section>
  );
}
