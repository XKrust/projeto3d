import { SaleChance } from "@/components/radar/SaleChance";
import { SALE_CHANCE_DOT } from "@/lib/radar-labels";
import { formatCompetition } from "@/lib/hype-types";
import type { TopModel } from "@/lib/sazonal-types";

// Top 5 de modelos para uma data. "hero" é a lista numerada do destaque; "compact" é a
// versão curta das linhas do calendário. Ideia sem dados não ganha nota inventada.
export function TopModels({
  models,
  label,
  variant,
}: {
  models: TopModel[];
  label: string;
  variant: "hero" | "compact";
}) {
  if (variant === "compact") {
    return (
      <ol aria-label={label} className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm">
        {models.map((model, index) => (
          <li key={model.query} className="flex items-center gap-1.5">
            <span className="tnum text-muted-foreground">{index + 1}.</span>
            {model.measured && model.sale_chance ? (
              <span
                aria-hidden="true"
                className={`size-1.5 rounded-full ${SALE_CHANCE_DOT[model.sale_chance] ?? SALE_CHANCE_DOT.Baixa}`}
              />
            ) : null}
            <span className="text-foreground">{model.name}</span>
            {model.measured && model.sale_chance ? (
              <span className="sr-only">
                chance {model.sale_chance} (estimativa)
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">sem dados ainda</span>
            )}
          </li>
        ))}
      </ol>
    );
  }

  return (
    <ol aria-label={label} className="flex flex-col border-b border-border">
      {models.map((model, index) => {
        const competition = formatCompetition(model.competition);
        return (
          <li
            key={model.query}
            className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 border-t border-border py-3"
          >
            <span className="tnum font-heading text-[length:var(--text-lg)] font-bold text-muted-foreground">
              {index + 1}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="font-medium text-foreground">{model.name}</span>
              <span className="text-xs text-muted-foreground">
                {model.measured
                  ? competition
                    ? `Concorrência: ${competition}`
                    : "Concorrência ainda não medida"
                  : "sem dados ainda — aparece depois das próximas coletas"}
              </span>
            </span>
            {model.measured && model.sale_chance ? (
              <SaleChance chance={model.sale_chance} />
            ) : (
              <span className="text-xs text-muted-foreground">—</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
