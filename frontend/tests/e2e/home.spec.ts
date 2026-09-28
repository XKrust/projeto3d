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

  test("países em ranking de possibilidade de venda, com o movimento da semana", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1, name: "Onde vender agora" })).toBeVisible();
    const cards = page.getByRole("list", { name: "Ranking de países" }).getByRole("listitem");
    await expect(cards.nth(0)).toContainText("1º");
    await expect(cards.nth(0)).toContainText("EUA");
    await expect(cards.nth(0)).toContainText("1º há 12 dias");
    await expect(cards.nth(1)).toContainText("Rússia");
    await expect(cards.nth(1)).toContainText("↑ 2 na semana");
    await expect(cards.nth(1)).toContainText("Pagamento difícil (sanções)");
    await expect(cards.nth(2)).toContainText("↓ 1 na semana");
    await expect(cards.nth(2)).toContainText("Sousou no Frieren · Minecraft · Articulated Dragon");
    await expect(cards.nth(2)).toContainText("Cults3D · Fab · MyMiniFactory");
    await expect(cards.nth(0)).toContainText("88");
    await expect(cards.nth(0)).toContainText("(estimativa)");
    await expect(page.getByRole("button", { name: /^Alemanha/ })).toContainText("aparecem depois da primeira coleta");
    await expect(page.getByRole("button", { name: /^Alemanha/ })).toContainText("Procura: ainda medindo");
    await expect(page.getByRole("link", { name: "Reino Unido: inativo, ative em Configurações" })).toBeVisible();
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
