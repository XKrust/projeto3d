# Analisador de modelo (Etapa 3)

## Entrada

- 1 a 4 imagens, mais um wireframe opcional.
- Perguntas: autoral ou fan-art? Mercado? Horas gastas?

## Processamento

- **Referências:** 3 a 5 modelos mais bem avaliados do mesmo tema no Sketchfab e no Cults3D.
- **Rubrica de 0 a 10:**
  - anatomia
  - silhueta
  - detalhe
  - pose
  - materiais
  - render
  - apresentação
  - imprimibilidade (só para impressão)

## Saída

- **Preço** = mediana dos itens comparáveis × `(0.7 + 0.06·nota)`, na moeda local.
- **Chance de venda** = oportunidade × qualidade × (1 − saturação).
- **Provedor:** Gemini free tier, atrás de `ai/provider.py`.

Os detalhes são preenchidos ao implementar a Etapa 3.
