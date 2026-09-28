"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { AnalysisHistory } from "@/components/analisar/AnalysisHistory";
import { AnalysisProgress } from "@/components/analisar/AnalysisProgress";
import { AnalysisResult } from "@/components/analisar/AnalysisResult";
import { AnalyzeForm, type AnalyzeInput } from "@/components/analisar/AnalyzeForm";
import { BackendOffline } from "@/components/BackendOffline";
import { ApiError, apiGet, apiPostForm, BackendOfflineError } from "@/lib/api";
import type { Analysis, AnalysisSummary } from "@/lib/analyzer-types";
import { resizeImage } from "@/lib/resize-image";

async function buildForm(input: AnalyzeInput): Promise<FormData> {
  const form = new FormData();
  const ext = (blob: Blob) => (blob.type === "image/png" ? "png" : blob.type === "image/webp" ? "webp" : "jpg");
  for (const [index, file] of input.images.entries()) {
    const blob = await resizeImage(file);
    form.append("images", blob, `image-${index + 1}.${ext(blob)}`);
  }
  if (input.wireframe) {
    const blob = await resizeImage(input.wireframe);
    form.append("wireframe", blob, `wireframe.${ext(blob)}`);
  }
  form.append("authorship", input.authorship);
  form.append("market", input.market);
  if (input.hours.trim()) form.append("hours", input.hours.trim());
  for (const url of input.referenceUrls) form.append("reference_urls", url);
  return form;
}

// Analisador de modelo (Etapa 3a): envia imagens, mostra a análise honesta e o histórico.
export default function AnalisarPage() {
  const history = useSWR<AnalysisSummary[]>("/api/analyses", apiGet);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);
  const [offline, setOffline] = useState(false);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);

  async function submit(input: AnalyzeInput) {
    setBusy(true);
    setError(null);
    setAnalysis(null);
    try {
      const result = await apiPostForm<Analysis>("/api/analyze", await buildForm(input));
      setAnalysis(result);
      history.mutate();
    } catch (exc) {
      if (exc instanceof BackendOfflineError) setOffline(true);
      else if (exc instanceof ApiError) setError({ message: exc.message, status: exc.status });
      else setError({ message: "Algo deu errado. Tente de novo.", status: 0 });
    } finally {
      setBusy(false);
    }
  }

  async function open(id: number) {
    setError(null);
    try {
      setAnalysis(await apiGet<Analysis>(`/api/analyses/${id}`));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (exc) {
      if (exc instanceof BackendOfflineError) setOffline(true);
    }
  }

  if (offline || history.error instanceof BackendOfflineError) {
    return <BackendOffline />;
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-12 px-4 sm:px-8">
      <header className="flex flex-col gap-3">
        <h1 className="text-[length:var(--text-display)] font-bold">Analisar modelo</h1>
        <p className="max-w-[62ch] text-[length:var(--text-md)] leading-snug text-muted-foreground">
          Uma segunda opinião honesta: nota por critério, o que está forte, o que melhorar e como
          corrigir, comparando com modelos de grandes artistas do mesmo tema. É uma avaliação por
          IA, não um julgamento final.
        </p>
      </header>

      {analysis && !busy && <AnalysisResult analysis={analysis} />}

      <AnalyzeForm busy={busy} onSubmit={submit} />
      {busy && <AnalysisProgress />}
      {error && (
        <div role="alert" className="flex flex-col gap-2 rounded-[var(--radius-card)] bg-card p-5">
          <p className="text-destructive">{error.message}</p>
          {error.status === 409 && (
            <Link href="/config" className="text-sm underline underline-offset-4 hover:text-primary">
              Abrir Configurações
            </Link>
          )}
        </div>
      )}

      <AnalysisHistory items={history.data ?? []} onOpen={open} />
    </div>
  );
}
