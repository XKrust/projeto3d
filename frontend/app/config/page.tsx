"use client";

import { useState } from "react";
import useSWR from "swr";
import { apiGet, apiPost, apiPut, BackendOfflineError } from "@/lib/api";
import { BackendOffline } from "@/components/BackendOffline";
import { ApiKeys } from "@/components/config/ApiKeys";
import { Preferences } from "@/components/config/Preferences";
import { PlatformsTable } from "@/components/config/PlatformsTable";
import { SourcesHealth } from "@/components/config/SourcesHealth";
import { Button } from "@/components/ui/button";
import type {
  PlatformConfig,
  SettingsData,
  SourceHealth as SourceHealthType,
  Weights,
} from "@/lib/config-types";

function Loading() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <p className="text-muted-foreground">Carregando...</p>
    </div>
  );
}

export default function ConfigPage() {
  const {
    data: settings,
    error: settingsError,
    isLoading: settingsLoading,
  } = useSWR<SettingsData>("/api/settings", apiGet);
  const {
    data: sources,
    error: sourcesError,
    isLoading: sourcesLoading,
    mutate: mutateSources,
  } = useSWR<SourceHealthType[]>("/api/sources", apiGet);
  const {
    data: platforms,
    error: platformsError,
    isLoading: platformsLoading,
  } = useSWR<PlatformConfig[]>("/api/platforms", apiGet);

  const [form, setForm] = useState<SettingsData | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [collectingSource, setCollectingSource] = useState<string | null>(null);

  // Copia `settings` para o estado editável assim que chega (padrão do React
  // para inicializar estado a partir de props/dados assíncronos, sem efeito:
  // https://react.dev/learn/you-might-not-need-an-effect).
  if (settings && !form) {
    setForm(settings);
  }

  if (
    settingsError instanceof BackendOfflineError ||
    sourcesError instanceof BackendOfflineError ||
    platformsError instanceof BackendOfflineError
  ) {
    return <BackendOffline />;
  }

  if (settingsLoading || sourcesLoading || platformsLoading || !form) {
    return <Loading />;
  }

  const loadError = settingsError ?? sourcesError ?? platformsError;
  if (loadError) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <p className="text-destructive">
          {loadError instanceof Error ? loadError.message : "Erro inesperado"}
        </p>
      </div>
    );
  }

  async function handleSave() {
    if (!form) {
      return;
    }
    setSaving(true);
    setSaveMessage(null);
    try {
      const updated = await apiPut<SettingsData>("/api/settings", form);
      setForm(updated);
      setSaveMessage("Salvo!");
    } catch (err) {
      setSaveMessage(err instanceof Error ? err.message : "Erro inesperado");
    } finally {
      setSaving(false);
    }
  }

  async function handleCollect(name: string) {
    setCollectingSource(name);
    try {
      await apiPost(`/api/collect?source=${name}`);
      await mutateSources();
    } finally {
      setCollectingSource(null);
    }
  }

  function updateForm(patch: Partial<SettingsData>) {
    setForm((prev) => (prev ? { ...prev, ...patch } : prev));
  }

  return (
    <div className="flex flex-1 flex-col gap-8 p-6">
      <h1 className="text-2xl font-semibold">Configurações</h1>

      {sources && (
        <SourcesHealth
          sources={sources}
          onCollect={handleCollect}
          collectingSource={collectingSource}
        />
      )}

      <div className="flex flex-col gap-6">
        <ApiKeys
          apiKeys={form.api_keys}
          onChange={(key, value) =>
            updateForm({ api_keys: { ...form.api_keys, [key]: value } })
          }
        />

        <Preferences
          countries={form.countries}
          modelingDays={form.modeling_days}
          leadDays={form.lead_days}
          weights={form.weights}
          onCountriesChange={(countries) => updateForm({ countries })}
          onModelingDaysChange={(modeling_days) => updateForm({ modeling_days })}
          onLeadDaysChange={(lead_days) => updateForm({ lead_days })}
          onWeightsChange={(weights: Weights) => updateForm({ weights })}
        />

        <div className="flex items-center gap-2">
          <Button onClick={handleSave} disabled={saving}>
            Salvar
          </Button>
          {saveMessage && (
            <p className="text-sm text-muted-foreground">{saveMessage}</p>
          )}
        </div>
      </div>

      {platforms && (
        <PlatformsTable platforms={platforms} countries={form.countries} />
      )}
    </div>
  );
}
