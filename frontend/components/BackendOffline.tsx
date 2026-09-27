export function BackendOffline() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-4 px-4 py-12 sm:px-8">
      <h1 className="text-[length:var(--text-2xl)] font-bold">O radar está desligado.</h1>
      <p className="max-w-[56ch] text-[length:var(--text-md)] leading-snug text-muted-foreground">
        Não consegui falar com o backend. Ele está ligado? Rode o
        iniciar.bat.
      </p>
    </div>
  );
}
