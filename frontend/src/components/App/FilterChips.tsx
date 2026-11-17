import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

export interface Chip<T extends string> {
  value: T
  label: string
  count?: number
}

// shadcn Tabs, in a horizontal ScrollArea so they slide on a phone.
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
    <Tabs value={value} onValueChange={(next) => onChange(next as T)}>
      <ScrollArea className="w-full whitespace-nowrap">
        <TabsList>
          {chips.map((chip) => (
            <TabsTrigger key={chip.value} value={chip.value}>
              {chip.label}
              {chip.count !== undefined && chip.count > 0 && (
                <span className="tabular-nums text-muted-foreground">
                  {chip.count}
                </span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>
    </Tabs>
  )
}
