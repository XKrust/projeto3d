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
import { COUNTRY_LABELS } from "@/lib/radar-labels";

// Seletor de país que grava a escolha em ?country= (Sazonal e Hype).
export function CountrySelect({
  countries,
  europe,
}: {
  countries: string[];
  europe: string[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const country = searchParams.get("country") || "BR";

  const items = Object.fromEntries(countries.map((code) => [code, COUNTRY_LABELS[code] ?? code]));
  const europeSet = new Set(europe);
  const main = countries.filter((code) => !europeSet.has(code));
  const european = countries.filter((code) => europeSet.has(code));

  function change(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("country", value);
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <Select items={items} value={country} onValueChange={(value) => change(String(value))}>
      <SelectTrigger aria-label="País">
        <SelectValue placeholder="País" />
      </SelectTrigger>
      <SelectContent>
        {main.map((code) => (
          <SelectItem key={code} value={code}>
            {COUNTRY_LABELS[code] ?? code}
          </SelectItem>
        ))}
        {european.length > 0 && (
          <SelectGroup>
            <SelectLabel>Europa</SelectLabel>
            {european.map((code) => (
              <SelectItem key={code} value={code}>
                {COUNTRY_LABELS[code] ?? code}
              </SelectItem>
            ))}
          </SelectGroup>
        )}
      </SelectContent>
    </Select>
  );
}
