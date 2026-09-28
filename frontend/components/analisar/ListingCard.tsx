"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { LANG_LABELS, type Listing } from "@/lib/sale-types";

export function CopyButton({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }
  return (
    <Button type="button" variant="outline" size="sm" className="rounded-full px-3" onClick={copy}>
      {copied ? "Copiado" : label}
    </Button>
  );
}

// Anúncio pronto de uma loja num idioma (spec 3b §11), com botões de copiar.
export function ListingCard({ listing, storeName }: { listing: Listing; storeName: string }) {
  return (
    <article
      aria-label={`Anúncio ${storeName} em ${LANG_LABELS[listing.lang]}`}
      className="flex flex-col gap-3 rounded-[var(--radius-card)] bg-card p-5"
    >
      <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">
        {storeName} · {LANG_LABELS[listing.lang]}
        {listing.trimmed && " · cortado para caber no limite da loja"}
      </p>
      <p className="font-medium text-foreground">{listing.title}</p>
      {listing.tags.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Tags">
          {listing.tags.map((tag) => (
            <li key={tag} className="rounded-full border border-border px-2.5 py-0.5 text-xs">
              {tag}
            </li>
          ))}
        </ul>
      )}
      {listing.description && <p className="whitespace-pre-line text-sm">{listing.description}</p>}
      {listing.flagged && (
        <p className="text-xs text-muted-foreground">A IA exagerou em algum ponto: revise antes de publicar.</p>
      )}
      <div className="flex flex-wrap gap-2">
        <CopyButton label="Copiar título" text={listing.title} />
        {listing.tags.length > 0 && <CopyButton label="Copiar tags" text={listing.tags.join(", ")} />}
        {listing.description && <CopyButton label="Copiar descrição" text={listing.description} />}
      </div>
    </article>
  );
}
