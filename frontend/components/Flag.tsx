import { AU, BR, BY, CA, DE, ES, FR, GB, IT, JP, MX, NL, PL, RU, US } from "country-flag-icons/react/3x2";

// Bandeiras em SVG: emoji de bandeira não aparece no Windows (vira "BR" em letras).
const FLAGS = { BR, US, GB, DE, FR, ES, JP, RU, BY, MX, IT, CA, AU, PL, NL } as const;

export function Flag({ code, className }: { code: string; className?: string }) {
  const Component = FLAGS[code as keyof typeof FLAGS];
  if (!Component) {
    return null;
  }
  return <Component aria-hidden="true" className={className} />;
}
