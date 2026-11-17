import type { DocumentPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { STATUS } from "@/lib/documents"

export function StatusBadge({ document }: { document: DocumentPublic }) {
  const { label, variant } = STATUS[document.status]
  const badge = <Badge variant={variant}>{label}</Badge>

  if (document.issues.length === 0) return badge

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-help">{badge}</span>
      </TooltipTrigger>
      <TooltipContent>
        <ul className="list-disc pl-4">
          {document.issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  )
}
