import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KEY_GUIDES } from "@/lib/keyGuides";

type ApiKeyField = { key: string; label: string };
type ApiKeyGroup = { service: string; fields: ApiKeyField[] };

// Agrupa os campos de `settings.api_keys` (backend/app/settings_store.py) por
// serviço, para casar cada grupo com seu guia em `keyGuides.ts`.
const API_KEY_GROUPS: ApiKeyGroup[] = [
  { service: "youtube", fields: [{ key: "youtube", label: "Chave da API do YouTube" }] },
  {
    service: "reddit",
    fields: [
      { key: "reddit_client_id", label: "Client ID do Reddit" },
      { key: "reddit_client_secret", label: "Client Secret do Reddit" },
    ],
  },
  {
    service: "sketchfab",
    fields: [{ key: "sketchfab", label: "Token da API do Sketchfab" }],
  },
  {
    service: "cults3d",
    fields: [
      { key: "cults3d_user", label: "Usuário do Cults3D" },
      { key: "cults3d_key", label: "Chave da API do Cults3D" },
    ],
  },
  {
    service: "etsy",
    fields: [
      { key: "etsy_keystring", label: "Keystring do Etsy" },
      { key: "etsy_shared_secret", label: "Shared secret do Etsy" },
    ],
  },
  {
    service: "thingiverse",
    fields: [{ key: "thingiverse", label: "App Token do Thingiverse" }],
  },
  {
    service: "myminifactory",
    fields: [{ key: "myminifactory", label: "Chave da API do MyMiniFactory" }],
  },
  {
    service: "cgtrader",
    fields: [{ key: "cgtrader", label: "Chave da API do CGTrader" }],
  },
  {
    service: "tmdb",
    fields: [{ key: "tmdb", label: "Token de leitura da API do TMDB" }],
  },
  {
    service: "igdb",
    fields: [
      { key: "igdb_client_id", label: "Client ID do IGDB (Twitch)" },
      { key: "igdb_client_secret", label: "Client Secret do IGDB (Twitch)" },
    ],
  },
  { service: "gemini", fields: [{ key: "gemini", label: "Chave da API do Gemini" }] },
];

export function ApiKeys({
  apiKeys,
  onChange,
}: {
  apiKeys: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <section className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <h2 className="text-[length:var(--text-xl)] font-bold">Chaves de API</h2>
        <p className="max-w-[62ch] text-muted-foreground">
          Todas são gratuitas e opcionais. Sem uma chave, só aquela fonte fica
          de fora. Abra “Como conseguir” para ver o passo a passo.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {API_KEY_GROUPS.map((group) => {
        const guide = KEY_GUIDES[group.service];
        return (
          <div
            key={group.service}
            className="flex min-w-0 flex-col gap-3 rounded-[var(--radius-card)] bg-card p-5"
          >
            <p className="font-heading text-[length:var(--text-md)] font-semibold tracking-[-0.015em]">
              {guide?.titulo ?? group.service}
            </p>

            {group.fields.map((field) => (
              <div key={field.key} className="flex flex-col gap-1.5">
                <Label htmlFor={`key-${field.key}`}>{field.label}</Label>
                <Input
                  id={`key-${field.key}`}
                  type="password"
                  autoComplete="off"
                  value={apiKeys[field.key] ?? ""}
                  onChange={(event) => onChange(field.key, event.target.value)}
                />
              </div>
            ))}

            {guide && (
              <details className="text-sm text-muted-foreground">
                <summary className="cursor-pointer select-none text-primary hover:underline">
                  Como conseguir
                </summary>
                <ol className="mt-2 ml-4 list-decimal space-y-1">
                  {guide.passos.map((passo) => (
                    <li key={passo}>{passo}</li>
                  ))}
                </ol>
                <a
                  href={guide.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-foreground underline underline-offset-4 hover:text-primary"
                >
                  Abrir página
                </a>
              </details>
            )}
          </div>
        );
      })}
      </div>
    </section>
  );
}
