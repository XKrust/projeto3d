"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  label: string;
  curto: string;
  emBreve?: boolean;
};

// "curto" é o rótulo em telas estreitas (≤ 640px), para a pílula caber em 320px.
const NAV_ITEMS: NavItem[] = [
  { href: "/radar", label: "Radar", curto: "Radar" },
  { href: "/sazonal", label: "Sazonal", curto: "Sazonal", emBreve: true },
  { href: "/hype", label: "Hype", curto: "Hype", emBreve: true },
  { href: "/analisar", label: "Analisar modelo", curto: "Analisar", emBreve: true },
  { href: "/config", label: "Configurações", curto: "Config" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Principal"
      className="fixed left-1/2 top-3 z-20 flex max-w-[calc(100vw-1rem)] -translate-x-1/2 items-center gap-1 rounded-full border border-border bg-[var(--color-glass)] py-1.5 pl-2 pr-1.5 shadow-[var(--shadow-float)] backdrop-blur-md sm:top-5 sm:gap-2 sm:pl-4"
    >
      <Link
        href="/radar"
        className="mr-1 hidden items-center gap-2 whitespace-nowrap font-mono text-sm font-medium tracking-tight text-foreground sm:flex"
      >
        <span
          aria-hidden="true"
          className="size-2 rounded-full bg-primary shadow-[0_0_0_4px_var(--color-accent-halo)]"
        />
        radar·3d
      </Link>
      <ul className="flex items-center">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                title={item.emBreve ? `${item.label} — em breve` : undefined}
                className={`block whitespace-nowrap rounded-full px-2 py-1.5 min-[360px]:px-2.5 text-[0.8125rem] transition-colors duration-150 sm:px-3.5 sm:text-sm ${
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
