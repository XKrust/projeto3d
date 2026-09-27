import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { COUNTRY_LABELS } from "@/lib/radar-labels";
import type { Weights } from "@/lib/config-types";

const ALL_COUNTRIES = Object.keys(COUNTRY_LABELS);

export function Preferences({
  countries,
  modelingDays,
  leadDays,
  weights,
  onCountriesChange,
  onModelingDaysChange,
  onLeadDaysChange,
  onWeightsChange,
}: {
  countries: string[];
  modelingDays: number;
  leadDays: number;
  weights: Weights;
  onCountriesChange: (countries: string[]) => void;
  onModelingDaysChange: (value: number) => void;
  onLeadDaysChange: (value: number) => void;
  onWeightsChange: (weights: Weights) => void;
}) {
  function toggleCountry(code: string, checked: boolean) {
    if (checked) {
      onCountriesChange([...countries, code]);
    } else {
      onCountriesChange(countries.filter((c) => c !== code));
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">Preferências</h2>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">Países</legend>
        <div className="flex flex-wrap gap-4">
          {ALL_COUNTRIES.map((code) => (
            <Label key={code} className="font-normal">
              <Checkbox
                checked={countries.includes(code)}
                onCheckedChange={(checked) => toggleCountry(code, checked)}
              />
              {COUNTRY_LABELS[code]}
            </Label>
          ))}
        </div>
      </fieldset>

      <div className="flex max-w-xs flex-col gap-1">
        <Label htmlFor="modeling-days">
          Quanto tempo você leva para modelar (dias)
        </Label>
        <Input
          id="modeling-days"
          type="number"
          min={1}
          max={180}
          value={modelingDays}
          onChange={(event) => onModelingDaysChange(Number(event.target.value))}
        />
      </div>

      <div className="flex max-w-xs flex-col gap-1">
        <Label htmlFor="lead-days">Antecedência de compra (dias)</Label>
        <Input
          id="lead-days"
          type="number"
          min={0}
          value={leadDays}
          onChange={(event) => onLeadDaysChange(Number(event.target.value))}
        />
      </div>

      <details>
        <summary className="cursor-pointer select-none text-sm font-medium">
          Avançado (pesos do score)
        </summary>
        <div className="mt-2 flex flex-wrap gap-4">
          <div className="flex max-w-32 flex-col gap-1">
            <Label htmlFor="weight-demand">Demanda</Label>
            <Input
              id="weight-demand"
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={weights.demand}
              onChange={(event) =>
                onWeightsChange({ ...weights, demand: Number(event.target.value) })
              }
            />
          </div>
          <div className="flex max-w-32 flex-col gap-1">
            <Label htmlFor="weight-momentum">Momentum</Label>
            <Input
              id="weight-momentum"
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={weights.momentum}
              onChange={(event) =>
                onWeightsChange({ ...weights, momentum: Number(event.target.value) })
              }
            />
          </div>
          <div className="flex max-w-32 flex-col gap-1">
            <Label htmlFor="weight-saturation">Saturação</Label>
            <Input
              id="weight-saturation"
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={weights.saturation}
              onChange={(event) =>
                onWeightsChange({
                  ...weights,
                  saturation: Number(event.target.value),
                })
              }
            />
          </div>
        </div>
      </details>
    </section>
  );
}
