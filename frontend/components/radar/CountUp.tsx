"use client";

import { useEffect, useState } from "react";

const DURATION_MS = 520;

// Conta de 0 até `value` uma vez, ao aparecer. Com "reduzir movimento" ligado,
// mostra o número final direto. O valor final fica sempre no aria-label.
export function CountUp({ value, className }: { value: number; className?: string }) {
  const target = Math.round(value);
  const [shown, setShown] = useState(target);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION_MS);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(Math.round(target * eased));
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target]);

  return (
    <span className={className} aria-label={String(target)}>
      <span aria-hidden="true">{shown}</span>
    </span>
  );
}
