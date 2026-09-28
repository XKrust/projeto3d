"use client";

import { useState } from "react";

// Checklist de lançamento (spec 3b §8). Marcar é só visual: não fica salvo.
export function LaunchChecklist({ steps }: { steps: string[] }) {
  const [done, setDone] = useState<Set<number>>(new Set());
  function toggle(index: number) {
    setDone((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }
  return (
    <ol className="flex flex-col">
      {steps.map((step, index) => (
        <li key={step} className="border-t border-border py-3">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={done.has(index)}
              onChange={() => toggle(index)}
              className="mt-1 size-4 accent-[var(--color-accent)]"
            />
            <span className={done.has(index) ? "text-muted-foreground line-through" : ""}>{step}</span>
          </label>
        </li>
      ))}
    </ol>
  );
}
