import { ImageOff } from "lucide-react";

export function Poster({ src, className }: { src: string | null; className: string }) {
  if (!src) {
    return (
      <div className={`flex shrink-0 items-center justify-center rounded-lg bg-muted ${className}`}>
        <ImageOff className="size-5 text-muted-foreground" aria-hidden="true" />
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element -- capas vêm de domínios arbitrários
  return <img src={src} alt="" className={`shrink-0 rounded-lg object-cover ${className}`} />;
}
