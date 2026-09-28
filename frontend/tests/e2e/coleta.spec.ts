import { test, expect } from "@playwright/test";

// Faixa de progresso da coleta (aparece em todas as telas) e atualização sozinha no fim.
test("mostra o progresso da coleta e recarrega as telas quando termina", async ({ page }) => {
  let calls = 0;
  const statuses = [
    { running: true, phase: "coleta", current: "Sketchfab", done: 3, total: 15 },
    { running: true, phase: "notas", current: null, done: 15, total: 15 },
    { running: false, phase: null, current: null, done: 15, total: 15, finished_at: "2026-09-28T10:00:00" },
  ];
  await page.route("**/api/collect/status", (route) => {
    const body = statuses[Math.min(calls, statuses.length - 1)];
    calls += 1;
    return route.fulfill({ json: body });
  });
  let radarLoads = 0;
  await page.route("**/api/radar/meta", (route) =>
    route.fulfill({ json: { countries: ["BR"], country_groups: {}, categories: [], markets: [], platforms: [], last_updated: null } })
  );
  await page.route("**/api/radar?*", (route) => {
    radarLoads += 1;
    return route.fulfill({ json: [] });
  });
  await page.goto("/radar?country=BR");

  const banner = page.getByRole("status").filter({ hasText: "Coletando dados" });
  await expect(banner).toContainText("Coletando dados: 4 de 15 fontes (Sketchfab)");
  await expect(page.getByText("Calculando as notas dos temas…")).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("Calculando as notas dos temas…")).toBeHidden({ timeout: 10000 });
  await expect.poll(() => radarLoads, { timeout: 10000 }).toBeGreaterThan(1);
});
