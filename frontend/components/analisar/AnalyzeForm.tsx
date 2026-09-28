"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";

export type AnalyzeInput = {
  images: File[];
  wireframe: File | null;
  authorship: "autoral" | "fanart";
  market: "print" | "digital";
  hours: string;
  referenceUrls: string[];
};

const MAX_IMAGES = 4;
const ACCEPT = "image/jpeg,image/png,image/webp";
export const FANART_NOTICE =
  "Fan-art usa personagem de outra pessoa: vender pode esbarrar em direitos autorais, e as lojas podem remover o anúncio. Confira as regras da loja antes de publicar.";

const radio = "size-4 accent-[var(--color-accent)]";

// Formulário da análise: imagens (1 a 4), wireframe opcional, 3 perguntas e links opcionais
// de referência. O botão só libera com 1 a 4 imagens.
export function AnalyzeForm({ busy, onSubmit }: { busy: boolean; onSubmit: (input: AnalyzeInput) => void }) {
  const [images, setImages] = useState<File[]>([]);
  const [wireframe, setWireframe] = useState<File | null>(null);
  const [authorship, setAuthorship] = useState<"autoral" | "fanart">("autoral");
  const [market, setMarket] = useState<"print" | "digital">("print");
  const [hours, setHours] = useState("");
  const [links, setLinks] = useState("");

  const previews = useMemo(() => images.map((file) => URL.createObjectURL(file)), [images]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  const countError = images.length > MAX_IMAGES ? "Envie de 1 a 4 imagens" : null;
  const ready = images.length >= 1 && images.length <= MAX_IMAGES && !busy;

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!ready) return;
    const referenceUrls = links
      .split(/\s+/)
      .map((line) => line.trim())
      .filter(Boolean);
    onSubmit({ images, wireframe, authorship, market, hours, referenceUrls });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-6 rounded-[var(--radius-card)] bg-card p-5 sm:p-6">
      <div className="flex flex-col gap-2">
        <label htmlFor="imagens" className="font-medium">
          Imagens do modelo (1 a 4)
        </label>
        <p className="text-sm text-muted-foreground">
          Renders ou fotos da peça, de ângulos diferentes. A imagem 1 é a capa.
        </p>
        <input
          id="imagens"
          type="file"
          accept={ACCEPT}
          multiple
          onChange={(e) => setImages(Array.from(e.target.files ?? []))}
          className="text-sm file:mr-3 file:rounded-full file:border-0 file:bg-muted file:px-4 file:py-2 file:text-foreground"
        />
        {images.length > 0 && (
          <ul aria-label="Imagens escolhidas" className="flex flex-wrap gap-2">
            {previews.map((url, index) => (
              <li key={url} className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element -- prévia local (blob:) */}
                <img src={url} alt={`Imagem ${index + 1}`} className="size-20 rounded-md object-cover" />
                <button
                  type="button"
                  onClick={() => setImages(images.filter((_, i) => i !== index))}
                  aria-label={`Remover imagem ${index + 1}`}
                  className="absolute -right-1.5 -top-1.5 rounded-full bg-muted px-1.5 text-xs"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {countError && <p className="text-sm text-destructive">{countError}</p>}
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="wireframe" className="font-medium">
          Wireframe (opcional)
        </label>
        <p className="text-sm text-muted-foreground">Sem ele, a topologia fica &quot;não avaliável&quot;.</p>
        <input
          id="wireframe"
          type="file"
          accept={ACCEPT}
          onChange={(e) => setWireframe(e.target.files?.[0] ?? null)}
          className="text-sm file:mr-3 file:rounded-full file:border-0 file:bg-muted file:px-4 file:py-2 file:text-foreground"
        />
      </div>

      <div className="grid gap-5 sm:grid-cols-3">
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 font-medium">Autoria</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="autoria" className={radio} checked={authorship === "autoral"} onChange={() => setAuthorship("autoral")} />
            Autoral
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="autoria" className={radio} checked={authorship === "fanart"} onChange={() => setAuthorship("fanart")} />
            Fan-art
          </label>
        </fieldset>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 font-medium">Mercado</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="mercado" className={radio} checked={market === "print"} onChange={() => setMarket("print")} />
            Impressão 3D
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="mercado" className={radio} checked={market === "digital"} onChange={() => setMarket("digital")} />
            Digital
          </label>
        </fieldset>
        <div className="flex flex-col gap-2">
          <label htmlFor="horas" className="font-medium">
            Horas gastas (opcional)
          </label>
          <input
            id="horas"
            type="number"
            min={0}
            step={0.5}
            value={hours}
            onChange={(e) => setHours(e.target.value)}
            className="h-9 w-28 rounded-md border border-border bg-transparent px-3 text-sm"
          />
        </div>
      </div>

      {authorship === "fanart" && (
        <p className="border-l-2 border-[var(--color-signal-mid)] pl-3 text-sm text-muted-foreground">{FANART_NOTICE}</p>
      )}

      <div className="flex flex-col gap-2">
        <label htmlFor="referencias" className="font-medium">
          Links de referência do Sketchfab (opcional, até 2)
        </label>
        <p className="text-sm text-muted-foreground">
          Modelos de artistas que você admira. Sem link, o app escolhe os mais destacados do tema.
        </p>
        <textarea
          id="referencias"
          rows={2}
          value={links}
          onChange={(e) => setLinks(e.target.value)}
          placeholder="https://sketchfab.com/3d-models/…"
          className="rounded-md border border-border bg-transparent p-3 text-sm"
        />
      </div>

      <div>
        <Button type="submit" disabled={!ready} className="h-10 rounded-full px-6">
          {busy ? "Analisando…" : "Analisar"}
        </Button>
      </div>
    </form>
  );
}
