import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

const metaFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/meta.json"), "utf-8")
);
const radarFixture = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/radar.json"), "utf-8")
);

test.describe("/radar", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/radar/meta", (route) =>
      route.fulfill({ json: metaFixture })
    );
  });

  test("renderiza os cards da fixture com nome, estimativa, melhor plataforma e pico", async ({
    page,
  }) => {
    await page.route("**/api/radar?*", (route) =>
      route.fulfill({ json: radarFixture })
    );

    await page.goto("/radar");

    await expect(page.getByText("Goku Super Saiyajin")).toBeVisible();
    await expect(page.getByText(/estimativa/).first()).toBeVisible();
    await expect(page.getByText("Melhor em: Cults3D")).toBeVisible();
    await expect(page.getByText("Pico em 10 dias")).toBeVisible();
    await expect(page.getByText("Pico agora")).toBeVisible();
    await expect(page.getByText("Preço mediano: US$ 4,50")).toBeVisible();
    await expect(page.getByText("Preço mediano: —")).toBeVisible();
  });

  test("o país da URL vai para a consulta do radar", async ({ page }) => {
    await page.route("**/api/radar?*", (route) =>
      route.fulfill({ json: radarFixture })
    );
    const radarRequest = page.waitForRequest((req) => req.url().includes("/api/radar?"));

    await page.goto("/radar?country=JP");

    expect((await radarRequest).url()).toContain("country=JP");
    await expect(page.getByText("Goku Super Saiyajin")).toBeVisible();
  });

  test("lista vazia mostra o texto de orientação", async ({ page }) => {
    await page.route("**/api/radar?*", (route) => route.fulfill({ json: [] }));

    await page.goto("/radar");

    await expect(
      page.getByText(
        "Nenhum tópico ainda. Clique em “Coletar agora” ou configure suas chaves em Configurações."
      )
    ).toBeVisible();
  });

  test('clicar em "Coletar agora" mostra mensagem de coleta em andamento', async ({
    page,
  }) => {
    await page.route("**/api/radar?*", (route) => route.fulfill({ json: [] }));
    await page.route("**/api/collect", (route) =>
      route.fulfill({
        json: {
          started: false,
          message: "Já existe uma coleta em andamento.",
        },
      })
    );

    await page.goto("/radar");
    await page.getByRole("button", { name: "Coletar agora" }).click();

    await expect(
      page.getByText("Já existe uma coleta em andamento.")
    ).toBeVisible();
  });
});
