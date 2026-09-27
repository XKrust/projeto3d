import { Poster } from "@/components/hype/Poster";
import { SaleChance } from "@/components/radar/SaleChance";
import { formatDayMonth } from "@/lib/dates";
import { KIND_LABELS, formatCompetition, type HypeRelease } from "@/lib/hype-types";

export function ReleaseRow({ release, rank }: { release: HypeRelease; rank: number }) {
  const competition = formatCompetition(release.competition);
  const when = release.release_date
    ? `Estreia em ${formatDayMonth(release.release_date)}`
    : "Data a confirmar";

  return (
    <li className="grid grid-cols-[2rem_3.5rem_minmax(0,1fr)_auto] items-start gap-x-3 gap-y-3 border-t border-border py-5 sm:gap-x-4 lg:px-2">
      <span className="tnum pt-1 text-sm text-muted-foreground">
        {String(rank).padStart(2, "0")}
      </span>
      <Poster src={release.image_url} className="h-20 w-14" />
      <div className="flex min-w-0 flex-col gap-1.5">
        <h3 className="text-[length:var(--text-md)] font-semibold tracking-[-0.015em]">
          {release.title}
        </h3>
        <p className="text-sm text-muted-foreground">
          {KIND_LABELS[release.kind]} · {when}
        </p>
        <p className="text-sm text-muted-foreground">
          {competition ?? "Concorrência ainda não medida"}
        </p>
      </div>
      <div className="flex flex-col items-end gap-2">
        <span className="tnum font-heading text-[length:var(--text-xl)] font-bold leading-none tracking-[-0.03em]">
          {Math.round(release.opportunity)}
        </span>
        <SaleChance chance={release.sale_chance} />
      </div>

      {release.characters.length > 0 && (
        <ul
          aria-label={`Personagens de ${release.title}`}
          className="col-span-4 flex flex-wrap gap-2 sm:col-start-3 sm:col-end-5"
        >
          {release.characters.map((character) => (
            <li
              key={character.name}
              className="flex flex-wrap items-center gap-2.5 rounded-full bg-card py-1 pl-1 pr-3 text-sm"
            >
              <Poster src={character.image_url} className="size-7 rounded-full" />
              <span className="font-medium text-foreground">{character.name}</span>
              <SaleChance chance={character.sale_chance} />
              <span className="text-xs text-muted-foreground">
                {formatCompetition(character.competition) ?? "sem medição"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
