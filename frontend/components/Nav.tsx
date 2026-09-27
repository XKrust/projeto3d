"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";

type NavItem = {
  href: string;
  label: string;
  selo?: string;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/radar", label: "Radar" },
  { href: "/sazonal", label: "Sazonal", selo: "Etapa 2" },
  { href: "/hype", label: "Hype", selo: "Etapa 2" },
  { href: "/analisar", label: "Analisar Modelo", selo: "Etapa 3" },
  { href: "/config", label: "Configurações" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="border-b">
      <ul className="mx-auto flex max-w-5xl flex-wrap items-center gap-1 px-4 py-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                {item.label}
                {item.selo && <Badge variant="secondary">{item.selo}</Badge>}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
