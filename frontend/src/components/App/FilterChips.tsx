import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"

export interface Chip<T extends string> {
  value: T
  label: string
  count?: number
}

// shadcn ToggleGroup, one choice at a time, scrollable sideways on a phone.
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
    <div className="no-scrollbar -mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
      <ToggleGroup
        type="single"
        variant="outline"
        spacing={2}
        value={value}
        onValueChange={(next) => {
          if (next) onChange(next as T)
        }}
        className="md:flex-wrap"
      >
        {chips.map((chip) => (
          <ToggleGroupItem
            key={chip.value}
            value={chip.value}
            className="h-9 px-4 data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
          >
            {chip.label}
            {chip.count !== undefined && chip.count > 0 && (
              <span
                className={cn(
                  "tabular-nums",
                  chip.value === value
                    ? "text-primary-foreground/70"
                    : "text-muted-foreground",
                )}
              >
                {chip.count}
              </span>
            )}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}
