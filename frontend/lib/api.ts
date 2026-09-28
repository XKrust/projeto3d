// Cliente de API do backend (FastAPI). Simples e sem dependência de framework
// (fetch puro) para que as Tarefas 16-17 possam usá-lo junto com SWR.

export class BackendOfflineError extends Error {
  constructor() {
    super("Não consegui falar com o backend.");
    this.name = "BackendOfflineError";
  }
}

const OFFLINE_STATUS = new Set([502, 503, 504]);

async function parseErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // corpo não é JSON ou está vazio: ignora e usa mensagem genérica
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new BackendOfflineError();
  }

  if (response.ok) {
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  if (OFFLINE_STATUS.has(response.status)) {
    throw new BackendOfflineError();
  }

  if (response.status === 422) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail ?? "Erro inesperado (422)");
  }

  throw new Error(`Erro inesperado (${response.status})`);
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function apiPost<T>(path: string): Promise<T> {
  return request<T>(path, { method: "POST" });
}

/** Erro de API com o status HTTP (ex.: 409 = sem chave do Gemini). */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** POST multipart (envio de arquivos). Qualquer 4xx com `detail` vira `ApiError(detail)`. */
export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { method: "POST", body: form });
  } catch {
    throw new BackendOfflineError();
  }
  if (response.ok) {
    return (await response.json()) as T;
  }
  if (OFFLINE_STATUS.has(response.status)) {
    throw new BackendOfflineError();
  }
  const detail = await parseErrorDetail(response);
  throw new ApiError(detail ?? `Erro inesperado (${response.status})`, response.status);
}
