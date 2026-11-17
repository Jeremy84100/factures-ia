import {
  ClipboardList,
  File,
  Loader2,
  type LucideIcon,
  Receipt,
  Truck,
} from "lucide-react"

import type { DocumentKind, DocumentPublic } from "@/client"
import { ListRow } from "@/components/App/ListRow"
import {
  formatAmount,
  formatDate,
  isBusy,
  KIND,
  STATUS,
  STATUS_TONE,
  TONE_TEXT,
} from "@/lib/documents"

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

export function DocumentRow({
  document,
  onClick,
}: {
  document: DocumentPublic
  onClick: () => void
}) {
  const busy = isBusy(document)
  const tone = STATUS_TONE[document.status]
  const kind = document.is_credit_note ? "Avoir" : KIND[document.kind]
  return (
    <ListRow
      icon={busy ? Loader2 : KIND_ICON[document.kind]}
      spin={busy}
      tone={busy || document.status === "ok" ? "neutral" : tone}
      title={document.supplier ?? document.filename}
      subtitle={
        busy
          ? "L'IA lit le document…"
          : [kind, document.number, formatDate(document.document_date)]
              .filter((part) => part && part !== "—")
              .join(" · ")
      }
      end={documentAmount(document)}
      endSub={
        busy || document.status === "ok" ? undefined : (
          <span className={TONE_TEXT[tone]}>
            {STATUS[document.status].label}
          </span>
        )
      }
      onClick={onClick}
    />
  )
}
