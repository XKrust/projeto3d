import { EmBreve } from "@/components/EmBreve";

export default function SazonalPage() {
  return (
    <EmBreve
      etapa={2}
      titulo="O calendário do que vende em cada época."
      texto="Datas que puxam vendas em cada país — Halloween, Natal, Dia das Mães, Golden Week no Japão — com o prazo certo para começar a modelar antes do pico."
      itens={[
        "Calendário por país, com as datas que importam para impressão 3D e assets",
        "Aviso de quando começar, contando o seu tempo de modelagem",
        "Temas que costumam vender em cada data",
      ]}
    />
  );
}
