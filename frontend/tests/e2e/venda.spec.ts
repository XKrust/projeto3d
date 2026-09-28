import fs from "node:fs";
import path from "node:path";
import { test, expect, type Page } from "@playwright/test";

const fixture = (name: string) => JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", name), "utf-8"));
const analysis = fixture("analysis.json");
const analyses = fixture("analyses.json");
const metaFixture = fixture("meta.json");
const sale = fixture("sale.json");
const IMAGE = path.join(__dirname, "fixtures", "modelo.png");
const COUNTRIES = {
  max: 5,
  defaults: ["US", "DE", "GB", "BR"],
  countries: [
    { code: "US", name: "EUA" },
    { code: "DE", name: "Alemanha" },
    { code: "GB", name: "Reino Unido" },
    { code: "BR", name: "Brasil" },
    { code: "FR", name: "França" },
    { code: "JP", name: "Japão" },
  ],
};

async function setup(page: Page, opts: { saved?: unknown; response?: { status: number; body: unknown } }) {
  const posted: unknown[] = [];
  await page.route("**/api/radar/meta", (route) => route.fulfill({ json: metaFixture }));
  await page.route("**/api/analyses", (route) => route.fulfill({ json: analyses }));
  await page.route("**/api/analyses/3", (route) =>
    route.fulfill({ json: { ...analysis, id: 3, previous: null, sale: opts.saved ?? null } })
  );
  await page.route("**/api/analyses/*/images/**", (route) => route.fulfill({ path: IMAGE, contentType: "image/png" }));
  await page.route("**/ref*.png", (route) => route.fulfill({ path: IMAGE, contentType: "image/png" }));
  await page.route("**/api/analyses/3/sale/countries", (route) => route.fulfill({ json: COUNTRIES }));
  await page.route("**/api/analyses/3/sale", async (route) => {
    posted.push(route.request().postDataJSON());
    const response = opts.response ?? { status: 200, body: sale };
    await route.fulfill({ status: response.status, json: response.body });
  });
  await page.route("**/api/settings", (route) => route.fulfill({ json: {} }));
  await page.goto("/analisar");
  await page.getByRole("list", { name: "Análises anteriores" }).getByRole("button", { name: /5,8/ }).click();
  return posted;
}

test.describe("/analisar · venda", () => {
  test("prepara a venda: países, lojas, preço, chance, anúncio e checklist", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    const posted = await setup(page, {});
    const section = page.getByRole("region", { name: "Venda" });

    // padrões marcados; até 5 países
    await expect(section.getByRole("button", { name: "EUA" })).toHaveAttribute("aria-pressed", "true");
    await expect(section.getByRole("button", { name: "França" })).toHaveAttribute("aria-pressed", "false");
    await section.getByRole("button", { name: "Alemanha" }).click();
    await section.getByRole("button", { name: "Reino Unido" }).click();
    await section.getByRole("button", { name: "Preparar venda" }).click();
    expect(posted).toEqual([{ countries: ["US", "BR"] }]);

    await expect(section.getByRole("tab", { name: "Brasil" })).toHaveAttribute("aria-selected", "true");
    const panel = section.getByRole("tabpanel");
    await expect(panel).toContainText("Cults3D");
    await expect(panel).toContainText("US$ 5,99");
    await expect(panel).toContainText("faixa US$ 4,99–US$ 6,99");
    await expect(panel).toContainText("sobra US$ 4,79 (taxa 20%)");
    await expect(panel).toContainText("mediana de 23 anúncios de Frieren no Cults3D");
    await expect(panel).toContainText("Chance de venda (estimativa)");
    await expect(panel).toContainText("Média");
    await expect(panel).toContainText("64/100");
    await expect(panel).toContainText("sem dados suficientes para esta loja");
    await expect(panel).toContainText("o tema ainda não tem nota no Brasil");

    // câmbio: 5,99 × 5,43 = 32,53
    await expect(panel).toContainText("≈ R$ 32,53");
    await expect(panel).toContainText("lançamento ≈ R$ 27,10");
    await expect(panel).toContainText("câmbio de 26/09, estimativa");

    await section.getByRole("tab", { name: "EUA" }).click();
    await expect(section.getByRole("tabpanel")).not.toContainText("≈ R$");
    await expect(section.getByRole("tabpanel")).toContainText("taxa: —");
    await expect(section.getByRole("tabpanel")).toContainText("Alta");

    await expect(section).toContainText("≈ 21 vendas");
    await section.getByLabel("Valor da sua hora (US$)").fill("20");
    await expect(section).toContainText("≈ 42 vendas");

    const card = section.getByRole("article", { name: "Anúncio Cults3D em Português" });
    await expect(card).toContainText("Busto Frieren STL (fan art)");
    await expect(card).toContainText("cortado para caber no limite da loja");
    await expect(card).toContainText("revise antes de publicar");
    await card.getByRole("button", { name: "Copiar título" }).click();
    await expect(card.getByRole("button", { name: "Copiado" })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("Busto Frieren STL (fan art)");

    await expect(section).toContainText("Comunidades onde o tema está em alta no Reddit:");
    await expect(section.getByRole("link", { name: "r/anime" })).toHaveAttribute("href", "https://www.reddit.com/r/anime/");
    await expect(section).toContainText("4 posts do tema em alta nos últimos 30 dias");
    await expect(section).toContainText("proíbem autopromoção");
    await section.getByRole("button", { name: "Copiar hashtags" }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("#frieren #animebust #sousounofrieren");
    await expect(section.getByLabel(/^Divulgue em r\/anime e r\/3Dprinting/)).toBeVisible();

    const step = section.getByLabel("Publique primeiro no Cults3D (melhor encaixe no Brasil).");
    await step.check();
    await expect(step).toBeChecked();
    await expect(section.getByRole("button", { name: "Gerar de novo" })).toBeVisible();
  });

  test("sem chave do Gemini: lojas e preço saem, o anúncio explica e leva para Configurações", async ({ page }) => {
    const note = "Configure a chave do Gemini em Configurações para gerar o anúncio.";
    const promotion = {
      ...sale.promotion,
      communities: [{ name: "r/3Dprinting", url: "https://www.reddit.com/r/3Dprinting/", why: "comunidade de impressão 3D", source: "tipo" }],
    };
    await setup(page, { response: { status: 200, body: { ...sale, listing: null, listing_note: note, promotion } } });
    const section = page.getByRole("region", { name: "Venda" });
    await section.getByRole("button", { name: "Preparar venda" }).click();
    await expect(section.getByRole("tabpanel")).toContainText("US$ 5,99");
    await expect(section.getByRole("note")).toContainText(note);
    await expect(section.getByRole("link", { name: "Abrir Configurações" })).toHaveAttribute("href", "/config");
    await expect(section).toContainText("O app ainda não viu o tema no Reddit. Comunidades do tipo de modelo:");
    await expect(section).toContainText("comunidade de impressão 3D");
  });

  test("análise com venda salva abre pronta", async ({ page }) => {
    await setup(page, { saved: sale });
    const section = page.getByRole("region", { name: "Venda" });
    await expect(section.getByRole("button", { name: "Gerar de novo" })).toBeVisible();
    await expect(section.getByRole("tabpanel")).toContainText("Cults3D");
    await expect(section.getByRole("button", { name: "Brasil" })).toHaveAttribute("aria-pressed", "true");
    await expect(section.getByRole("button", { name: "Alemanha" })).toHaveAttribute("aria-pressed", "false");
  });

  test("erro de validação aparece na seção", async ({ page }) => {
    await setup(page, { response: { status: 422, body: { detail: "Escolha de 1 a 5 países" } } });
    const section = page.getByRole("region", { name: "Venda" });
    await section.getByRole("button", { name: "Preparar venda" }).click();
    await expect(section.getByRole("alert")).toHaveText("Escolha de 1 a 5 países");
  });
});
