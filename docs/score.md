# Score

O score é calculado por (tópico, país, plataforma, dia). Os pesos ficam em `config`.

- **demanda** (0–100): percentil do sinal ponderado entre os tópicos do país. O sinal combina Trends, YouTube, Reddit e engajamento nas plataformas.
- **momentum** (0–100): `(média dos últimos 3 dias / média dos 7 dias anteriores) − 1`, limitado a [−1, +2] e mapeado para 0–100.
- **saturação** (0–100): percentil da quantidade de anúncios do tema na plataforma.
- **pico previsto:**
  - Hype e sazonal: data do evento − antecedência (padrão de 21 dias).
  - Orgânico: hoje, se o momentum está caindo; hoje + 10 dias, se está subindo.
- **entrega** = hoje + tempo de modelagem do usuário (padrão de 7 dias).
- **fit_janela** = 1 se pico ≥ entrega. Senão, `0.5^(dias_atraso/7)`.
- **oportunidade** = `(0.40·demanda + 0.25·momentum + 0.35·(100−saturação)) · fit_janela`.
- **fit_plataforma** = força da plataforma no país × compatibilidade de mercado × presença do tema na plataforma.
- **Chance de venda:** ≥70 é Alta, 40–69 é Média, <40 é Baixa. Sempre rotulada como "estimativa".
