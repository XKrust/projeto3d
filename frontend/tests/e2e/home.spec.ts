import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const countriesFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/countries.json"), "utf-8")
);
const metaFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/meta.json"), "utf-8")
);

test.describe("tela inicial (países)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/countries", (route) => route.fulfill({ json: countriesFixture }));
    await page.route("**/api/radar/meta", (route) => route.fulfill({ json: metaFixture }));
    await page.route("**/api/radar?*", (route) => route.fulfill({ json: [] }));
  });

  test("cada país mostra os temas em alta e as lojas fortes, sem porcentagem", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1, name: "Onde você vai vender?" })).toBeVisible();
    const brasil = page.getByRole("button", { name: /^Brasil/ });
    await expect(brasil).toContainText("Sousou no Frieren · Minecraft · Articulated Dragon");
    await expect(brasil).toContainText("Cults3D · MyMiniFactory · Fab");
    await expect(page.getByRole("button", { name: /^Japão/ })).toContainText("BOOTH");
    await expect(page.getByRole("button", { name: /^Alemanha/ })).toContainText("Ainda sem temas");
    await expect(page.getByRole("link", { name: "Reino Unido: inativo, ative em Configurações" })).toBeVisible();
    await expect(page.getByText("%")).toHaveCount(0);
  });

  test("escolher Japao leva ao radar com country=JP e lembra a escolha", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /^Japão/ }).click();

    await expect(page).toHaveURL(/\/radar\?country=JP/);

    // Voltando ao radar sem ?country=, o país guardado continua valendo.
    const radarRequest = page.waitForRequest((req) => req.url().includes("/api/radar?"));
    await page.goto("/radar");
    expect((await radarRequest).url()).toContain("country=JP");
  });

  test("nav mostra o pais escolhido", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /^Japão/ }).click();
    await expect(page).toHaveURL(/country=JP/);

    await expect(page.getByRole("link", { name: "País: Japão. Trocar país" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Sazonal" })).toHaveAttribute("href", "/sazonal?country=JP");
  });
});
