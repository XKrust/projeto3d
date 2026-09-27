import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";

function loadFixture(name: string) {
  return JSON.parse(
    fs.readFileSync(path.join(__dirname, "fixtures", name), "utf-8")
  );
}

const settingsFixture = loadFixture("config-settings.json");
const sourcesFixture = loadFixture("config-sources.json");
const platformsFixture = loadFixture("config-platforms.json");

test.describe("/config", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/settings", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ json: settingsFixture });
      }
      return route.fulfill({ json: settingsFixture });
    });
    await page.route("**/api/sources", (route) =>
      route.fulfill({ json: sourcesFixture })
    );
    await page.route("**/api/platforms", (route) =>
      route.fulfill({ json: platformsFixture })
    );
  });

  test("fonte sem chave mostra 🟡 e “sem chave”", async ({ page }) => {
    await page.goto("/config");

    const row = page.getByRole("row", { name: /YouTube/ });
    await expect(row).toContainText("🟡");
    await expect(row).toContainText("sem chave");
  });

  test("fonte com erro mostra 🔴 e o texto do erro", async ({ page }) => {
    await page.goto("/config");

    const row = page.getByRole("row", { name: /Reddit/ });
    await expect(row).toContainText("🔴");
    await expect(row).toContainText("erro");
    await expect(row).toContainText("Chave inválida ou sem permissão (401)");
  });

  test("salvar com pesos inválidos mostra a mensagem de erro do backend", async ({
    page,
  }) => {
    await page.route("**/api/settings", (route) => {
      if (route.request().method() === "PUT") {
        return route.fulfill({
          status: 422,
          json: { detail: "Os pesos precisam somar 1,0" },
        });
      }
      return route.fulfill({ json: settingsFixture });
    });

    await page.goto("/config");
    await page.getByText("Avançado (pesos do score)").click();
    await page.getByLabel("Demanda").fill("0.9");
    await page.getByRole("button", { name: "Salvar", exact: true }).click();

    await expect(page.getByText("Os pesos precisam somar 1,0")).toBeVisible();
  });

  test("chave mascarada aparece e o PUT envia o valor mascarado sem alterar", async ({
    page,
  }) => {
    const captured: { body: { api_keys?: Record<string, string> } | null } = {
      body: null,
    };
    await page.route("**/api/settings", (route) => {
      if (route.request().method() === "PUT") {
        captured.body = route.request().postDataJSON();
        return route.fulfill({ json: settingsFixture });
      }
      return route.fulfill({ json: settingsFixture });
    });

    await page.goto("/config");

    const youtubeInput = page.getByLabel("Chave da API do YouTube");
    await expect(youtubeInput).toHaveValue("••••1234");

    await page.getByRole("button", { name: "Salvar", exact: true }).click();

    await expect(page.getByText("Salvo!")).toBeVisible();
    expect(captured.body?.api_keys?.youtube).toBe("••••1234");
  });

  test("plataforma com taxa não confirmada mostra —", async ({ page }) => {
    await page.goto("/config");

    // Cults3D tem fee_pct null na fixture (taxa ainda não confirmada).
    const feeInput = page.getByLabel("Taxa de Cults3D");
    await expect(feeInput).toHaveValue("");
    await expect(feeInput).toHaveAttribute("placeholder", "—");
  });

  test("loja fechada sai da tabela e aparece como só sinal de tendência", async ({ page }) => {
    await page.goto("/config");

    await expect(page.getByLabel("Força de Cults3D em Brasil")).toBeVisible();
    await expect(page.getByLabel("Força de Sketchfab em Brasil")).toHaveCount(0);
    await expect(page.getByText(/Sketchfab não vende(m)? mais/)).toBeVisible();
  });
});
