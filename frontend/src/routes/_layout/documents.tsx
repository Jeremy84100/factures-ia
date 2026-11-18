import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FileText } from "lucide-react"
import { useState } from "react"

import type { DocumentPublic } from "@/client"
import { EmptyState } from "@/components/App/EmptyState"
import { type Chip, FilterChips } from "@/components/App/FilterChips"
import { ListGroup } from "@/components/App/ListRow"
import { SearchBox } from "@/components/App/SearchBox"
import { UploadButton } from "@/components/App/UploadButton"
import { DocumentRow } from "@/components/Documents/DocumentRow"
import { DocumentSheet } from "@/components/Documents/DocumentSheet"
import { fold, needsReview, plural } from "@/lib/documents"
import { documentsQuery, useLiveOptions } from "@/lib/queries"

const FILTERS = ["all", "invoice", "order", "delivery", "review"] as const
type Filter = (typeof FILTERS)[number]

const MATCH: Record<Filter, (document: DocumentPublic) => boolean> = {
  all: () => true,
  invoice: (d) => d.kind === "invoice",
  order: (d) => d.kind === "order",
  delivery: (d) => d.kind === "delivery",
  review: needsReview,
}

const LABELS: Record<Filter, string> = {
  all: "Tous",
  invoice: "Factures",
  order: "Commandes",
  delivery: "Livraisons",
  review: "À vérifier",
}

export const Route = createFileRoute("/_layout/documents")({
  validateSearch: (search: Record<string, unknown>): { filter?: Filter } =>
    FILTERS.includes(search.filter as Filter)
      ? { filter: search.filter as Filter }
      : {},
  loader: ({ context }) => context.queryClient.ensureQueryData(documentsQuery),
  component: Documents,
  head: () => ({ meta: [{ title: "Documents - Factures IA" }] }),
})

function Nothing({ filter }: { filter: Filter }) {
  return filter === "review" ? (
    <EmptyState
      icon={FileText}
      title="Rien à vérifier"
      description="L'IA a tout lu sans hésiter."
    />
  ) : (
    <EmptyState
      icon={FileText}
      title="Aucun document ici"
      description="Déposez vos commandes, bons de livraison et factures en vrac : ils sont triés tout seuls."
    >
      <UploadButton />
    </EmptyState>
  )
}

function Documents() {
  const { filter = "all" } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const live = useLiveOptions()
  const { data } = useSuspenseQuery(live.documents)
  const [selected, setSelected] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [query, setQuery] = useState("")

  const chips: Chip<Filter>[] = FILTERS.map((value) => ({
    value,
    label: LABELS[value],
    count: value === "all" ? undefined : data.data.filter(MATCH[value]).length,
  }))
  const term = fold(query.trim())
  const shown = data.data.filter(
    (d) =>
      MATCH[filter](d) &&
      (!term ||
        fold(
          [d.supplier, d.number, d.order_reference, d.filename]
            .filter(Boolean)
            .join(" "),
        ).includes(term)),
  )

  return (
    <div className="flex flex-col gap-4">
      <SearchBox
        value={query}
        onChange={setQuery}
        placeholder={`Chercher dans ${plural(data.count, "document", "documents")}`}
      />

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

      {shown.length === 0 ? (
        <Nothing filter={filter} />
      ) : (
        <ListGroup>
          {shown.map((document) => (
            <DocumentRow
              key={document.id}
              document={document}
              onClick={() => {
                setSelected(document.id)
                setSheetOpen(true)
              }}
            />
          ))}
        </ListGroup>
      )}

      <DocumentSheet
        document={data.data.find((d) => d.id === selected)}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  )
}
