import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatRelativeTime, SOURCE_STATUS_META } from "@/lib/config-labels";
import type { SourceHealth as SourceHealthType } from "@/lib/config-types";

export function SourcesHealth({
  sources,
  onCollect,
  collectingSource,
}: {
  sources: SourceHealthType[];
  onCollect: (name: string) => void;
  collectingSource: string | null;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">Saúde das fontes</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Fonte</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Última coleta</TableHead>
            <TableHead>Itens</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sources.map((source) => {
            const meta =
              SOURCE_STATUS_META[source.status] ?? SOURCE_STATUS_META.never;
            return (
              <TableRow key={source.name}>
                <TableCell>{source.label}</TableCell>
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <span>
                      <span aria-hidden="true">{meta.emoji}</span> {meta.label}
                    </span>
                    {source.status === "error" && source.last_error && (
                      <span className="text-sm text-destructive">
                        {source.last_error}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>{formatRelativeTime(source.last_run)}</TableCell>
                <TableCell>{source.items_last_run}</TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onCollect(source.name)}
                    disabled={collectingSource === source.name}
                  >
                    Coletar
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </section>
  );
}
