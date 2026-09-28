import { CopyButton } from "@/components/analisar/ListingCard";
import type { Sale } from "@/lib/sale-types";

// Onde divulgar (Etapa 3c): comunidades do Reddit (onde o tema está em alta ou do tipo de
// modelo) e hashtags reais dos anúncios do tema.
export function PromotionBlock({ promotion }: { promotion: NonNullable<Sale["promotion"]> }) {
  const fromTopic = promotion.communities.some((c) => c.source === "tema");
  return (
    <div className="flex flex-col gap-4">
      {promotion.communities.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            {fromTopic
              ? "Comunidades onde o tema está em alta no Reddit:"
              : "O app ainda não viu o tema no Reddit. Comunidades do tipo de modelo:"}
          </p>
          <ul className="flex flex-col">
            {promotion.communities.map((community) => (
              <li key={community.name} className="flex flex-wrap items-baseline gap-x-3 border-t border-border py-3">
                <a
                  href={community.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium underline underline-offset-4 hover:text-primary"
                >
                  {community.name}
                </a>
                <span className="text-sm text-muted-foreground">{community.why}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {promotion.hashtags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <ul className="flex flex-wrap gap-1.5" aria-label="Hashtags">
            {promotion.hashtags.map((tag) => (
              <li key={tag} className="rounded-full border border-border px-2.5 py-0.5 text-xs">
                {tag}
              </li>
            ))}
          </ul>
          <CopyButton label="Copiar hashtags" text={promotion.hashtags.join(" ")} />
        </div>
      )}
      <p className="border-l-2 border-[var(--color-signal-mid)] pl-3 text-sm text-muted-foreground">{promotion.note}</p>
    </div>
  );
}
