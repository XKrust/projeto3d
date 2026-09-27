"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CATEGORY_LABELS, COUNTRY_LABELS, MARKET_LABELS } from "@/lib/radar-labels";
import type { RadarMeta } from "@/lib/radar-types";

// Sentinela para a opção "Todas"/"Todos": nunca vai para a URL, só remove o filtro.
const ALL_VALUE = "todas";

export function Filters({ meta }: { meta: RadarMeta }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const country = searchParams.get("country") || "BR";
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

  const europeCodes = new Set(meta.country_groups?.Europa ?? []);
  const mainCountries = meta.countries.filter((code) => !europeCodes.has(code));
  const europeCountries = meta.countries.filter((code) => europeCodes.has(code));

  return (
    <div className="flex flex-wrap gap-3">
      <Select value={country} onValueChange={(value) => setParam("country", String(value))}>
        <SelectTrigger aria-label="País">
          <SelectValue placeholder="País" />
        </SelectTrigger>
        <SelectContent>
          {mainCountries.map((code) => (
            <SelectItem key={code} value={code}>
              {COUNTRY_LABELS[code] ?? code}
            </SelectItem>
          ))}
          {europeCountries.length > 0 && (
            <SelectGroup>
              <SelectLabel>Europa</SelectLabel>
              {europeCountries.map((code) => (
                <SelectItem key={code} value={code}>
                  {COUNTRY_LABELS[code] ?? code}
                </SelectItem>
              ))}
            </SelectGroup>
          )}
        </SelectContent>
      </Select>

      <Select value={platform} onValueChange={(value) => setParam("platform", String(value))}>
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

      <Select value={market} onValueChange={(value) => setParam("market", String(value))}>
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

      <Select value={category} onValueChange={(value) => setParam("category", String(value))}>
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
