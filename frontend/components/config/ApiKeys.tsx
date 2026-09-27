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
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">Chaves de API</h2>
      {API_KEY_GROUPS.map((group) => {
        const guide = KEY_GUIDES[group.service];
        return (
          <div
            key={group.service}
            className="flex flex-col gap-3 rounded-lg border p-4"
          >
            <p className="font-medium">{guide?.titulo ?? group.service}</p>

            {group.fields.map((field) => (
              <div key={field.key} className="flex max-w-sm flex-col gap-1">
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
                <summary className="cursor-pointer select-none">
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
                  className="mt-2 inline-block underline"
                >
                  Abrir página
                </a>
              </details>
            )}
          </div>
        );
      })}
    </section>
  );
}
