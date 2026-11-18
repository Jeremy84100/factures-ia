import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Building2 } from "lucide-react"
import { useState } from "react"

import { EmptyState } from "@/components/App/EmptyState"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { SearchBox } from "@/components/App/SearchBox"
import { UploadButton } from "@/components/App/UploadButton"
import {
  countryName,
  SupplierSheet,
} from "@/components/Suppliers/SupplierSheet"
import { fold, formatAmount, formatDate, plural } from "@/lib/documents"
import { suppliersQuery } from "@/lib/queries"

export const Route = createFileRoute("/_layout/suppliers")({
  // ?id=… opens a supplier's page, as from a purchase.
  validateSearch: (search: Record<string, unknown>): { id?: string } =>
    typeof search.id === "string" ? { id: search.id } : {},
  loader: ({ context }) => context.queryClient.ensureQueryData(suppliersQuery),
  component: Suppliers,
  head: () => ({ meta: [{ title: "Fournisseurs - Factures IA" }] }),
})

function Suppliers() {
  const { id } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const { data } = useSuspenseQuery(suppliersQuery)
  const [query, setQuery] = useState("")

  const term = fold(query.trim())
  const shown = data.data.filter((s) => !term || fold(s.name).includes(term))

  const open = (supplierId: string) => {
    navigate({ search: { id: supplierId }, replace: true })
  }

  if (data.count === 0) {
    return (
      <EmptyState
        icon={Building2}
        title="Aucun fournisseur pour l'instant"
        description="Chaque document déposé range son fournisseur ici, avec son IBAN, ses conditions de paiement et ce que vous avez corrigé."
      >
        <UploadButton />
      </EmptyState>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <SearchBox
        value={query}
        onChange={setQuery}
        placeholder={`Chercher parmi ${plural(data.count, "fournisseur", "fournisseurs")}`}
      />
      <ListGroup>
        {shown.map((supplier) => (
          <ListRow
            key={supplier.id}
            icon={Building2}
            title={supplier.name}
            subtitle={[
              plural(supplier.documents ?? 0, "document", "documents"),
              countryName(supplier.country),
            ]
              .filter(Boolean)
              .join(" · ")}
            value={
              Number(supplier.invoiced_incl_tax) !== 0
                ? formatAmount(supplier.invoiced_incl_tax)
                : undefined
            }
            meta={
              supplier.last_document_date
                ? formatDate(supplier.last_document_date)
                : undefined
            }
            chevron={Number(supplier.invoiced_incl_tax) === 0}
            onClick={() => open(supplier.id)}
          />
        ))}
      </ListGroup>
      <SupplierSheet
        id={id ?? null}
        open={!!id}
        onOpenChange={(next) => {
          if (!next) navigate({ search: {}, replace: true })
        }}
      />
    </div>
  )
}
