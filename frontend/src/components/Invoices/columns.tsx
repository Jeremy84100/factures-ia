import type { ColumnDef } from "@tanstack/react-table"

import type { InvoicePublic } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { formatAmount, formatDate } from "@/lib/invoices"
import { InvoiceActionsMenu } from "./InvoiceActionsMenu"
import { StatusBadge } from "./StatusBadge"

const money = (invoice: InvoicePublic, value: string | null | undefined) =>
  formatAmount(value, invoice.currency ?? "EUR")

export const columns: ColumnDef<DataTableFeatures, InvoicePublic>[] = [
  {
    accessorKey: "status",
    header: "Statut",
    cell: ({ row }) => <StatusBadge invoice={row.original} />,
  },
  {
    accessorKey: "supplier",
    header: "Fournisseur",
    cell: ({ row }) => (
      <div className="flex flex-col">
        <span className="flex items-center gap-2 font-medium">
          {row.original.supplier ?? "—"}
          {row.original.is_credit_note && (
            <Badge variant="outline">Avoir</Badge>
          )}
        </span>
        <span className="max-w-48 truncate text-xs text-muted-foreground">
          {row.original.filename}
        </span>
      </div>
    ),
  },
  {
    accessorKey: "invoice_number",
    header: "Numéro",
    cell: ({ row }) => (
      <span className="font-mono text-xs">
        {row.original.invoice_number ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "invoice_date",
    header: "Date",
    cell: ({ row }) => formatDate(row.original.invoice_date),
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
        <InvoiceActionsMenu invoice={row.original} />
      </div>
    ),
  },
]
