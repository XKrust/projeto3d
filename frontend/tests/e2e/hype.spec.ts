import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const metaFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/meta.json"), "utf-8")
);
const hypeFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/hype.json"), "utf-8")
);

test.describe("/hype", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/radar/meta", (route) => route.fulfill({ json: metaFixture }));
  });

  test("mostra o topo com dias para a estreia", async ({ page }) => {
    await page.route("**/api/hype?*", (route) => route.fulfill({ json: hypeFixture }));
    await page.goto("/hype");

    // O topo é o lançamento de maior oportunidade (o filme, 78,5).
    await expect(
      page.getByRole("heading", { level: 1, name: "Vingadores: Guerras Secretas" })
    ).toBeVisible();
    await expect(page.getByText("dias para a estreia")).toBeVisible();
    await expect(page.getByText("Estreia em 82 dias · concorrência ainda não medida")).toBeVisible();
  });

  test("personagens aparecem com chance (estimativa)", async ({ page }) => {
    await page.route("**/api/hype?*", (route) => route.fulfill({ json: hypeFixture }));
    await page.goto("/hype");

    const row = page.getByRole("listitem").filter({ hasText: "The Apothecary Diaries Season 3" }).first();
    await expect(row).toContainText("Maomao");
    await expect(row).toContainText("Cults3D 34 · BOOTH 7");
    const maomao = page.getByRole("listitem").filter({ hasText: "Maomao" }).last();
    await expect(maomao).toContainText("Média");
    await expect(maomao).toContainText("(estimativa)");
  });

  test("lançamento sem data mostra Data a confirmar", async ({ page }) => {
    await page.route("**/api/hype?*", (route) => route.fulfill({ json: hypeFixture }));
    await page.goto("/hype");

    const row = page.getByRole("listitem").filter({ hasText: "Jogo Sem Data" }).first();
    await expect(row).toContainText("Data a confirmar");
  });

  test("trocar o tipo muda a query", async ({ page }) => {
    await page.route("**/api/hype?*", (route) => route.fulfill({ json: hypeFixture }));
    await page.goto("/hype");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await page.getByLabel("Tipo").click();
    await page.getByRole("option", { name: "Jogos" }).click();

    await expect(page).toHaveURL(/kind=jogo/);
  });

  test("lista vazia mostra orientação", async ({ page }) => {
    await page.route("**/api/hype?*", (route) =>
      route.fulfill({ json: { country: "BR", releases: [] } })
    );
    await page.goto("/hype");

    await expect(page.getByText("Nenhuma estreia ainda.")).toBeVisible();
    await expect(page.getByText(/cole as chaves do TMDB e do IGDB/)).toBeVisible();
  });
});
