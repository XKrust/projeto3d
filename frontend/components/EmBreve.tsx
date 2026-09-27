export function EmBreve({ etapa }: { etapa: number }) {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <p className="text-muted-foreground">Chega na Etapa {etapa}.</p>
    </div>
  );
}
