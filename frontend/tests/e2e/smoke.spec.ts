import { test, expect } from "@playwright/test";

/**
 * Smoke test de ponta a ponta: roda contra o backend e o frontend REAIS
 * (não usa `page.route` para mockar a API), então precisa dos dois
 * servidores rodando de verdade — por exemplo via `iniciar.bat`.
 *
 * Fica fora da suíte padrão (`npx playwright test`), que continua
 * funcionando sem backend: só roda com a variável de ambiente
 * `RADAR_SMOKE=1` definida, como em:
 *
 *   RADAR_SMOKE=1 npx playwright test tests/e2e/smoke.spec.ts
 *
 * Ver docs/como-rodar.md.
 */
test.describe("smoke (servidores reais)", () => {
  test.skip(
    process.env.RADAR_SMOKE !== "1",
    "Defina RADAR_SMOKE=1 para rodar este teste contra o backend e o frontend reais."
  );

  const rotas = ["/", "/radar", "/config", "/sazonal", "/hype", "/analisar"];

  for (const rota of rotas) {
    test(`${rota} carrega sem erro no console`, async ({ page }) => {
      const erros: string[] = [];
      page.on("pageerror", (err) => erros.push(String(err)));
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          erros.push(msg.text());
        }
      });

      await page.goto(rota);
      await page.waitForLoadState("networkidle");

      expect(erros, `erros de console em ${rota}:\n${erros.join("\n")}`).toEqual(
        []
      );
    });
  }

  test("/config lista as 15 fontes", async ({ page }) => {
    await page.goto("/config");
    await page.waitForLoadState("networkidle");

    for (const fonte of [
      "Google Trends",
      "YouTube",
      "Reddit",
      "Sketchfab",
      "Cults3D",
      "Printables",
      "BOOTH",
      "ArtStation",
      "Etsy",
      "Thingiverse",
      "MyMiniFactory",
      "CGTrader",
      "AniList",
      "TMDB",
      "IGDB (jogos)",
    ]) {
      await expect(page.getByText(fonte).first()).toBeVisible();
    }
  });
});
