import {
  Banknote,
  CircleCheck,
  Hourglass,
  type LucideIcon,
  TriangleAlert,
} from "lucide-react"

import type { Purchase, PurchaseStatus } from "@/client"
import { ListRow } from "@/components/App/ListRow"
import { Badge } from "@/components/ui/badge"
import {
  dueLabel,
  formatAmount,
  formatDate,
  PURCHASE_STATUS,
} from "@/lib/documents"

export const PURCHASE_ICON: Record<PurchaseStatus, LucideIcon> = {
  to_pay: CircleCheck,
  dispute: TriangleAlert,
  waiting: Hourglass,
  paid: Banknote,
}

export const allIssues = (purchase: Purchase) => [
  ...(purchase.issues ?? []),
  ...(purchase.lines ?? []).flatMap((line) => line.issues ?? []),
]

// Overbilled, incl. tax when the invoice gives its tax.
export const overbilled = (purchase: Purchase) =>
  Math.max(0, Number(purchase.gap_incl_tax ?? purchase.gap_excl_tax ?? 0))

export const isCredit = (purchase: Purchase) =>
  Number(purchase.to_pay_incl_tax ?? 0) < 0

export const paidOn = (purchase: Purchase) =>
  formatDate(purchase.paid_at?.slice(0, 10))

// What is to pay (or was paid), incl. tax. Null while no invoice came.
export function purchaseAmount(purchase: Purchase): string | null {
  if (!purchase.invoices?.length) return null
  // Once paid, what was paid; before, what is left to pay.
  const incl = purchase.paid_at
    ? purchase.invoiced_incl_tax
    : purchase.to_pay_incl_tax
  if (incl !== null && incl !== undefined) return formatAmount(incl)
  if (purchase.invoiced_excl_tax)
    return `${formatAmount(purchase.invoiced_excl_tax)} HT`
  return null
}

// The full sentence is in the detail; the list gets a few words that fit a phone.
export function shortReason(text: string): string {
  const pair = (a: string, b: string) =>
    text.match(new RegExp(`${a} (\\S+), ${b} (\\S+)`))
  const billed = pair("facturé", "livré")
  if (billed) return `Facturé ${billed[1]}, livré ${billed[2]}`
  const over = pair("livré", "commandé")
  if (over) return `Livré ${over[1]}, commandé ${over[2]}`
  const extra = pair("facturé", "commandé")
  if (extra) return `Facturé ${extra[1]}, commandé ${extra[2]}`
  if (text.includes("Mode de livraison")) return "Mode de livraison différent"
  if (text.includes("prix facturé")) return "Prix plus cher que commandé"
  if (text.includes("mais pas commandé")) return "Article non commandé"
  if (text.startsWith("Total facturé")) return "Total trop élevé"
  if (text.startsWith("Déjà payé")) return "Écart trouvé après paiement"
  if (text.includes(" à vérifier : ")) return "Un document est à vérifier"
  if (text.includes("n'est pas rangé")) return "Bon de livraison à ranger"
  const late = text.match(/\((\d+) jours? de retard\)/)
  if (late) return `Livraison attendue depuis ${late[1]} j`
  return text
}

function summary(purchase: Purchase): string {
  switch (purchase.status) {
    case "dispute":
      return shortReason(
        purchase.notes?.find((note) => note.startsWith("Déjà payé")) ??
          allIssues(purchase)[0] ??
          "Un point bloque le paiement",
      )
    case "waiting":
      if (purchase.iban_warning) return "Nouvel IBAN : appelez avant de payer"
      return shortReason(purchase.notes?.[0] ?? "Il manque un document")
    case "paid":
      return `Payé le ${paidOn(purchase)}`
    default:
      if (purchase.settled_at) return "Litige réglé"
      if (isCredit(purchase)) return "Avoir à déduire"
      if (purchase.invoice_only) return "Facture seule"
      if (!purchase.orders?.length) return "Sans bon de commande"
      return "Tout concorde"
  }
}

export const purchaseTitle = (purchase: Purchase) =>
  purchase.supplier ?? purchase.order_reference

// "Commande CMD-26-101", "Facture TPP-0458", "Livraison sans bon de commande".
export function purchaseSubtitle(purchase: Purchase) {
  if (purchase.orders?.length) return `Commande ${purchase.order_reference}`
  if (purchase.invoice_only) return `Facture ${purchase.order_reference}`
  return `Sans bon de commande · réf. ${purchase.order_reference}`
}

export function PurchaseBadge({ purchase }: { purchase: Purchase }) {
  const { label, variant } = PURCHASE_STATUS[purchase.status]
  return <Badge variant={variant}>{label}</Badge>
}

function meta(purchase: Purchase): { text: string; alert: boolean } {
  if (purchase.status === "to_pay") {
    if (isCredit(purchase)) return { text: "À déduire", alert: false }
    const due = dueLabel(purchase.due_date)
    if (due) return { text: due.text, alert: due.late }
  }
  return {
    text: PURCHASE_STATUS[purchase.status].label,
    alert: purchase.status === "dispute" || !!purchase.iban_warning,
  }
}

export function PurchaseRow({
  purchase,
  onClick,
}: {
  purchase: Purchase
  onClick: () => void
}) {
  const { text, alert } = meta(purchase)
  return (
    <ListRow
      icon={PURCHASE_ICON[purchase.status]}
      title={purchaseTitle(purchase)}
      subtitle={summary(purchase)}
      value={purchaseAmount(purchase)}
      meta={text}
      alert={alert}
      onClick={onClick}
    />
  )
}
