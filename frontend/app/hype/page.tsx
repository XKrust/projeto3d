import { EmBreve } from "@/components/EmBreve";

export default function HypePage() {
  return (
    <EmBreve
      etapa={2}
      titulo="O hype antes de ele chegar."
      texto="Estreias de anime, filmes e jogos que vão gerar procura por modelos, para você ter o personagem pronto no dia em que todo mundo começar a buscar."
      itens={[
        "Próximas estreias de anime (AniList), filmes (TMDB) e jogos (IGDB)",
        "Quanto tempo falta para o lançamento e para o pico de procura",
        "Ligação direta com os tópicos do radar",
      ]}
    />
  );
}
