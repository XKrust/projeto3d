# Design — Radar 3D

Sistema de design travado do app. Toda tela nova (Sazonal, Hype, Analisar) lê este
arquivo antes de ser desenhada. Não escolha outro tema por tela: amplie este arquivo
quando o sistema precisar crescer. Os valores vivem em `frontend/app/tokens.css`.

## Gênero
Atmosférico — tela escura com um único brilho laranja parado no canto superior direito.
Quem modela 3D passa o dia no Blender, então o escuro é a casa dele. O laranja é o da
"oficina 3D".

## Famílias de macroestrutura
- **Telas de dados (Radar, Hype):** Stat-Led. O item nº 1 abre a tela com o número
  real dele em tamanho grande (nunca um número inventado), sempre ao lado de uma frase
  que diz o que ele significa. Depois vem o ranking em linhas (lista ordenada, sem
  grade de cards iguais).
- **Telas de ajuste (Configurações):** Long Document. Título grande, uma introdução
  curta e seções com título e um parágrafo explicando para que servem. Painéis
  (`bg-card`) só para grupos de campos.
- **Telas futuras (Em breve):** declaração curta. Um selo "Chega na Etapa N", uma frase
  forte e uma lista do que a tela vai fazer, sem datas nem números inventados.

## Tema
- `--color-paper`   oklch(14.5% 0.010 55) — fundo
- `--color-paper-2` oklch(18% 0.011 55) — painéis (`bg-card`)
- `--color-paper-3` oklch(22.5% 0.012 55) — hover, menus
- `--color-rule`    oklch(30% 0.010 55) — linhas e bordas
- `--color-ink`     oklch(94% 0.008 75) — texto principal
- `--color-muted`   oklch(78% 0.008 65) — texto secundário
- `--color-neutral` oklch(64% 0.010 60) — legendas (`text-muted-foreground`)
- `--color-accent`  oklch(74% 0.165 55) — laranja; no máximo 3–5% da tela
- `--color-focus`   oklch(80% 0.15 62)
- Sinais (só com texto ao lado): `--color-signal-up` verde, `--color-signal-mid` âmbar,
  `--color-signal-down` vermelho.

As variáveis do shadcn/ui (`--background`, `--primary`…) apontam para esses tokens em
`frontend/app/globals.css`, então botões, tabelas e selects herdam o tema.

## Tipografia
- **Títulos e números grandes:** Bricolage Grotesque (700–800), tracking de −0.025em
  a −0.045em. Classe `font-heading`. Sempre em pé: título em itálico é proibido.
- **Texto:** Geist 400. Classe `font-sans` (padrão).
- **Nota fora da curva:** Geist Mono, só no logotipo `radar·3d`.
- Escala 1.25 em `tokens.css` (`--text-md` … `--text-display`, `--text-figure`).
- Toda coluna de números usa `tnum` (algarismos tabulares).

## Espaço
Escala de 4pt com nomes (`--space-sm` … `--space-3xl`). Entre seções grandes, use
`--space-2xl`. O conteúdo fica em `max-w-6xl` (dados) ou `max-w-5xl` (documento), com
`px-4 sm:px-8`.

## Movimento
- Curvas: `--ease-out`, `--ease-in`, `--ease-in-out`. Só `transform` e `opacity`, nunca
  `transition-all`.
- A única animação de entrada é a contagem do número do destaque (~520 ms).
- Com "reduzir movimento" ligado, tudo vira no máximo 150 ms e o número aparece pronto.

## Microinterações
- Sucesso em silêncio: o texto de status muda, sem toast comemorativo.
- Botão em andamento troca o rótulo ("Iniciando…", "Salvando…") e fica desabilitado.
- Foco sempre visível: contorno de 2px na cor `--color-focus`, sem animação.

## Voz dos botões
- **Principal:** pílula preenchida com o laranja, texto escuro (`rounded-full`,
  `h-9 px-5`). Um por área.
- **Secundário:** pílula com contorno (`variant="outline"`, `rounded-full`).
- A barra "Salvar" das Configurações é uma pílula fixa no rodapé da tela.

## Navegação e rodapé
- **N5 · Pílula flutuante** no topo, centralizada, com fundo translúcido. A tela atual
  fica em laranja, e as telas que ainda não existem ficam em tom mais apagado. Em
  telas ≤ 640px, rótulos curtos (Config, Analisar) e o logotipo é omitido.
- **Ft2 · Linha única** no rodapé: o que o app é e o aviso de que notas e preços são
  estimativas.

## O que toda tela DEVE seguir
- As mesmas cores, fontes, nav e rodapé.
- "Chance de venda" e "preço" sempre rotulados como estimativa.
- Nada de número, depoimento ou métrica inventados. Sem dado real, mostre "—" ou
  explique por que falta (ex.: "A linha aparece depois de 2 dias de coleta.").
- Nada de rolagem lateral de página em 320 / 375 / 414 / 768 px. Tabelas largas rolam
  dentro do próprio quadro.

## O que pode variar
- A macroestrutura, dentro da família da tela.
- O conteúdo do destaque (Radar: nota de oportunidade; Hype: dias até a estreia, por
  exemplo).

## Exports

### tokens.css
Ver `frontend/app/tokens.css` (fonte da verdade).

### shadcn/ui
Mapeamento em `frontend/app/globals.css` (`:root { --background: var(--color-paper); … }`).
