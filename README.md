# Radar 3D

Ferramenta para modeladores 3D descobrirem **o que modelar**, **quando entregar** e **onde
vender**: radar de tendências por país e loja, calendário sazonal, hype de lançamentos
(anime, filmes, jogos) e um analisador de modelo com IA que prepara a venda (lojas, preço,
chance, anúncio pronto, capa, variações e onde divulgar).

Roda no seu computador (Windows); nada é enviado para servidor nosso.

## Instalar

1. Baixe o **`Radar3D-Setup.exe`** que está aqui na página inicial do repositório (clique
   nele e depois em **Download**), ou baixe tudo em **Code → Download ZIP** e abra o
   `Radar3D-Setup.exe` que vem dentro.
2. Abra o arquivo e siga o instalador (não pede senha de administrador).
   O Windows pode avisar que o app é de um editor desconhecido: clique em
   **Mais informações → Executar assim mesmo**.
3. Abra pelo menu Iniciar (**Radar 3D**). Na primeira vez ele baixa o Python e as
   bibliotecas (uns 100 MB, alguns minutos, precisa de internet). Depois abre em segundos.

Para desligar: menu Iniciar → **Parar Radar 3D**. Seus dados ficam em
`%LOCALAPPDATA%\Radar3D\data` e continuam lá se você desinstalar.

As chaves de API (Gemini, Reddit etc.) são opcionais e ficam na tela **Configurações**.

## Para quem mexe no código

Veja `CLAUDE.md` (mapa dos docs), `docs/como-rodar.md` (rodar pelo código com `ferramentas-dev\iniciar.bat`)
e `docs/instalador.md` (como o instalador é montado e publicado).
