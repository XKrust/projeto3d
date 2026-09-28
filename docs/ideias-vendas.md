# Ideias para o modelador vender mais

Banco de ideias pedido pelo usuário em 2026-09-27: "pense que o cara hoje não consegue vender bem".

Nada aqui está aprovado para implementação. Cada ideia entra numa etapa só depois de passar por brainstorming, spec e plano, como o resto do projeto.

- **Custo:** todas as ideias abaixo cabem no orçamento zero.
- **Dados:** usam o que o radar já coleta ou o Gemini free tier.

## Onde a venda falha hoje

1. **Tema errado ou atrasado.** O hype passou quando o modelo fica pronto. O radar já ataca isso.
2. **Anúncio fraco.** Título sem busca, tags ruins, thumbnail que não chama atenção.
3. **Preço no chute.** Caro demais não vende; barato demais deixa dinheiro na mesa.
4. **Uma plataforma só.** O mesmo arquivo poderia estar em 3 ou 4 lojas.
5. **Um produto só.** Não oferece variações, versão pré-suportada, bundle ou licença comercial.
6. **Ninguém fica sabendo.** Publica e não divulga onde o público está.
7. **Sem aprender com as próprias vendas.** Não sabe o que funcionou.

## Entregues

- **#1 (em parte):** na Etapa 3b, a venda mostra "≈ N vendas para cobrir as horas" (não no
  card do radar).
- **#3, #6 e #10:** Etapa 3c: variações que vendem (com prova nos anúncios do tema), nota da
  capa (checklist + capas dos mais curtidos) e risco de fan-art por loja (política oficial).
- **#2:** Etapa 3b: título, tags e descrição por loja e idioma, preço de lançamento de 48 h,
  ordem de publicação. Etapa 3c: onde divulgar (subreddits e hashtags).

## Ideias priorizadas

| # | Ideia | O que faz | Resolve | Etapa sugerida | Esforço |
|---|---|---|---|---|---|
| 1 | **"Vale a pena modelar?" (retorno por hora)** | No card do radar: preço mediano × chance de venda ÷ horas de modelagem → "≈ US$ X por hora de trabalho (estimativa)" | 1, 3 | 1b/2 | Baixo |
| 2 | **Plano de lançamento** | Depois da análise do modelo, um checklist pronto: título e tags por plataforma e idioma, preço de lançamento (desconto nas primeiras 48 h) e preço cheio, ordem de publicação nas lojas, e onde divulgar (subreddits e hashtags onde o tema está em alta) | 2, 3, 4, 6 | 3 | Médio |
| 3 | **Variações que vendem** | Para cada modelo ou tema, sugerir derivados: versão chibi, busto, pose alternativa, **versão pré-suportada** (valorizada em impressão 3D), base temática, kit ou bundle, licença comercial | 5 | 3 | Baixo (Gemini) |
| 4 | **Oportunidades ocultas** | Uma aba do radar só com temas de demanda alta e **pouquíssimos anúncios** numa plataforma específica ("ninguém vendendo X no Cults ainda") | 1, 4 | 1b | Baixo |
| 5 | **Lista de observação e alertas no app** | Marcar temas e personagens; um aviso aparece no app quando começam a subir ou quando a janela de pico se aproxima | 1 | 2 | Médio |
| 6 | **Checklist de thumbnail que vende** | No analisador: nota específica da imagem de capa (fundo, ângulo 3/4, escala, iluminação, texto), comparada às capas dos mais vendidos do mesmo tema | 2 | 3 | Baixo |
| 7 | **Minhas vendas e calibração** | O usuário registra o que publicou e vendeu (manual ou CSV da plataforma); a ferramenta mostra o que funcionou e ajusta o score à realidade dele | 7 | 3+ | Médio |
| 8 | **Publicar em várias lojas** | Para cada modelo, uma tabela das lojas onde ainda não está, com taxa, público e exigências de formato | 4 | 2/3 | Baixo |
| 9 | **Renda recorrente** | Sugerir quando vale montar coleção mensal (Patreon, MyMiniFactory Tribes) com base em temas que ficam em alta por muito tempo | 5 | 3+ | Baixo (conteúdo) |
| 10 | **Risco de fan-art** | Aviso por plataforma sobre remoção e licenciamento, e sugestão de versão "inspirada em" autoral quando o risco é alto | protege a conta | 3 | Baixo |

## Sugestão de ordem

1. **Etapa 1b:** junto com os coletores restantes, entram o #1 (retorno por hora) e o #4 (oportunidades ocultas). São baratos e usam dados que já existem.
2. **Etapa 2:** hype e sazonal, mais o #5 (lista de observação e alertas) e o #8 (várias lojas).
3. **Etapa 3:** o analisador vira um "assistente de lançamento", com #2, #3, #6 e #10.
4. **Depois:** #7 (minhas vendas) e #9 (renda recorrente).
