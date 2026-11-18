import {
  ClipboardList,
  File,
  type LucideIcon,
  Receipt,
  Truck,
} from "lucide-react"

import type { DocumentKind, DocumentPublic } from "@/client"
import { ListRow } from "@/components/App/ListRow"
import { Badge } from "@/components/ui/badge"
import { formatAmount, formatDate, isBusy, KIND, STATUS } from "@/lib/documents"

export const KIND_ICON: Record<DocumentKind, LucideIcon> = {
  invoice: Receipt,
  order: ClipboardList,
  delivery: Truck,
  unknown: File,
}

// TTC when the document gives it, else HT said so: never one for the other.
export function documentAmount(document: DocumentPublic) {
  if (document.kind === "delivery" || document.kind === "unknown") return null
  const currency = document.currency ?? "EUR"
  if (document.amount_incl_tax != null)
    return formatAmount(document.amount_incl_tax, currency)
  if (document.amount_excl_tax != null)
    return `${formatAmount(document.amount_excl_tax, currency)} HT`
  return null
}

export function DocumentBadge({ document }: { document: DocumentPublic }) {
  const { label, variant } = STATUS[document.status]
  return <Badge variant={variant}>{label}</Badge>
}

export function DocumentRow({
  document,
  onClick,
}: {
  document: DocumentPublic
  onClick: () => void
}) {
  const busy = isBusy(document)
  const kind = document.is_credit_note ? "Avoir" : KIND[document.kind]
  const amount = documentAmount(document)
  return (
    <ListRow
      icon={KIND_ICON[document.kind]}
      spin={busy}
      title={document.supplier ?? document.filename}
      subtitle={
        busy
          ? "L'IA lit le document…"
          : [kind, document.number]
              .filter((part) => part && part !== "—")
              .join(" ")
      }
      value={amount}
      meta={
        busy || document.status === "ok"
          ? formatDate(document.document_date)
          : STATUS[document.status].label
      }
      alert={document.status === "unreadable"}
      onClick={onClick}
    />
  )
}
