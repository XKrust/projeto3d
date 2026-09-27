import { EmBreve } from "@/components/EmBreve";

export default function AnalisarPage() {
  return (
    <EmBreve
      etapa={3}
      titulo="Uma segunda opinião sobre o seu modelo."
      texto="Envie as imagens do modelo e receba uma avaliação com IA: o que está forte, o que melhorar, um título que vende e uma faixa de preço — sempre como estimativa."
      itens={[
        "Nota com rubrica clara, explicada em português",
        "Sugestão de título, plataforma e preço (estimativa)",
        "Comparação com modelos parecidos que já vendem",
      ]}
    />
  );
}
