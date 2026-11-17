import type { ColumnDef } from "@tanstack/react-table"

import type { DocumentPublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { formatAmount, formatDate, KIND } from "@/lib/documents"
import { DocumentActionsMenu } from "./DocumentActionsMenu"
import { StatusBadge } from "./StatusBadge"

const money = (document: DocumentPublic, value: string | null | undefined) =>
  formatAmount(value, document.currency ?? "EUR")

export const columns: ColumnDef<DataTableFeatures, DocumentPublic>[] = [
  {
    accessorKey: "status",
    header: "Statut",
    cell: ({ row }) => <StatusBadge document={row.original} />,
  },
  {
    accessorKey: "kind",
    header: "Type",
    cell: ({ row }) => (
      <Badge variant="outline">
        {row.original.is_credit_note ? "Avoir" : KIND[row.original.kind]}
      </Badge>
    ),
  },
  {
    accessorKey: "supplier",
    header: "Fournisseur",
    cell: ({ row }) => (
      <div className="flex flex-col">
        <span className="font-medium">{row.original.supplier ?? "—"}</span>
        <span className="max-w-48 truncate text-xs text-muted-foreground">
          {row.original.filename}
        </span>
      </div>
    ),
  },
  {
    accessorKey: "number",
    header: "Numéro",
    cell: ({ row }) => (
      <div className="flex flex-col">
        <span className="font-mono text-xs">{row.original.number ?? "—"}</span>
        {row.original.order_reference && (
          <span className="font-mono text-xs text-muted-foreground">
            Cde {row.original.order_reference}
          </span>
        )}
      </div>
    ),
  },
  {
    accessorKey: "document_date",
    header: "Date",
    cell: ({ row }) => formatDate(row.original.document_date),
  },
  {
    accessorKey: "amount_excl_tax",
    header: () => <span className="block text-right">HT</span>,
    cell: ({ row }) => (
      <span className="block text-right tabular-nums text-muted-foreground">
        {money(row.original, row.original.amount_excl_tax)}
      </span>
    ),
  },
  {
    accessorKey: "amount_incl_tax",
    header: () => <span className="block text-right">TTC</span>,
    cell: ({ row }) => (
      <span className="block text-right font-medium tabular-nums">
        {money(row.original, row.original.amount_incl_tax)}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <DocumentActionsMenu document={row.original} />
      </div>
    ),
  },
]
