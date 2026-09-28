"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { LoaderCircle, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { IMAGE_ACCEPT, MODEL_ACCEPT, modelExtension } from "@/lib/model-files";
import { cn } from "@/lib/utils";

export type AnalyzeInput = {
  images: File[];
  wireframe: File | null;
  authorship: "autoral" | "fanart";
  market: "print" | "digital";
  hours: string;
  referenceUrls: string[];
};

const MAX_IMAGES = 4;
const IMAGE_TYPES = IMAGE_ACCEPT.split(",");
export const FANART_NOTICE =
  "Fan-art usa personagem de outra pessoa: vender pode esbarrar em direitos autorais, e as lojas podem remover o anúncio. Confira as regras da loja antes de publicar.";
const MSG_RENDER_FAILED = "Não consegui abrir esse arquivo 3D. Exporte em STL, OBJ ou GLB, ou envie prints do modelo.";

const radio = "size-4 accent-[var(--color-accent)]";

function unsupportedMessage(name: string) {
  const zip = /\.(zip|rar|7z)$/i.test(name);
  return zip
    ? `${name} é um arquivo compactado: extraia e envie o STL, OBJ ou GLB de dentro dele.`
    : `Não dá para ler ${name}. Envie imagens (PNG, JPG ou WEBP) ou o modelo em STL, OBJ, GLB, 3MF ou FBX.`;
}

// Formulário da análise: imagens (1 a 4) ou o arquivo 3D (o app tira 4 fotos dele no próprio
// computador), wireframe opcional, 3 perguntas e links opcionais de referência. O botão só
// libera com 1 a 4 imagens.
export function AnalyzeForm({ busy, onSubmit }: { busy: boolean; onSubmit: (input: AnalyzeInput) => void }) {
  const [images, setImages] = useState<File[]>([]);
  const [wireframe, setWireframe] = useState<File | null>(null);
  const [authorship, setAuthorship] = useState<"autoral" | "fanart">("autoral");
  const [market, setMarket] = useState<"print" | "digital">("print");
  const [hours, setHours] = useState("");
  const [links, setLinks] = useState("");
  const [dragging, setDragging] = useState(false);
  const [rendering, setRendering] = useState<string | null>(null);
  const [fileNote, setFileNote] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const imagesInput = useRef<HTMLInputElement>(null);
  const wireframeInput = useRef<HTMLInputElement>(null);

  const previews = useMemo(() => images.map((file) => URL.createObjectURL(file)), [images]);
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  const countError = images.length > MAX_IMAGES ? "Envie de 1 a 4 imagens" : null;
  const ready = images.length >= 1 && images.length <= MAX_IMAGES && !busy && !rendering;

  async function addFiles(files: File[]) {
    if (!files.length) return;
    const model = files.find((file) => modelExtension(file));
    const pictures = files.filter((file) => IMAGE_TYPES.includes(file.type));
    const unsupported = files.find((file) => !modelExtension(file) && !IMAGE_TYPES.includes(file.type));
    setFileError(unsupported ? unsupportedMessage(unsupported.name) : null);
    if (!model) {
      if (pictures.length) setImages((current) => [...current, ...pictures]);
      return;
    }
    // Arquivo 3D: as 4 fotos dele ocupam as 4 vagas (dá para trocar qualquer uma depois).
    setRendering(model.name);
    try {
      const { renderModel } = await import("@/lib/render-model");
      setImages(await renderModel(model));
      setFileNote(
        `Fotos tiradas de ${model.name}: capa em 3/4, frente, lado e costas. Pode trocar qualquer uma por um print seu.`,
      );
    } catch (error) {
      setFileError(error instanceof Error && error.name === "ModelRenderError" ? error.message : MSG_RENDER_FAILED);
    } finally {
      setRendering(null);
    }
  }

  function removeImage(index: number) {
    const next = images.filter((_, i) => i !== index);
    setImages(next);
    if (!next.length) setFileNote(null);
  }

  function openPicker() {
    if (!rendering) imagesInput.current?.click();
  }

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
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="imagens" className="font-medium">
            Imagens do modelo (1 a 4)
          </label>
          <p className="text-sm text-muted-foreground">
            Renders ou fotos da peça, de ângulos diferentes, ou o próprio arquivo 3D: o app tira as fotos
            dele sozinho. A imagem 1 é a capa.
          </p>
        </div>

        <div
          role="button"
          tabIndex={0}
          aria-busy={rendering ? true : undefined}
          onClick={openPicker}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              openPicker();
            }
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            if (!rendering) void addFiles(Array.from(event.dataTransfer.files));
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[var(--radius-card)] border-2 border-dashed px-6 py-9 text-center transition-colors outline-none focus-visible:border-primary",
            dragging ? "border-primary bg-primary/10" : "border-border hover:border-primary/60 hover:bg-muted/40",
            rendering && "cursor-wait",
          )}
        >
          {rendering ? (
            <>
              <LoaderCircle aria-hidden="true" className="size-7 animate-spin text-primary" />
              <p className="font-medium">Tirando as fotos de {rendering}…</p>
              <p className="text-sm text-muted-foreground">Leva alguns segundos.</p>
            </>
          ) : (
            <>
              <Upload aria-hidden="true" className="size-7 text-primary" />
              <p className="font-medium">Arraste aqui as imagens ou o arquivo 3D</p>
              <p className="text-sm text-muted-foreground">
                ou <span className="text-foreground underline underline-offset-4">clique para escolher</span>
              </p>
              <p className="text-xs text-muted-foreground">
                Imagens PNG, JPG ou WEBP · Arquivo 3D STL, OBJ, GLB, 3MF ou FBX
              </p>
            </>
          )}
          <input
            ref={imagesInput}
            id="imagens"
            type="file"
            accept={`${IMAGE_ACCEPT},${MODEL_ACCEPT}`}
            multiple
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => {
              void addFiles(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
            className="sr-only"
          />
        </div>

        {images.length > 0 && (
          <ul aria-label="Imagens escolhidas" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {previews.map((url, index) => (
              <li key={url} className="relative overflow-hidden rounded-lg border border-border bg-muted/30">
                {/* eslint-disable-next-line @next/next/no-img-element -- prévia local (blob:) */}
                <img src={url} alt={`Imagem ${index + 1}`} className="aspect-square w-full object-cover" />
                {index === 0 && (
                  <span className="absolute left-2 top-2 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                    Capa
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => removeImage(index)}
                  aria-label={`Remover imagem ${index + 1}`}
                  className="absolute right-2 top-2 flex size-7 items-center justify-center rounded-full bg-black/60 text-white transition-colors hover:bg-black/80"
                >
                  <X aria-hidden="true" className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
        {fileNote && images.length > 0 && <p className="text-sm text-muted-foreground">{fileNote}</p>}
        {fileError && <p className="text-sm text-destructive">{fileError}</p>}
        {countError && <p className="text-sm text-destructive">{countError}</p>}
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="wireframe" className="font-medium">
          Wireframe (opcional)
        </label>
        <p className="text-sm text-muted-foreground">
          Print da malha em modo wireframe. Sem ele, a topologia fica &quot;não avaliável&quot;.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => wireframeInput.current?.click()}
            className="h-9 rounded-full px-4"
          >
            Escolher imagem
          </Button>
          <span className="text-sm text-muted-foreground">{wireframe ? wireframe.name : "Nenhuma imagem escolhida"}</span>
          {wireframe && (
            <button
              type="button"
              onClick={() => {
                setWireframe(null);
                if (wireframeInput.current) wireframeInput.current.value = "";
              }}
              className="text-sm underline underline-offset-4 hover:text-primary"
            >
              Remover
            </button>
          )}
          <input
            ref={wireframeInput}
            id="wireframe"
            type="file"
            accept={IMAGE_ACCEPT}
            onChange={(event) => setWireframe(event.target.files?.[0] ?? null)}
            className="sr-only"
          />
        </div>
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
            placeholder="ex.: 12"
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
