import { cn } from "@/lib/utils"

export interface Chip<T extends string> {
  value: T
  label: string
  count?: number
}

export function FilterChips<T extends string>({
  chips,
  value,
  onChange,
}: {
  chips: Chip<T>[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div
      role="tablist"
      className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 md:mx-0 md:flex-wrap md:px-0"
    >
      {chips.map((chip) => {
        const active = chip.value === value
        return (
          <button
            key={chip.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(chip.value)}
            className={cn(
              "flex h-9 shrink-0 items-center gap-1.5 rounded-full px-4 text-sm font-medium transition-colors",
              active
                ? "bg-foreground text-background"
                : "bg-surface text-foreground hover:bg-muted",
            )}
          >
            {chip.label}
            {chip.count !== undefined && chip.count > 0 && (
              <span
                className={cn(
                  "tabular-nums",
                  active ? "text-background/70" : "text-muted-foreground",
                )}
              >
                {chip.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
