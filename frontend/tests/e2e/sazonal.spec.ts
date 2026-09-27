import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const metaFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/meta.json"), "utf-8")
);
const seasonalFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/seasonal.json"), "utf-8")
);

test.describe("/sazonal", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/radar/meta", (route) => route.fulfill({ json: metaFixture }));
    await page.route("**/api/seasonal?*", (route) =>
      route.fulfill({ json: seasonalFixture })
    );
  });

  test("mostra o próximo evento e o comece a modelar até", async ({ page }) => {
    await page.goto("/sazonal");

    // O destaque é o próximo evento que ainda dá tempo (o atrasado não conta).
    await expect(
      page.getByRole("heading", { level: 1, name: "Halloween" })
    ).toBeVisible();
    await expect(page.getByText("Comece a modelar até 03/10")).toBeVisible();
    await expect(page.getByText("Evento em 31/10")).toBeVisible();
  });

  test("destaque mostra o top 5 do evento", async ({ page }) => {
    await page.goto("/sazonal");

    const top = page.getByRole("list", { name: "Top 5 modelos para Halloween" });
    await expect(top.getByRole("listitem")).toHaveCount(5);
    await expect(top.getByRole("listitem").first()).toContainText("Caveira");
    await expect(top.getByRole("listitem").first()).toContainText("Alta");
    await expect(top.getByRole("listitem").first()).toContainText("(estimativa)");
    await expect(top.getByRole("listitem").first()).toContainText("Cults3D 900 · BOOTH 12");
    await expect(top.getByRole("listitem").last()).toContainText("sem dados ainda");
  });

  test("linha do calendario mostra top 5", async ({ page }) => {
    await page.goto("/sazonal");

    const natal = page.getByRole("list", { name: "Top 5 de Natal" });
    await expect(natal.getByRole("listitem")).toHaveCount(5);
    await expect(natal).toContainText("Enfeite de árvore");
    await expect(natal).toContainText("sem dados ainda");
  });

  test("evento atrasado aparece com o texto atrasado", async ({ page }) => {
    await page.goto("/sazonal");

    const row = page.getByRole("listitem").filter({ hasText: "Dia das Crianças" });
    await expect(row).toContainText("Atrasado");
    await expect(row).toContainText("Prazo ideal já passou");
    await expect(row).not.toContainText("Comece até");
  });

  test("país inválido na URL cai no país padrão", async ({ page }) => {
    const request = page.waitForRequest((req) => req.url().includes("/api/seasonal?"));

    await page.goto("/sazonal?country=XX");

    expect((await request).url()).toContain("country=BR");
  });

  test("usa o país da URL", async ({ page }) => {
    const request = page.waitForRequest((req) => req.url().includes("/api/seasonal?"));

    await page.goto("/sazonal?country=JP");

    expect((await request).url()).toContain("country=JP");
  });
});
