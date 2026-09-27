"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CATEGORY_LABELS, MARKET_LABELS } from "@/lib/radar-labels";
import type { RadarMeta } from "@/lib/radar-types";

// Sentinela para a opção "Todas"/"Todos": nunca vai para a URL, só remove o filtro.
const ALL_VALUE = "todas";

export function Filters({ meta }: { meta: RadarMeta }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const platform = searchParams.get("platform") || ALL_VALUE;
  const market = searchParams.get("market") || ALL_VALUE;
  const category = searchParams.get("category") || ALL_VALUE;

  function setParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === ALL_VALUE) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  // Mapas valor → rótulo: fazem o campo mostrar o nome em vez do código.
  const platformItems = {
    [ALL_VALUE]: "Todas as plataformas",
    ...Object.fromEntries(meta.platforms.map((item) => [item.slug, item.name])),
  };
  const marketItems = {
    [ALL_VALUE]: "Todos os mercados",
    ...Object.fromEntries(meta.markets.map((slug) => [slug, MARKET_LABELS[slug] ?? slug])),
  };
  const categoryItems = {
    [ALL_VALUE]: "Todas as categorias",
    ...Object.fromEntries(meta.categories.map((slug) => [slug, CATEGORY_LABELS[slug] ?? slug])),
  };

  return (
    <div className="flex flex-wrap gap-2">
      <Select items={platformItems} value={platform} onValueChange={(value) => setParam("platform", String(value))}>
        <SelectTrigger aria-label="Plataforma">
          <SelectValue placeholder="Plataforma" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>Todas</SelectItem>
          {meta.platforms.map((item) => (
            <SelectItem key={item.slug} value={item.slug}>
              {item.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select items={marketItems} value={market} onValueChange={(value) => setParam("market", String(value))}>
        <SelectTrigger aria-label="Mercado">
          <SelectValue placeholder="Mercado" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>Todos</SelectItem>
          {meta.markets.map((slug) => (
            <SelectItem key={slug} value={slug}>
              {MARKET_LABELS[slug] ?? slug}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select items={categoryItems} value={category} onValueChange={(value) => setParam("category", String(value))}>
        <SelectTrigger aria-label="Categoria">
          <SelectValue placeholder="Categoria" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>Todas</SelectItem>
          {meta.categories.map((slug) => (
            <SelectItem key={slug} value={slug}>
              {CATEGORY_LABELS[slug] ?? slug}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
