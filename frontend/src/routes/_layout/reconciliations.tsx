import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Check, GitCompareArrows, Minus } from "lucide-react"
import { Suspense, useState } from "react"

import {
  type DocumentRef,
  type Purchase,
  type PurchaseStatus,
  ReconciliationsService,
} from "@/client"
import {
  DataTable,
  type DataTableFeatures,
} from "@/components/Common/DataTable"
import { openPdf } from "@/components/Documents/DocumentActionsMenu"
import PendingDocuments from "@/components/Pending/PendingDocuments"
import { PurchaseDetail } from "@/components/Reconciliations/PurchaseDetail"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  formatAmount,
  formatDate,
  KIND,
  PURCHASE_STATUS,
} from "@/lib/documents"
import { cn } from "@/lib/utils"

type Tab = PurchaseStatus | "all" | "unlinked"

const TABS: { value: Tab; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "dispute", label: "Litiges" },
  { value: "waiting", label: "En attente" },
  { value: "no_order", label: "Sans commande" },
  { value: "to_pay", label: "Bons à payer" },
  { value: "unlinked", label: "À relier" },
]

export const Route = createFileRoute("/_layout/reconciliations")({
  component: Reconciliations,
  head: () => ({
    meta: [{ title: "Rapprochements - Factures IA" }],
  }),
})

function StatusCell({ purchase }: { purchase: Purchase }) {
  const { label, variant } = PURCHASE_STATUS[purchase.status]
  const badge = <Badge variant={variant}>{label}</Badge>
  const issues = [
    ...(purchase.issues ?? []),
    ...(purchase.lines ?? []).flatMap((line) => line.issues ?? []),
  ]
  if (issues.length === 0) return badge
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help">{badge}</span>
      </TooltipTrigger>
      <TooltipContent>
        <ul className="list-disc pl-4">
          {issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  )
}

const count = (documents: DocumentRef[] | undefined) =>
  documents?.length ? (
    <span className="tabular-nums">{documents.length}</span>
  ) : (
    <Minus className="size-4 text-muted-foreground" />
  )

const columns: ColumnDef<DataTableFeatures, Purchase>[] = [
  {
    accessorKey: "status",
    header: "Statut",
    cell: ({ row }) => <StatusCell purchase={row.original} />,
  },
  {
    accessorKey: "supplier",
    header: "Fournisseur",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.supplier ?? "—"}</span>
    ),
  },
  {
    accessorKey: "order_reference",
    header: "N° commande",
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.order_reference}</span>
    ),
  },
  {
    id: "order",
    header: "Commande",
    cell: ({ row }) =>
      row.original.orders?.length ? (
        <Check className="size-4" />
      ) : (
        <Minus className="size-4 text-muted-foreground" />
      ),
  },
  {
    id: "deliveries",
    header: "Livraisons",
    cell: ({ row }) => count(row.original.deliveries),
  },
  {
    id: "invoices",
    header: "Factures",
    cell: ({ row }) => count(row.original.invoices),
  },
  {
    accessorKey: "invoiced_excl_tax",
    header: () => <span className="block text-right">Facturé HT</span>,
    cell: ({ row }) => (
      <span className="block text-right tabular-nums">
        {formatAmount(row.original.invoiced_excl_tax)}
      </span>
    ),
  },
  {
    accessorKey: "gap_excl_tax",
    header: () => <span className="block text-right">Écart</span>,
    cell: ({ row }) => {
      const gap = Number(row.original.gap_excl_tax ?? 0)
      return (
        <span
          className={cn(
            "block text-right tabular-nums",
            gap > 0.02
              ? "font-semibold text-destructive"
              : "text-muted-foreground",
          )}
        >
          {row.original.gap_excl_tax === null ||
          row.original.gap_excl_tax === undefined
            ? "—"
            : formatAmount(gap)}
        </span>
      )
    },
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Détail</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <PurchaseDetail purchase={row.original} />
      </div>
    ),
  },
]

function Unlinked({ documents }: { documents: DocumentRef[] }) {
  if (documents.length === 0) {
    return (
      <p className="py-12 text-center text-muted-foreground">
        Tous les documents sont reliés à une commande.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Ces documents n'indiquent pas de numéro de commande. Ajoutez-le dans{" "}
        <Link to="/documents" className="underline">
          Documents
        </Link>{" "}
        › Corriger, et ils rejoindront leur achat.
      </p>
      <div className="flex flex-wrap gap-2">
        {documents.map((document) => (
          <Button
            key={document.id}
            variant="outline"
            size="sm"
            onClick={() => openPdf(document.id)}
          >
            {KIND[document.kind]} {document.number ?? document.filename}
            <span className="text-muted-foreground">
              {formatDate(document.document_date)}
            </span>
          </Button>
        ))}
      </div>
    </div>
  )
}

function PurchasesContent({ tab }: { tab: Tab }) {
  const { data } = useSuspenseQuery({
    queryKey: ["purchases"],
    queryFn: async () => (await ReconciliationsService.readPurchases()).data,
  })

  if (tab === "unlinked") return <Unlinked documents={data.unlinked} />

  const purchases =
    tab === "all" ? data.data : data.data.filter((p) => p.status === tab)

  if (purchases.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-muted p-4">
          <GitCompareArrows className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">Aucun achat ici</h3>
        <p className="text-muted-foreground">
          Déposez une commande, son bon de livraison et sa facture dans
          Documents : ils sont rapprochés automatiquement.
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={purchases} />
}

function Reconciliations() {
  const [tab, setTab] = useState<Tab>("all")

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Rapprochements</h1>
        <p className="text-muted-foreground">
          Commande, livraison et facture comparées ligne par ligne : on paie ce
          qui a été commandé et livré, au prix commandé
        </p>
      </div>
      <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
        <TabsList>
          {TABS.map(({ value, label }) => (
            <TabsTrigger key={value} value={value}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Suspense fallback={<PendingDocuments />}>
        <PurchasesContent tab={tab} />
      </Suspense>
    </div>
  )
}
