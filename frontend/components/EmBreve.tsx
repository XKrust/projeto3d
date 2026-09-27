// Tela de uma função que ainda não existe: diz o que ela vai fazer, sem
// prometer números nem datas inventadas.
export function EmBreve({
  etapa,
  titulo,
  texto,
  itens,
}: {
  etapa: number;
  titulo: string;
  texto: string;
  itens: string[];
}) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-6 sm:px-8 sm:py-12">
      <p className="inline-flex w-fit items-center gap-2 rounded-full border border-border px-3 py-1 text-sm text-muted-foreground">
        <span aria-hidden="true" className="size-1.5 rounded-full bg-primary" />
        Chega na Etapa {etapa}
      </p>
      <h1 className="text-[length:var(--text-display)] font-bold">{titulo}</h1>
      <p className="max-w-[58ch] text-[length:var(--text-md)] leading-snug text-muted-foreground">
        {texto}
      </p>
      <ul className="flex flex-col border-b border-border">
        {itens.map((item) => (
          <li
            key={item}
            className="flex gap-4 border-t border-border py-4 text-foreground"
          >
            <span aria-hidden="true" className="text-primary">
              →
            </span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
