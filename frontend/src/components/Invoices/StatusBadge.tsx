import type { InvoicePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { STATUS } from "@/lib/invoices"

export function StatusBadge({ invoice }: { invoice: InvoicePublic }) {
  const { label, variant } = STATUS[invoice.status]
  const badge = <Badge variant={variant}>{label}</Badge>

  if (invoice.issues.length === 0) return badge

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help">{badge}</span>
      </TooltipTrigger>
      <TooltipContent>
        <ul className="list-disc pl-4">
          {invoice.issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  )
}
