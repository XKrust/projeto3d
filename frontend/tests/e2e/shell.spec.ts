import { test, expect } from "@playwright/test";

test.describe("esqueleto do frontend", () => {
  test("/analisar mostra aviso de backend desligado quando a API falha", async ({ page }) => {
    await page.route("**/api/**", (route) => route.abort());
    await page.goto("/analisar");
    await expect(
      page.getByText("Não consegui falar com o backend. Feche e abra o Radar 3D de novo pelo menu Iniciar (ou pelo atalho da área de trabalho).")
    ).toBeVisible();
  });

  test("/radar mostra aviso de backend desligado quando a API falha", async ({
    page,
  }) => {
    await page.route("**/api/**", (route) => route.abort());
    await page.goto("/radar");
    await expect(
      page.getByText(
        "Não consegui falar com o backend. Feche e abra o Radar 3D de novo pelo menu Iniciar (ou pelo atalho da área de trabalho)."
      )
    ).toBeVisible();
  });

  test("/config mostra aviso de backend desligado quando a API falha", async ({
    page,
  }) => {
    await page.route("**/api/**", (route) => route.abort());
    await page.goto("/config");
    await expect(
      page.getByText(
        "Não consegui falar com o backend. Feche e abra o Radar 3D de novo pelo menu Iniciar (ou pelo atalho da área de trabalho)."
      )
    ).toBeVisible();
  });
});
