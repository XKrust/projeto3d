import type { Variation } from "@/lib/sale-types";

// Variações que vendem (Etapa 3c): tipos fixos, com a prova nos anúncios do tema quando há.
export function VariationsBlock({ variations }: { variations: Variation[] }) {
  const fromAi = variations.some((v) => v.source === "ia");
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">
        {fromAi
          ? "Versões deste modelo que costumam vender mais, sugeridas pela IA."
          : "Sugestões do app a partir dos anúncios do tema (sem IA desta vez)."}
      </p>
      <ul className="flex flex-col">
        {variations.map((v) => (
          <li key={v.type} className="flex flex-col gap-1 border-t border-border py-3">
            <p className="font-medium">{v.label}</p>
            <p className="text-sm">
              {v.why}
              {v.flagged && <span className="ml-2 text-xs text-muted-foreground">(a IA exagerou aqui)</span>}
            </p>
            {v.evidence && v.evidence !== v.why && <p className="text-xs text-muted-foreground">{v.evidence}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
