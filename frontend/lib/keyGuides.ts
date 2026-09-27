// Guias de como conseguir cada chave de API, em linguagem leiga (o usuário
// não programa). URLs conferidas em 27/09/2026 - ver relatório da Tarefa 17
// para notas sobre a confirmação de cada uma.

export type KeyGuide = {
  titulo: string;
  passos: string[];
  url: string;
};

export const KEY_GUIDES: Record<string, KeyGuide> = {
  youtube: {
    titulo: "YouTube",
    passos: [
      "Acesse o Google Cloud Console e crie um projeto (ou use um já existente).",
      "No menu, vá em “APIs e serviços” → “Biblioteca”, procure por “YouTube Data API v3” e clique em “Ativar”.",
      "Vá em “Credenciais” → “Criar credenciais” → “Chave de API”.",
      "Copie a chave gerada e cole aqui.",
    ],
    url: "https://console.cloud.google.com/apis/credentials",
  },
  reddit: {
    titulo: "Reddit",
    passos: [
      "Acesse reddit.com/prefs/apps com sua conta do Reddit.",
      "Clique em “create another app...” no fim da página.",
      "Escolha o tipo “script”, dê um nome qualquer e preencha “redirect uri” com http://localhost:3000.",
      "Clique em “create app”.",
      "O “client id” aparece embaixo do nome do app; o “secret” é o campo logo abaixo. Copie os dois.",
    ],
    url: "https://www.reddit.com/prefs/apps",
  },
  sketchfab: {
    titulo: "Sketchfab",
    passos: [
      "Opcional: funciona sem chave, a chave só evita limites.",
      "Acesse sketchfab.com/settings/password com sua conta do Sketchfab.",
      "Na aba “Password & API”, copie o “API Token” mostrado na página.",
    ],
    url: "https://sketchfab.com/settings/password",
  },
  cults3d: {
    titulo: "Cults3D",
    passos: [
      "Acesse cults3d.com/en/api/keys com sua conta do Cults3D.",
      "Gere uma nova chave de API na página.",
      "Copie seu nome de usuário do Cults3D e a chave gerada; os dois são necessários.",
    ],
    url: "https://cults3d.com/en/api/keys",
  },
  gemini: {
    titulo: "Gemini",
    passos: [
      "É gratuito. Usado para explicar as tendências do radar e, mais adiante, para analisar modelos 3D.",
      "Acesse aistudio.google.com/app/apikey com sua conta do Google.",
      "Clique em “Create API key” e escolha um projeto.",
      "Copie a chave gerada e cole aqui.",
    ],
    url: "https://aistudio.google.com/app/apikey",
  },
};
