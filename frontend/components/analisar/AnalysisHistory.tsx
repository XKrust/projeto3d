import { formatScore, type AnalysisSummary } from "@/lib/analyzer-types";

// Lista das análises anteriores; clicar abre a análise.
export function AnalysisHistory({ items, onOpen }: { items: AnalysisSummary[]; onOpen: (id: number) => void }) {
  if (!items.length) return null;
  return (
    <section aria-labelledby="historico-titulo" className="flex flex-col gap-3">
      <h2 id="historico-titulo" className="text-[length:var(--text-xl)] font-bold">
        Análises anteriores
      </h2>
      <ul aria-label="Análises anteriores" className="flex flex-col border-b border-border">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onOpen(item.id)}
              className="flex w-full items-center gap-4 border-t border-border py-3 text-left hover:bg-muted"
            >
              {item.thumb ? (
                // eslint-disable-next-line @next/next/no-img-element -- imagem salva no backend local
                <img src={item.thumb} alt="" className="size-12 rounded-md object-cover" />
              ) : (
                <span className="size-12 rounded-md bg-muted" aria-hidden="true" />
              )}
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate font-medium">{item.theme}</span>
                <span className="text-sm text-muted-foreground">
                  {new Date(item.created_at).toLocaleDateString("pt-BR")}
                </span>
              </span>
              <span className="tnum font-heading text-[length:var(--text-lg)] font-bold">
                {formatScore(item.overall)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
