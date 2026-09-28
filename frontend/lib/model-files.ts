// Arquivos 3D que a tela Analisar aceita no lugar das imagens: o app tira as fotos sozinho
// (lib/render-model.ts, carregado só quando alguém escolhe um desses).

export const MODEL_EXTENSIONS = ["stl", "obj", "glb", "3mf", "fbx"] as const;
export const MODEL_ACCEPT = MODEL_EXTENSIONS.map((ext) => `.${ext}`).join(",");
export const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp";

export function modelExtension(file: File): string | null {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return (MODEL_EXTENSIONS as readonly string[]).includes(ext) ? ext : null;
}
