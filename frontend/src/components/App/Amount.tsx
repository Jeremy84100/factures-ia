import { visibleSpaces } from "@/lib/documents"
import { cn } from "@/lib/utils"

const euro = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

// Big figure with small cents, as on a banking app: "1 234,50 €".
export function Amount({
  value,
  className,
}: {
  value: number
  className?: string
}) {
  const [units, cents] = visibleSpaces(euro.format(value)).split(",")
  return (
    <span
      className={cn("font-semibold tracking-tight tabular-nums", className)}
    >
      {units}
      <span className="text-[0.55em] text-muted-foreground">,{cents} €</span>
    </span>
  )
}
