import { formatScore } from "@/lib/analyzer-types";
import type { Cover } from "@/lib/sale-types";

const MARK = { true: "✓", false: "✗", null: "—" } as const;

// Nota da capa (Etapa 3c): checklist da IA; a nota é calculada pelo app.
export function CoverBlock({ cover }: { cover: Cover }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="flex items-baseline gap-3">
        <span className="tnum font-heading text-[length:var(--text-lg)] font-bold">{formatScore(cover.score)}</span>
        <span className="text-sm text-muted-foreground">
          {cover.score === null ? "não deu para avaliar a capa pela imagem" : "/10 · avaliação por IA da imagem 1"}
        </span>
      </p>
      <ul className="flex flex-col" aria-label="Checklist da capa">
        {Object.entries(cover.checks).map(([slug, check]) => (
          <li key={slug} className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-2 border-t border-border py-3">
            <span
              aria-label={check.ok === null ? "não avaliado" : check.ok ? "ok" : "precisa melhorar"}
              className={
                check.ok === null
                  ? "text-muted-foreground"
                  : check.ok
                    ? "text-[var(--color-signal-up)]"
                    : "text-[var(--color-signal-down)]"
              }
            >
              {MARK[String(check.ok) as keyof typeof MARK]}
            </span>
            <div className="flex flex-col gap-1">
              <p className="font-medium">{check.label}</p>
              {check.why && <p className="text-sm text-muted-foreground">{check.why}</p>}
              {check.fix && (
                <p className="text-sm">
                  <span className="font-medium text-primary">Como corrigir: </span>
                  {check.fix}
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
      {cover.references.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">Capas dos anúncios mais curtidos do tema:</p>
          <ul className="grid gap-3 sm:grid-cols-3">
            {cover.references.map((ref, index) => (
              <li key={ref.thumb_url} className="flex flex-col gap-2 rounded-[var(--radius-card)] bg-card p-3">
                {/* eslint-disable-next-line @next/next/no-img-element -- miniatura de outra loja */}
                <img src={ref.thumb_url} alt="" className="aspect-[4/3] w-full rounded-md object-cover" />
                {ref.url ? (
                  <a href={ref.url} target="_blank" rel="noreferrer" className="text-sm underline underline-offset-4 hover:text-primary">
                    {index + 1}. {ref.title}
                  </a>
                ) : (
                  <span className="text-sm">
                    {index + 1}. {ref.title}
                  </span>
                )}
                {cover.vs_top
                  .filter((c) => c.reference === index + 1)
                  .map((c) => (
                    <p key={c.text} className="text-sm">
                      {c.text}
                    </p>
                  ))}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
