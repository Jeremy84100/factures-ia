import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Lightbulb, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"

import { type Purchase, type SupplierDetail, SuppliersService } from "@/client"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import {
  PurchaseRow,
  purchaseSubtitle,
} from "@/components/Purchases/PurchaseRow"
import { PurchaseSheet } from "@/components/Purchases/PurchaseSheet"
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
import { purchasesQuery, supplierQuery } from "@/lib/queries"
import { handleError } from "@/utils"
import { EditSupplier } from "./EditSupplier"

// Shown before "Tout voir": enough for a phone screen.
const FIRST_PURCHASES = 5

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

// The account on file, then the others its invoices gave: the old ones, and
// a new one nobody has confirmed yet.
function Iban({ supplier }: { supplier: SupplierDetail }) {
  if (!supplier.iban) return "—"
  return (
    <span className="flex flex-col gap-1">
      <span className="flex flex-col">
        <span className="tabular-nums">{groupIban(supplier.iban)}</span>
        <span className="text-xs text-muted-foreground">
          {supplier.iban_confirmed_at
            ? `Confirmé le ${new Date(supplier.iban_confirmed_at).toLocaleDateString("fr-FR")}`
            : "Lu sur ses factures, pas encore confirmé"}
        </span>
      </span>
      {supplier.other_ibans?.map((other) => (
        <span key={other.iban} className="flex flex-col">
          <span className="tabular-nums text-muted-foreground">
            {groupIban(other.iban)}
          </span>
          <span
            className={
              other.newer
                ? "text-xs text-destructive"
                : "text-xs text-muted-foreground"
            }
          >
            {other.newer ? "Nouveau, pas encore confirmé" : "Ancien"}
            {other.number && ` · facture ${other.number}`}
            {other.last_seen && ` du ${formatDate(other.last_seen)}`}
          </span>
        </span>
      ))}
    </span>
  )
}

function Details({ supplier }: { supplier: SupplierDetail }) {
  const rows: [string, React.ReactNode][] = [
    ["Pays", countryName(supplier.country) ?? "Inconnu"],
    ["Dates", dateOrderLabel(supplier)],
    ["Paiement", supplier.payment_terms ?? "30 jours (délai légal)"],
    ["E-mail", supplier.email ?? "—"],
    ["IBAN", <Iban key="iban" supplier={supplier} />],
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

const sum = (purchases: Purchase[], amount: (p: Purchase) => unknown) =>
  purchases.reduce((total, p) => total + Number(amount(p) ?? 0), 0)

// Its whole story with you, in three figures, incl. tax.
function Totals({ purchases }: { purchases: Purchase[] }) {
  const billed = purchases.filter((p) => p.invoices?.length)
  const paid = billed.filter((p) => p.status === "paid")
  const unpaid = billed.filter((p) => p.status !== "paid")
  const figures: [string, number][] = [
    ["Facturé", sum(billed, (p) => p.invoiced_incl_tax)],
    ["Payé", sum(paid, (p) => p.invoiced_incl_tax)],
    ["Reste dû", sum(unpaid, (p) => p.to_pay_incl_tax)],
  ]
  return (
    <Card size="sm" className="grid grid-cols-3 gap-0 py-3">
      {figures.map(([label, value]) => (
        <div
          key={label}
          className="flex min-w-0 flex-col px-3 not-first:border-l"
        >
          <span className="text-xs text-muted-foreground">{label}</span>
          <span className="truncate font-semibold tabular-nums">
            {formatAmount(value)}
          </span>
        </div>
      ))}
    </Card>
  )
}

// The latest document of a purchase, to show the newest first.
const lastDate = (purchase: Purchase) =>
  [
    ...(purchase.orders ?? []),
    ...(purchase.deliveries ?? []),
    ...(purchase.invoices ?? []),
  ]
    .map((d) => d.document_date ?? "")
    .sort()
    .reverse()[0] ?? ""

function History({
  purchases,
  onOpen,
}: {
  purchases: Purchase[]
  onOpen: (key: string) => void
}) {
  const [all, setAll] = useState(false)
  const disputes = purchases.filter((p) => p.status === "dispute").length
  const shown = all ? purchases : purchases.slice(0, FIRST_PURCHASES)
  return (
    <section className="flex flex-col gap-2">
      <h2 className="px-1 text-sm font-semibold">
        {plural(purchases.length, "achat", "achats")}
        {disputes > 0 && (
          <span className="font-normal text-destructive">
            {" · "}
            {plural(disputes, "litige", "litiges")}
          </span>
        )}
      </h2>
      <Card size="sm" className="gap-0 py-1">
        <ItemGroup className="gap-0">
          {shown.map((purchase) => (
            <PurchaseRow
              key={purchase.key}
              purchase={purchase}
              title={purchaseSubtitle(purchase)}
              onClick={() => onOpen(purchase.key)}
            />
          ))}
        </ItemGroup>
        {!all && purchases.length > FIRST_PURCHASES && (
          <Button
            variant="ghost"
            size="sm"
            className="mx-2 mb-1"
            onClick={() => setAll(true)}
          >
            Tout voir ({purchases.length})
          </Button>
        )}
      </Card>
    </section>
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
  const { data: allPurchases } = useQuery({ ...purchasesQuery, enabled: !!id })
  const [editing, setEditing] = useState(false)
  const [purchaseKey, setPurchaseKey] = useState<string | null>(null)
  const [purchaseOpen, setPurchaseOpen] = useState(false)

  const purchases = (allPurchases?.data ?? [])
    .filter((p) => p.supplier_id === id)
    .sort((a, b) => lastDate(b).localeCompare(lastDate(a)))

  const subtitle = supplier
    ? [
        plural(supplier.documents ?? 0, "document", "documents"),
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
            {purchases.length > 0 && <Totals purchases={purchases} />}
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
            {purchases.length > 0 && (
              <History
                purchases={purchases}
                onOpen={(key) => {
                  setPurchaseKey(key)
                  setPurchaseOpen(true)
                }}
              />
            )}
            <Rules supplier={supplier} />
          </div>
        )}
      </ResponsiveSheet>
      <PurchaseSheet
        purchase={purchases.find((p) => p.key === purchaseKey)}
        unlinked={allPurchases?.unlinked}
        open={purchaseOpen}
        onOpenChange={setPurchaseOpen}
        fromSupplier
      />
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
