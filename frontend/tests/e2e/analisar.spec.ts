import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { test, expect, type Page } from "@playwright/test";

const fixture = (name: string) => JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", name), "utf-8"));
const analysis = fixture("analysis.json");
const analyses = fixture("analyses.json");
const metaFixture = fixture("meta.json");
const IMAGE = path.join(__dirname, "fixtures", "modelo.png");
const STL = path.join(__dirname, "fixtures", "peca.stl");

// PNG RGBA 2000×4 totalmente transparente (render com fundo transparente, maior que 1600 px).
function transparentPng(width = 2000, height = 4): Buffer {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const byte of buf) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type), data]);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([len, body, sum]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 6, 0, 0, 0], 8);
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(width * 4)]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function setup(page: Page, analyze: { status: number; body: unknown; delayMs?: number }) {
  await page.route("**/api/radar/meta", (route) => route.fulfill({ json: metaFixture }));
  await page.route("**/api/analyses", (route) => route.fulfill({ json: analyses }));
  await page.route("**/api/analyses/3", (route) => route.fulfill({ json: { ...analysis, id: 3, previous: null } }));
  await page.route("**/api/analyses/*/images/**", (route) => route.fulfill({ path: IMAGE, contentType: "image/png" }));
  await page.route("**/ref*.png", (route) => route.fulfill({ path: IMAGE, contentType: "image/png" }));
  await page.route("**/api/analyses/*/sale/countries", (route) =>
    route.fulfill({ json: { max: 5, defaults: ["BR"], countries: [{ code: "BR", name: "Brasil" }] } })
  );
  await page.route("**/api/analyze", async (route) => {
    if (analyze.delayMs) await new Promise((resolve) => setTimeout(resolve, analyze.delayMs));
    await route.fulfill({ status: analyze.status, json: analyze.body });
  });
}

test.describe("/analisar", () => {
  test("envia, mostra progresso e o resultado honesto", async ({ page }) => {
    await setup(page, { status: 201, body: analysis, delayMs: 800 });
    await page.goto("/analisar");

    const button = page.getByRole("button", { name: "Analisar", exact: true });
    await expect(button).toBeDisabled();
    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles([IMAGE, IMAGE]);
    await page.getByLabel("Fan-art").check();
    await expect(page.getByText(/direitos autorais/)).toBeVisible();
    await button.click();

    await expect(page.getByText("Identificando o modelo…")).toBeVisible();
    const result = page.getByRole("region", { name: "Resultado da análise" });
    await expect(result.getByRole("heading", { name: "Busto da Frieren" })).toBeVisible();
    await expect(result).toContainText("6,9");
    await expect(result).toContainText("avaliação por IA");
    await expect(result).toContainText("antes: 5,8 → agora: 6,9");
    await expect(result).toContainText("Corrigir os dedos da mão esquerda");
    await expect(result).toContainText("não avaliável");
    await expect(result).toContainText("Como corrigir");
    await expect(result).toContainText("Vale conferir");
    await expect(result).toContainText("a IA exagerou aqui");
    await expect(result.getByRole("link", { name: /Frieren Bust/ })).toHaveAttribute(
      "href",
      "https://sketchfab.com/3d-models/frieren-aaaa"
    );
    await expect(result).toContainText("mechas em 3 níveis");
  });

  test("mais de 4 imagens não deixa analisar", async ({ page }) => {
    await setup(page, { status: 201, body: analysis });
    await page.goto("/analisar");

    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles([IMAGE, IMAGE, IMAGE, IMAGE, IMAGE]);

    await expect(page.getByRole("button", { name: "Analisar", exact: true })).toBeDisabled();
    await expect(page.getByText("Envie de 1 a 4 imagens")).toBeVisible();
  });

  test("sem chave do Gemini explica e leva para Configurações", async ({ page }) => {
    await setup(page, {
      status: 409,
      body: { detail: "Configure a chave do Gemini em Configurações para analisar modelos" },
    });
    await page.goto("/analisar");
    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles([IMAGE]);
    await page.getByRole("button", { name: "Analisar", exact: true }).click();

    await expect(page.getByText("Configure a chave do Gemini em Configurações para analisar modelos")).toBeVisible();
    await expect(page.getByRole("link", { name: "Abrir Configurações" })).toHaveAttribute("href", "/config");
  });

  test("cota esgotada mostra a mensagem", async ({ page }) => {
    await setup(page, {
      status: 429,
      body: { detail: "A cota grátis da IA acabou por hoje. Tente de novo mais tarde." },
    });
    await page.goto("/analisar");
    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles([IMAGE]);
    await page.getByRole("button", { name: "Analisar", exact: true }).click();

    await expect(page.getByText("A cota grátis da IA acabou por hoje. Tente de novo mais tarde.")).toBeVisible();
  });

  test("histórico abre uma análise antiga", async ({ page }) => {
    await setup(page, { status: 201, body: analysis });
    await page.goto("/analisar");

    const history = page.getByRole("list", { name: "Análises anteriores" });
    await expect(history.getByRole("listitem")).toHaveCount(2);
    await history.getByRole("button", { name: /5,8/ }).click();

    await expect(page.getByRole("region", { name: "Resultado da análise" })).toContainText("Busto da Frieren");
  });

  test("render com fundo transparente continua PNG ao ser reduzido", async ({ page }) => {
    await setup(page, { status: 201, body: analysis });
    let body = "";
    await page.route("**/api/analyze", async (route) => {
      body = route.request().postDataBuffer()?.toString("latin1") ?? "";
      await route.fulfill({ status: 201, json: analysis });
    });
    await page.goto("/analisar");

    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles({
      name: "render.png",
      mimeType: "image/png",
      buffer: transparentPng(),
    });
    await page.getByRole("button", { name: "Analisar", exact: true }).click();
    await expect(page.getByRole("region", { name: "Resultado da análise" })).toBeVisible();

    expect(body).toContain("Content-Type: image/png");
    expect(body).not.toContain("Content-Type: image/jpeg");
  });

  test("arquivo 3D vira 4 fotos e vai para a análise", async ({ page }) => {
    await setup(page, { status: 201, body: analysis });
    let body = "";
    await page.route("**/api/analyze", async (route) => {
      body = route.request().postDataBuffer()?.toString("latin1") ?? "";
      await route.fulfill({ status: 201, json: analysis });
    });
    await page.goto("/analisar");

    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles(STL);

    const chosen = page.getByRole("list", { name: "Imagens escolhidas" });
    await expect(chosen.getByRole("listitem")).toHaveCount(4, { timeout: 30_000 });
    await expect(page.getByText(/Fotos tiradas de peca\.stl: capa em 3\/4, frente, lado e costas/)).toBeVisible();
    await expect(chosen.getByRole("listitem").first()).toContainText("Capa");
    // Foto de verdade (1200 px, não vazia): a peça clara aparece sobre o fundo escuro.
    const stats = await chosen.getByRole("img").first().evaluate(async (img: HTMLImageElement) => {
      await img.decode();
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(img, 0, 0);
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let bright = 0;
      for (let i = 0; i < data.length; i += 4) if (data[i] > 120) bright++;
      return { width: img.naturalWidth, bright: bright / (data.length / 4) };
    });
    expect(stats.width).toBe(1200);
    expect(stats.bright).toBeGreaterThan(0.05);

    await page.getByRole("button", { name: "Analisar", exact: true }).click();
    await expect(page.getByRole("region", { name: "Resultado da análise" })).toBeVisible();
    expect(body).toContain('filename="image-4.png"');
    expect(body).not.toContain('filename="image-5');
  });

  test("arquivo que não dá para ler explica o que enviar", async ({ page }) => {
    await setup(page, { status: 201, body: analysis });
    await page.goto("/analisar");

    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles({
      name: "pack.zip",
      mimeType: "application/zip",
      buffer: Buffer.from("PK"),
    });
    await expect(page.getByText("pack.zip é um arquivo compactado: extraia e envie o STL, OBJ ou GLB de dentro dele.")).toBeVisible();

    await page.getByLabel("Imagens do modelo (1 a 4)").setInputFiles({
      name: "quebrado.stl",
      mimeType: "model/stl",
      buffer: Buffer.from("isto não é um STL"),
    });
    await expect(
      page.getByText("Não consegui abrir esse arquivo 3D. Exporte em STL, OBJ ou GLB, ou envie prints do modelo."),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Analisar", exact: true })).toBeDisabled();
  });
});
