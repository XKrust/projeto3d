import { SALE_CHANCE_DOT } from "@/lib/radar-labels";

// "Chance de venda" é sempre rotulada como estimativa (regra do projeto).
export function SaleChance({ chance }: { chance: string }) {
  const dot = SALE_CHANCE_DOT[chance] ?? SALE_CHANCE_DOT.Baixa;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
      <span aria-hidden="true" className={`size-1.5 rounded-full ${dot}`} />
      <span className="text-foreground">{chance}</span> (estimativa)
    </span>
  );
}
