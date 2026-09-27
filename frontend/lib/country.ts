"use client";

import { useSearchParams } from "next/navigation";
import { useSyncExternalStore } from "react";

// País escolhido na tela inicial. Fica guardado no navegador e vale para o app todo;
// um ?country= na URL tem prioridade (links da nav e compartilhados).
const STORAGE_KEY = "radar3d.country";
const EVENT = "radar3d-country";
export const DEFAULT_COUNTRY = "BR";
const KNOWN_COUNTRIES = new Set(["BR", "US", "GB", "DE", "FR", "ES", "JP"]);

// Código fora da lista (URL digitada errada, valor velho guardado) é ignorado.
function valid(code: string | null | undefined): string | null {
  return code && KNOWN_COUNTRIES.has(code) ? code : null;
}

function readStored(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

// No servidor (e durante a hidratação) o armazenamento ainda não é conhecido.
function readServer(): undefined {
  return undefined;
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

export function saveCountry(code: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // navegador sem armazenamento (modo privado): segue só com o ?country= da URL
  }
  window.dispatchEvent(new Event(EVENT));
}

/**
 * País atual: ?country= da URL, senão o guardado, senão "BR" (códigos desconhecidos são ignorados).
 * Devolve `null` só no primeiro instante (antes de ler o navegador), para as telas não
 * pedirem dados do país errado; nesse caso, espere antes de buscar.
 */
export function useCountry(): string | null {
  const searchParams = useSearchParams();
  const stored = useSyncExternalStore<string | null | undefined>(subscribe, readStored, readServer);
  const fromUrl = valid(searchParams.get("country"));
  if (fromUrl) {
    return fromUrl;
  }
  if (stored === undefined) {
    return null;
  }
  return valid(stored) ?? DEFAULT_COUNTRY;
}

/** O país guardado (ou null), sem olhar a URL — para a tela inicial marcar a escolha. */
export function useStoredCountry(): string | null {
  return useSyncExternalStore<string | null>(subscribe, readStored, () => null);
}
