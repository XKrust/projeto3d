"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";
import type { SparklinePoint } from "@/lib/radar-types";

// Linha dos últimos dias de demanda. `height` maior + área preenchida no destaque;
// fina e sem área nas linhas do ranking.
export function Sparkline({
  data,
  height = 36,
  filled = false,
}: {
  data: SparklinePoint[];
  height?: number;
  filled?: boolean;
}) {
  if (data.length < 2) {
    return filled ? (
      <div
        className="flex items-center justify-center rounded-lg border border-dashed border-border text-center text-sm text-muted-foreground"
        style={{ height }}
      >
        A linha aparece depois de 2 dias de coleta.
      </div>
    ) : null;
  }

  const gradientId = filled ? "spark-fill-hero" : undefined;

  return (
    <div className="w-full text-primary" style={{ height }} aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          {gradientId && (
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="currentColor" stopOpacity={0.28} />
                <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
              </linearGradient>
            </defs>
          )}
          <Area
            type="monotone"
            dataKey="value"
            stroke="currentColor"
            strokeWidth={filled ? 2.25 : 1.75}
            fill={gradientId ? `url(#${gradientId})` : "transparent"}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
