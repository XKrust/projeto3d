"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Flag } from "@/components/Flag";
import { DEFAULT_COUNTRY, useCountry } from "@/lib/country";
import { COUNTRY_LABELS } from "@/lib/radar-labels";

type NavItem = {
  href: string;
  label: string;
  curto: string;
  emBreve?: boolean;
};

// "curto" é o rótulo em telas estreitas (≤ 640px), para a pílula caber em 320px.
const NAV_ITEMS: NavItem[] = [
  { href: "/radar", label: "Radar", curto: "Radar" },
  { href: "/sazonal", label: "Sazonal", curto: "Sazonal" },
  { href: "/hype", label: "Hype", curto: "Hype" },
  { href: "/analisar", label: "Analisar modelo", curto: "Analisar" },
  { href: "/config", label: "Configurações", curto: "Config" },
];

// Telas que dependem do país levam ?country= no link.
const COUNTRY_PAGES = new Set(["/radar", "/sazonal", "/hype"]);

export function Nav() {
  const pathname = usePathname();
  const country = useCountry() ?? DEFAULT_COUNTRY;
  const countryName = COUNTRY_LABELS[country] ?? country;

  return (
    <nav
      aria-label="Principal"
      className="fixed left-1/2 top-3 z-20 flex max-w-[calc(100vw-1rem)] -translate-x-1/2 items-center gap-1 rounded-full border border-border bg-[var(--color-glass)] p-1.5 shadow-[var(--shadow-float)] backdrop-blur-md sm:top-5 sm:gap-2"
    >
      <Link
        href="/"
        title="Trocar país"
        aria-label={`País: ${countryName}. Trocar país`}
        aria-current={pathname === "/" ? "page" : undefined}
        className={`flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full p-1 transition-colors duration-150 hover:bg-muted sm:pr-3 ${
          pathname === "/" ? "bg-muted" : ""
        }`}
      >
        <Flag
          code={country}
          className="h-4.5 w-7 rounded-[3px] shadow-[0_0_0_1px_var(--color-rule)]"
        />
        <span className="hidden text-sm font-medium text-foreground sm:inline">
          {countryName}
        </span>
      </Link>
      <ul className="flex items-center">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const href = COUNTRY_PAGES.has(item.href)
            ? `${item.href}?country=${country}`
            : item.href;
          return (
            <li key={item.href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                title={item.emBreve ? `${item.label} — em breve` : undefined}
                className={`block whitespace-nowrap rounded-full px-2 py-1.5 text-[0.8125rem] transition-colors duration-150 min-[360px]:px-2.5 sm:px-3.5 sm:text-sm ${
                  active
                    ? "bg-primary font-medium text-primary-foreground"
                    : item.emBreve
                      ? "text-muted-foreground/70 hover:bg-muted hover:text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <span className="sm:hidden">{item.curto}</span>
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
