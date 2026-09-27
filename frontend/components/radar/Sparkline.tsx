"use client";

import { Line, LineChart, ResponsiveContainer } from "recharts";
import type { SparklinePoint } from "@/lib/radar-types";

const SPARKLINE_HEIGHT = 40;

export function Sparkline({ data }: { data: SparklinePoint[] }) {
  if (data.length < 2) {
    return null;
  }

  return (
    <div
      className="text-primary"
      style={{ width: "100%", height: SPARKLINE_HEIGHT }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="value"
            stroke="currentColor"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
