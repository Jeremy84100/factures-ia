import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { FileText, Link2, ShoppingBag } from "lucide-react"
import { useState } from "react"

import {
  DocumentsService,
  type Purchase,
  type UnlinkedDocument,
} from "@/client"
import { EmptyState } from "@/components/App/EmptyState"
import { type Chip, FilterChips } from "@/components/App/FilterChips"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { DocumentSheet } from "@/components/Documents/DocumentSheet"
import { PurchaseRow } from "@/components/Purchases/PurchaseRow"
import { PurchaseSheet } from "@/components/Purchases/PurchaseSheet"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { formatDate, KIND_LONG } from "@/lib/documents"
import { documentsQuery, purchasesQuery, useLiveOptions } from "@/lib/queries"
import { handleError } from "@/utils"

const FILTERS = ["all", "to_pay", "dispute", "waiting", "paid"] as const
type Filter = (typeof FILTERS)[number]

const LABELS: Record<Filter, string> = {
  all: "Tous",
  to_pay: "À payer",
  dispute: "Litiges",
  waiting: "En attente",
  paid: "Payés",
}

const MATCH: Record<Filter, (p: Purchase) => boolean> = {
  all: () => true,
  to_pay: (p) => p.status === "to_pay",
  dispute: (p) => p.status === "dispute",
  waiting: (p) => p.status === "waiting",
  paid: (p) => p.status === "paid",
}

// Documents to file are shown with what is waiting for them.
const SHOWS_UNLINKED: Filter[] = ["all", "waiting"]

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
        filter === "paid"
          ? "Touchez « Payé » sur un achat une fois le virement fait : il est rangé ici."
          : "Déposez une commande, son bon de livraison et sa facture : ils sont rapprochés tout seuls."
      }
    />
  )
}

// One document set aside: one tap files it in the purchase it may belong to.
function ToFileRow({
  document,
  onOpen,
}: {
  document: UnlinkedDocument
  onOpen: () => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const link = useMutation({
    mutationFn: (order_reference: string) =>
      DocumentsService.updateDocument({
        path: { id: document.id },
        body: { order_reference },
      }),
    onSuccess: () => showSuccessToast("Document rangé dans son achat"),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
      queryClient.invalidateQueries({ queryKey: ["documents"] })
    },
  })
  const first = document.suggestions?.[0]
  return (
    <>
      <ListRow
        icon={Link2}
        title={`${KIND_LONG[document.kind]} ${document.number ?? ""}`}
        subtitle={
          first
            ? `${document.supplier ?? ""} · c'est la commande ${first.order_reference} ?`
            : `${formatDate(document.document_date)} · sans numéro de commande`
        }
        chevron={!first}
        onClick={onOpen}
      />
      {first && (
        <div className="flex flex-wrap gap-2 px-4 pb-3">
          {document.suggestions?.map((suggestion) => (
            <Button
              key={suggestion.key}
              size="sm"
              disabled={link.isPending}
              onClick={() => link.mutate(suggestion.order_reference)}
            >
              Oui, {suggestion.order_reference}
            </Button>
          ))}
          <Button size="sm" variant="secondary" onClick={onOpen}>
            Autre
          </Button>
        </div>
      )}
    </>
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
      value === "all" || value === "paid"
        ? undefined
        : data.data.filter(MATCH[value]).length +
          (value === "waiting" ? data.unlinked.length : 0),
  }))

  const purchases = data.data.filter(MATCH[filter])
  const toFile = SHOWS_UNLINKED.includes(filter) ? data.unlinked : []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Commande, livraison et facture comparées ligne par ligne.
        </p>
        <Button variant="link" size="sm" className="shrink-0" asChild>
          <Link to="/documents">
            <FileText data-icon="inline-start" />
            Documents
          </Link>
        </Button>
      </div>

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

      {toFile.length > 0 && (
        <ListGroup title="À ranger">
          {toFile.map((document) => (
            <ToFileRow
              key={document.id}
              document={document}
              onOpen={() => {
                setDocumentId(document.id)
                setDocumentOpen(true)
              }}
            />
          ))}
        </ListGroup>
      )}

      {purchases.length === 0 && toFile.length === 0 ? (
        <Nothing filter={filter} />
      ) : (
        purchases.length > 0 && (
          <ListGroup title={toFile.length > 0 ? "Achats" : undefined}>
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
        )
      )}

      <PurchaseSheet
        purchase={data.data.find((p) => p.key === purchaseKey)}
        unlinked={data.unlinked}
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
