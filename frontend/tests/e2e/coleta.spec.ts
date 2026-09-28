import { test, expect } from "@playwright/test";

// Faixa de progresso da coleta (aparece em todas as telas) e atualização sozinha no fim.
test("mostra o progresso da coleta e recarrega as telas quando termina", async ({ page }) => {
  let calls = 0;
  const statuses = [
    { running: true, phase: "coleta", current: "Sketchfab", done: 3, total: 15, quiet: false },
    { running: true, phase: "notas", current: null, done: 15, total: 15, quiet: false },
    { running: true, phase: "concorrencia", current: null, done: 15, total: 15, quiet: false },
    { running: false, phase: null, current: null, done: 15, total: 15, quiet: false, finished_at: "2026-09-28T10:00:00" },
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
  await expect(page.getByText(/Radar atualizado\. Agora medindo a concorrência/)).toBeVisible({ timeout: 10000 });
  // o radar recarrega já quando as notas ficam prontas, sem esperar a concorrência
  await expect.poll(() => radarLoads, { timeout: 10000 }).toBeGreaterThan(1);
  await expect(page.getByText(/medindo a concorrência/)).toBeHidden({ timeout: 10000 });
});


test("ciclo silencioso (nenhuma fonte no horário) não mostra a faixa", async ({ page }) => {
  await page.route("**/api/collect/status", (route) =>
    route.fulfill({ json: { running: true, phase: "notas", current: null, done: 0, total: 0, quiet: true } })
  );
  await page.route("**/api/radar/meta", (route) =>
    route.fulfill({ json: { countries: ["BR"], country_groups: {}, categories: [], markets: [], platforms: [], last_updated: null } })
  );
  await page.route("**/api/radar?*", (route) => route.fulfill({ json: [] }));
  await page.goto("/radar?country=BR");
  await expect(page.getByText(/A primeira coleta começa sozinha/)).toBeVisible();
  await expect(page.getByText("Calculando as notas dos temas…")).toBeHidden();
});
