import {
  CircleCheck,
  FileQuestion,
  Hourglass,
  type LucideIcon,
  TriangleAlert,
} from "lucide-react"

import type { Purchase, PurchaseStatus } from "@/client"
import { ListRow } from "@/components/App/ListRow"
import {
  formatAmount,
  PURCHASE_STATUS,
  PURCHASE_TONE,
  TONE_TEXT,
} from "@/lib/documents"

export const PURCHASE_ICON: Record<PurchaseStatus, LucideIcon> = {
  to_pay: CircleCheck,
  dispute: TriangleAlert,
  waiting: Hourglass,
  no_order: FileQuestion,
}

export const allIssues = (purchase: Purchase) => [
  ...(purchase.issues ?? []),
  ...(purchase.lines ?? []).flatMap((line) => line.issues ?? []),
]

export const overbilled = (purchase: Purchase) =>
  Math.max(0, Number(purchase.gap_excl_tax ?? 0))

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
  const late = text.match(/\((\d+) jours? de retard\)/)
  if (late) return `Livraison attendue depuis ${late[1]} j`
  return text
}

function summary(purchase: Purchase): string {
  switch (purchase.status) {
    case "dispute":
      return shortReason(
        allIssues(purchase)[0] ?? "Un point bloque le paiement",
      )
    case "waiting":
      return shortReason(purchase.notes?.[0] ?? "Il manque un document")
    case "no_order":
      return "Sans bon de commande"
    default:
      return purchase.late ? "Livré en retard" : "Tout concorde"
  }
}

export function PurchaseRow({
  purchase,
  onClick,
}: {
  purchase: Purchase
  onClick: () => void
}) {
  const tone = PURCHASE_TONE[purchase.status]
  const extra = overbilled(purchase)
  return (
    <ListRow
      icon={PURCHASE_ICON[purchase.status]}
      tone={tone}
      title={purchase.supplier ?? `Commande ${purchase.order_reference}`}
      subtitle={summary(purchase)}
      end={
        purchase.status === "dispute" && extra > 0.02 ? (
          <span className="text-destructive">+{formatAmount(extra)}</span>
        ) : (
          formatAmount(purchase.invoiced_excl_tax)
        )
      }
      endSub={
        <span className={TONE_TEXT[tone]}>
          {PURCHASE_STATUS[purchase.status].label}
        </span>
      }
      onClick={onClick}
    />
  )
}
