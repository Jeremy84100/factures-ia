import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Link2, ShoppingBag } from "lucide-react"
import { useState } from "react"

import type { Purchase } from "@/client"
import { EmptyState } from "@/components/App/EmptyState"
import { type Chip, FilterChips } from "@/components/App/FilterChips"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { DocumentSheet } from "@/components/Documents/DocumentSheet"
import { PurchaseRow } from "@/components/Purchases/PurchaseRow"
import { PurchaseSheet } from "@/components/Purchases/PurchaseSheet"
import { formatDate, KIND_LONG } from "@/lib/documents"
import { documentsQuery, purchasesQuery, useLiveOptions } from "@/lib/queries"

const FILTERS = [
  "all",
  "dispute",
  "late",
  "waiting",
  "to_pay",
  "no_order",
  "unlinked",
] as const
type Filter = (typeof FILTERS)[number]

const LABELS: Record<Filter, string> = {
  all: "Tous",
  dispute: "Litiges",
  late: "En retard",
  waiting: "En attente",
  to_pay: "Bons à payer",
  no_order: "Sans commande",
  unlinked: "À relier",
}

const MATCH: Record<Exclude<Filter, "unlinked">, (p: Purchase) => boolean> = {
  all: () => true,
  dispute: (p) => p.status === "dispute",
  late: (p) => !!p.late,
  waiting: (p) => p.status === "waiting",
  to_pay: (p) => p.status === "to_pay",
  no_order: (p) => p.status === "no_order",
}

export const Route = createFileRoute("/_layout/reconciliations")({
  validateSearch: (search: Record<string, unknown>): { filter?: Filter } =>
    FILTERS.includes(search.filter as Filter)
      ? { filter: search.filter as Filter }
      : {},
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(purchasesQuery),
      context.queryClient.ensureQueryData(documentsQuery),
    ]),
  component: Purchases,
  head: () => ({ meta: [{ title: "Achats - Factures IA" }] }),
})

function Nothing({ filter }: { filter: Filter }) {
  return (
    <EmptyState
      icon={ShoppingBag}
      title="Rien ici"
      description={
        filter === "unlinked"
          ? "Tous les documents sont rattachés à leur commande."
          : "Déposez une commande, son bon de livraison et sa facture : ils sont rapprochés tout seuls."
      }
    />
  )
}

function Purchases() {
  const { filter = "all" } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const live = useLiveOptions()
  const { data } = useSuspenseQuery(live.purchases)
  const { data: documents } = useSuspenseQuery(live.documents)
  const [purchaseKey, setPurchaseKey] = useState<string | null>(null)
  const [purchaseOpen, setPurchaseOpen] = useState(false)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [documentOpen, setDocumentOpen] = useState(false)

  const chips: Chip<Filter>[] = FILTERS.map((value) => ({
    value,
    label: LABELS[value],
    count:
      value === "all"
        ? undefined
        : value === "unlinked"
          ? data.unlinked.length
          : data.data.filter(MATCH[value]).length,
  }))

  const purchases = filter === "unlinked" ? [] : data.data.filter(MATCH[filter])
  const empty =
    filter === "unlinked" ? data.unlinked.length === 0 : purchases.length === 0

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        {filter === "unlinked"
          ? "Touchez un document, puis « Corriger » pour ajouter son numéro de commande."
          : "Commande, livraison et facture comparées ligne par ligne."}
      </p>

      <FilterChips
        chips={chips}
        value={filter}
        onChange={(value) =>
          navigate({
            search: value === "all" ? {} : { filter: value },
            replace: true,
          })
        }
      />

      {empty ? (
        <Nothing filter={filter} />
      ) : filter === "unlinked" ? (
        <ListGroup title="Sans numéro de commande">
          {data.unlinked.map((document) => (
            <ListRow
              key={document.id}
              icon={Link2}
              title={`${KIND_LONG[document.kind]} ${document.number ?? ""}`}
              subtitle={`${formatDate(document.document_date)} · ${document.filename}`}
              chevron
              onClick={() => {
                setDocumentId(document.id)
                setDocumentOpen(true)
              }}
            />
          ))}
        </ListGroup>
      ) : (
        <ListGroup>
          {purchases.map((purchase) => (
            <PurchaseRow
              key={purchase.key}
              purchase={purchase}
              onClick={() => {
                setPurchaseKey(purchase.key)
                setPurchaseOpen(true)
              }}
            />
          ))}
        </ListGroup>
      )}

      <PurchaseSheet
        purchase={data.data.find((p) => p.key === purchaseKey)}
        open={purchaseOpen}
        onOpenChange={setPurchaseOpen}
      />
      <DocumentSheet
        document={documents.data.find((d) => d.id === documentId)}
        open={documentOpen}
        onOpenChange={setDocumentOpen}
      />
    </div>
  )
}
