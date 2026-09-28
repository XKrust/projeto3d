"use client";

import { useEffect, useState } from "react";

const STEPS = ["Identificando o modelo…", "Buscando referências…", "Comparando com as referências…"];
const STEP_MS = 8000;

// Mensagens fixas enquanto a análise roda (20–40 s). Não é progresso medido: só troca de
// texto a cada 8 s para mostrar que está andando.
export function AnalysisProgress() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), STEP_MS);
    return () => clearInterval(timer);
  }, []);
  return (
    <p role="status" className="rounded-[var(--radius-card)] bg-card p-5 text-[length:var(--text-md)]">
      {STEPS[step]}
      <span className="block text-sm text-muted-foreground">Leva uns 20 a 40 segundos.</span>
    </p>
  );
}
