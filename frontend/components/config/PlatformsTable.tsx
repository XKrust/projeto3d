"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiPut } from "@/lib/api";
import { COUNTRY_LABELS } from "@/lib/radar-labels";
import type { PlatformConfig } from "@/lib/config-types";

export function PlatformsTable({
  platforms,
  countries,
}: {
  platforms: PlatformConfig[];
  countries: string[];
}) {
  const [edited, setEdited] = useState<Record<string, PlatformConfig>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function currentValue(platform: PlatformConfig): PlatformConfig {
    return edited[platform.slug] ?? platform;
  }

  function updateFee(platform: PlatformConfig, rawValue: string) {
    const fee_pct = rawValue === "" ? null : Number(rawValue);
    setEdited((prev) => ({
      ...prev,
      [platform.slug]: { ...currentValue(platform), fee_pct },
    }));
  }

  function updateStrength(platform: PlatformConfig, country: string, rawValue: string) {
    const current = currentValue(platform);
    setEdited((prev) => ({
      ...prev,
      [platform.slug]: {
        ...current,
        strength: { ...current.strength, [country]: Number(rawValue) },
      },
    }));
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      for (const slug of Object.keys(edited)) {
        const platform = edited[slug];
        await apiPut(`/api/platforms/${slug}`, {
          fee_pct: platform.fee_pct,
          strength: platform.strength,
        });
      }
      setMessage("Salvo!");
      setEdited({});
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Erro inesperado");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">Plataformas</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Plataforma</TableHead>
            <TableHead>Taxa (%)</TableHead>
            {countries.map((code) => (
              <TableHead key={code}>{COUNTRY_LABELS[code] ?? code}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {platforms.map((platform) => {
            const value = currentValue(platform);
            return (
              <TableRow key={platform.slug}>
                <TableCell>{platform.name}</TableCell>
                <TableCell>
                  <Input
                    aria-label={`Taxa de ${platform.name}`}
                    type="number"
                    step="0.1"
                    min={0}
                    max={100}
                    className="w-20"
                    // Taxa nao confirmada (null): campo fica em branco mas mostra
                    // "—" como placeholder, conforme docs/plataformas.md.
                    placeholder={value.fee_pct === null ? "—" : undefined}
                    value={value.fee_pct ?? ""}
                    onChange={(event) => updateFee(platform, event.target.value)}
                  />
                </TableCell>
                {countries.map((code) => (
                  <TableCell key={code}>
                    <Input
                      aria-label={`Força de ${platform.name} em ${COUNTRY_LABELS[code] ?? code}`}
                      type="number"
                      step="0.1"
                      min={0}
                      max={1}
                      className="w-16"
                      value={value.strength[code] ?? ""}
                      onChange={(event) =>
                        updateStrength(platform, code, event.target.value)
                      }
                    />
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <div className="flex items-center gap-2">
        <Button
          onClick={handleSave}
          disabled={saving || Object.keys(edited).length === 0}
        >
          Salvar plataformas
        </Button>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
      </div>
    </section>
  );
}
