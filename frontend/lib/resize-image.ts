// Reduz a imagem no navegador antes de enviar: o envio passa pelo proxy do Next (limite de
// corpo) e imagem menor gasta menos cota do Gemini. Lado maior ≤ 1600 px. PNG continua PNG
// (render com fundo transparente não pode virar fundo preto); o resto vira JPEG 0,85.
// Imagem que já cabe e não é grande em bytes vai como está.

const SMALL_BYTES = 1_500_000;

export async function resizeImage(file: File, maxSide = 1600): Promise<Blob> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file; // o backend recusa com a mensagem de formato
  }
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size <= SMALL_BYTES) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const type = file.type === "image/png" ? "image/png" : "image/jpeg";
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, 0.85));
  return blob ?? file;
}
