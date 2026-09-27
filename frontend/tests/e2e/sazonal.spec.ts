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
    await expect(page.getByText("caveiras").first()).toBeVisible();
  });

  test("evento atrasado aparece com o texto atrasado", async ({ page }) => {
    await page.goto("/sazonal");

    const row = page.getByRole("listitem").filter({ hasText: "Dia das Crianças" });
    await expect(row).toContainText("Atrasado");
    await expect(row).toContainText("Comece até 14/09");
  });

  test("usa o país da URL", async ({ page }) => {
    const request = page.waitForRequest((req) => req.url().includes("/api/seasonal?"));

    await page.goto("/sazonal?country=JP");

    expect((await request).url()).toContain("country=JP");
  });
});
