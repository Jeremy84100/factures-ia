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

export function documentAmount(document: DocumentPublic) {
  const value =
    document.kind === "invoice"
      ? document.amount_incl_tax
      : document.kind === "order"
        ? document.amount_excl_tax
        : null
  return value === null || value === undefined
    ? null
    : formatAmount(value, document.currency ?? "EUR")
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
          : [kind, document.number, formatDate(document.document_date)]
              .filter((part) => part && part !== "—")
              .join(" · ")
      }
      actions={
        <>
          {amount && (
            <span className="text-sm font-medium tabular-nums">{amount}</span>
          )}
          {!busy && document.status !== "ok" && (
            <DocumentBadge document={document} />
          )}
        </>
      }
      onClick={onClick}
    />
  )
}
