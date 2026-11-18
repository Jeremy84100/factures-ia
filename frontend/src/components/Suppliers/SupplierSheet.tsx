import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Lightbulb, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"

import { type SupplierDetail, SuppliersService } from "@/client"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { DocumentList } from "@/components/Purchases/PurchaseSheet"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { formatAmount, formatDate, groupIban, plural } from "@/lib/documents"
import { supplierQuery } from "@/lib/queries"
import { handleError } from "@/utils"
import { EditSupplier } from "./EditSupplier"

const REGIONS = new Intl.DisplayNames(["fr"], { type: "region" })

export function countryName(code: string | null | undefined) {
  if (!code) return null
  try {
    return REGIONS.of(code) ?? code
  } catch {
    return code
  }
}

// From the country unless the user said otherwise.
export function dateOrderLabel(supplier: SupplierDetail) {
  const order =
    supplier.date_order ??
    (supplier.country === "US"
      ? "month_first"
      : supplier.country && supplier.country !== "CA"
        ? "day_first"
        : null)
  if (!order) return "Lues par l'IA"
  return order === "day_first"
    ? "Jour/mois (08/01 = 8 janvier)"
    : "Mois/jour (08/01 = 1er août)"
}

function Details({ supplier }: { supplier: SupplierDetail }) {
  const rows: [string, React.ReactNode][] = [
    ["Pays", countryName(supplier.country) ?? "Inconnu"],
    ["Dates", dateOrderLabel(supplier)],
    ["Paiement", supplier.payment_terms ?? "30 jours (délai légal)"],
    ["E-mail", supplier.email ?? "—"],
    [
      "IBAN",
      supplier.iban ? (
        <span key="iban" className="flex flex-col">
          <span className="tabular-nums">{groupIban(supplier.iban)}</span>
          <span className="text-xs text-muted-foreground">
            {supplier.iban_confirmed_at
              ? `Confirmé le ${new Date(supplier.iban_confirmed_at).toLocaleDateString("fr-FR")}`
              : "Lu sur ses factures, pas encore confirmé"}
          </span>
        </span>
      ) : (
        "—"
      ),
    ],
  ]
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

// What a correction taught the app: replayed on the next documents, and
// removable when it was a mistake.
function Rules({ supplier }: { supplier: SupplierDetail }) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const forget = useMutation({
    mutationFn: (ruleId: string) =>
      SuppliersService.forgetRule({
        path: { id: supplier.id, rule_id: ruleId },
      }),
    onSuccess: () => showSuccessToast("Règle oubliée"),
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["suppliers"] }),
  })
  const rules = supplier.rules ?? []
  return (
    <section className="flex flex-col gap-2">
      <h2 className="px-1 text-sm font-semibold">Ce que l'appli a appris</h2>
      {rules.length === 0 ? (
        <p className="px-1 text-sm text-muted-foreground">
          Rien pour l'instant. Quand vous corrigez un document de ce
          fournisseur, l'appli s'en souvient pour les suivants.
        </p>
      ) : (
        <Card size="sm" className="gap-0 py-1">
          <ItemGroup className="gap-0">
            {rules.map((rule) => (
              <Item key={rule.id} size="sm">
                <ItemMedia variant="icon" className="text-muted-foreground">
                  <Lightbulb />
                </ItemMedia>
                <ItemContent className="min-w-0">
                  <ItemTitle className="font-normal">{rule.label}</ItemTitle>
                </ItemContent>
                <ItemActions>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Oublier"
                    disabled={forget.isPending}
                    onClick={() => forget.mutate(rule.id)}
                  >
                    <Trash2 />
                  </Button>
                </ItemActions>
              </Item>
            ))}
          </ItemGroup>
        </Card>
      )}
    </section>
  )
}

export function SupplierSheet({
  id,
  open,
  onOpenChange,
}: {
  id: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { data: supplier } = useQuery({
    ...supplierQuery(id ?? ""),
    enabled: !!id,
  })
  const [editing, setEditing] = useState(false)

  const subtitle = supplier
    ? [
        plural(supplier.documents ?? 0, "document", "documents"),
        Number(supplier.invoiced_incl_tax) !== 0 &&
          `${formatAmount(supplier.invoiced_incl_tax)} facturés`,
        supplier.last_document_date &&
          `dernier le ${formatDate(supplier.last_document_date)}`,
      ]
        .filter(Boolean)
        .join(" · ")
    : undefined

  return (
    <>
      <ResponsiveSheet
        open={open}
        onOpenChange={onOpenChange}
        title={supplier?.name ?? "Fournisseur"}
        description={subtitle}
      >
        {!supplier ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-5 w-3/4" />
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <section className="flex flex-col gap-3">
              <Details supplier={supplier} />
              <div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setEditing(true)}
                >
                  <Pencil data-icon="inline-start" />
                  Modifier
                </Button>
              </div>
            </section>
            <Rules supplier={supplier} />
            {(supplier.recent?.length ?? 0) > 0 && (
              <DocumentList
                documents={supplier.recent ?? []}
                title="Derniers documents"
              />
            )}
          </div>
        )}
      </ResponsiveSheet>
      {supplier && (
        <EditSupplier
          supplier={supplier}
          open={editing}
          onOpenChange={setEditing}
        />
      )}
    </>
  )
}
