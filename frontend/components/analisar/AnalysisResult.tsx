import { FANART_NOTICE } from "@/components/analisar/AnalyzeForm";
import { SaleSection } from "@/components/analisar/SaleSection";
import { CRITERIA_LABELS, formatScore, type Analysis, type Improvement } from "@/lib/analyzer-types";

function Flag({ flagged }: { flagged: boolean }) {
  return flagged ? (
    <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
      a IA exagerou aqui
    </span>
  ) : null;
}

function Where({ image, area }: { image: number | null; area: string }) {
  return (
    <span className="text-xs uppercase tracking-[0.08em] text-muted-foreground">
      {image ? `Imagem ${image} · ` : ""}
      {area}
    </span>
  );
}

function ImprovementItem({ item }: { item: Improvement }) {
  return (
    <li className="flex flex-col gap-1.5 border-t border-border py-4">
      <Where image={item.image} area={item.area} />
      <p className="font-medium text-foreground">
        {item.problem}
        <Flag flagged={item.flagged} />
      </p>
      <p className="text-sm">
        <span className="font-medium text-primary">Como corrigir: </span>
        {item.fix}
      </p>
      {item.gain && <p className="text-sm text-muted-foreground">Ganho: {item.gain}</p>}
    </li>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-[length:var(--text-lg)] font-bold">{title}</h3>
      {children}
    </section>
  );
}

// Resultado da análise (spec 3a §9). A nota geral é a média das notas dos critérios,
// calculada pelo app; tudo rotulado como avaliação por IA.
export function AnalysisResult({ analysis }: { analysis: Analysis }) {
  const { result, identified, references, previous } = analysis;
  const comparisons = (index: number) => result.reference_comparison.filter((c) => c.reference === index + 1);

  return (
    <section aria-label="Resultado da análise" className="flex flex-col gap-10">
      <header className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-end">
        <div className="flex flex-col gap-2">
          <p className="flex items-baseline gap-3 font-heading font-extrabold leading-none tracking-[-0.045em]">
            <span className="tnum text-[length:var(--text-figure)]">{formatScore(result.overall)}</span>
            <span className="text-[length:var(--text-md)] font-medium tracking-normal text-muted-foreground">
              {result.overall === null ? "não avaliável pelas imagens" : "/10 · avaliação por IA"}
            </span>
          </p>
          {previous && previous.overall !== null && result.overall !== null && (
            <p className="text-sm text-muted-foreground">
              antes: {formatScore(previous.overall)} → agora: {formatScore(result.overall)}
            </p>
          )}
          <h2 className="text-[length:var(--text-display)] font-bold">{identified.theme}</h2>
          <p className="text-sm text-muted-foreground">
            {identified.style && `${identified.style} · `}
            {analysis.input.market === "print" ? "impressão 3D" : "digital"}
            {analysis.input.hours ? ` · ${analysis.input.hours} h` : ""}
          </p>
        </div>
        {result.top_actions.length > 0 && (
          <div className="rounded-[var(--radius-card)] bg-card p-5">
            <p className="mb-3 text-xs uppercase tracking-[0.08em] text-muted-foreground">O que fazer primeiro</p>
            <ol className="flex list-decimal flex-col gap-2 pl-5">
              {result.top_actions.map((action) => (
                <li key={action} className="text-foreground">
                  {action}
                </li>
              ))}
            </ol>
          </div>
        )}
      </header>

      {analysis.input.authorship === "fanart" && (
        <p className="border-l-2 border-[var(--color-signal-mid)] pl-3 text-sm text-muted-foreground">{FANART_NOTICE}</p>
      )}

      <Section title="Nota por critério">
        <ul className="flex flex-col">
          {Object.entries(result.criteria).map(([slug, criterion]) => (
            <li key={slug} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] gap-x-4 gap-y-1 border-t border-border py-3 sm:grid-cols-[14rem_6rem_minmax(0,1fr)]">
              <span className="font-medium">{CRITERIA_LABELS[slug] ?? slug}</span>
              <span className="tnum sm:order-none">
                {criterion.score === null ? (
                  <span className="text-muted-foreground">não avaliável</span>
                ) : (
                  <span className="flex items-center gap-2">
                    <span className="h-1.5 w-12 overflow-hidden rounded-full bg-muted" aria-hidden="true">
                      <span className="block h-full bg-primary" style={{ width: `${criterion.score * 10}%` }} />
                    </span>
                    {criterion.score}/10
                  </span>
                )}
              </span>
              <span className="col-span-2 text-sm text-muted-foreground sm:col-span-1">{criterion.why}</span>
            </li>
          ))}
        </ul>
      </Section>

      <div className="grid gap-10 lg:grid-cols-2">
        <Section title="Pontos fortes">
          {result.strengths.length ? (
            <ul className="flex flex-col">
              {result.strengths.map((s) => (
                <li key={s.text} className="flex flex-col gap-1 border-t border-border py-3">
                  <Where image={s.image} area={s.area} />
                  <p>
                    {s.text}
                    <Flag flagged={s.flagged} />
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">A IA não apontou pontos fortes específicos nas imagens.</p>
          )}
        </Section>
        <Section title="O que melhorar">
          {result.improvements.length ? (
            <ul className="flex flex-col">
              {result.improvements.map((item) => (
                <ImprovementItem key={`${item.area}-${item.problem}`} item={item} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Nenhum problema visível com certeza nas imagens.</p>
          )}
        </Section>
      </div>

      {result.to_check.length > 0 && (
        <Section title="Vale conferir">
          <p className="text-sm text-muted-foreground">A IA não teve certeza pelas imagens. Confira no arquivo.</p>
          <ul className="flex flex-col">
            {result.to_check.map((item) => (
              <ImprovementItem key={`${item.area}-${item.problem}`} item={item} />
            ))}
          </ul>
        </Section>
      )}

      <Section title="Comparação com grandes artistas">
        {analysis.references_note && <p className="text-sm text-muted-foreground">{analysis.references_note}</p>}
        <ul className="grid gap-3 sm:grid-cols-3">
          {references.map((ref, index) => (
            <li key={ref.url} className="flex flex-col gap-3 rounded-[var(--radius-card)] bg-card p-4">
              {ref.thumb_url && (
                // eslint-disable-next-line @next/next/no-img-element -- miniatura do Sketchfab
                <img src={ref.thumb_url} alt="" className="aspect-[4/3] w-full rounded-md object-cover" />
              )}
              <a href={ref.url} target="_blank" rel="noreferrer" className="font-medium underline underline-offset-4 hover:text-primary">
                {index + 1}. {ref.name}
              </a>
              <span className="text-sm text-muted-foreground">
                {ref.artist}
                {ref.source === "usuario" ? " · escolhida por você" : ""}
              </span>
              {comparisons(index).map((c) => (
                <p key={c.text} className="text-sm">
                  {c.text}
                  <Flag flagged={c.flagged} />
                </p>
              ))}
            </li>
          ))}
        </ul>
      </Section>

      <SaleSection key={analysis.id} analysisId={analysis.id} initialSale={analysis.sale ?? null} />
    </section>
  );
}
