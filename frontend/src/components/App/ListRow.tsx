import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Card } from "@/components/ui/card"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item"
import { Spinner } from "@/components/ui/spinner"
import { TONE_CLASSES, type Tone } from "@/lib/documents"
import { cn } from "@/lib/utils"

export function IconBubble({
  icon: Icon,
  tone = "neutral",
  className,
  spin = false,
}: {
  icon: LucideIcon
  tone?: Tone
  className?: string
  spin?: boolean
}) {
  return (
    <span
      className={cn(
        "flex size-10 shrink-0 items-center justify-center rounded-full",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {spin ? (
        <Spinner className="size-[18px]" />
      ) : (
        <Icon className="size-[18px]" />
      )}
    </span>
  )
}

interface ListRowProps {
  icon: LucideIcon
  tone?: Tone
  spin?: boolean
  title: ReactNode
  subtitle?: ReactNode
  end?: ReactNode
  endSub?: ReactNode
  onClick?: () => void
}

// One row of a list, built on shadcn's Item: round icon, title, subtitle,
// amount on the right.
export function ListRow({
  icon,
  tone,
  spin,
  title,
  subtitle,
  end,
  endSub,
  onClick,
}: ListRowProps) {
  const body = (
    <>
      <ItemMedia>
        <IconBubble icon={icon} tone={tone} spin={spin} />
      </ItemMedia>
      <ItemContent className="min-w-0 gap-0.5">
        <ItemTitle className="block w-full truncate text-[15px]">
          {title}
        </ItemTitle>
        {subtitle && (
          <ItemDescription className="line-clamp-1">{subtitle}</ItemDescription>
        )}
      </ItemContent>
      {(end || endSub) && (
        <ItemActions className="flex-col items-end gap-0.5 text-sm">
          {end && (
            <span className="text-[15px] font-medium tabular-nums">{end}</span>
          )}
          {endSub}
        </ItemActions>
      )}
    </>
  )

  if (!onClick) {
    return (
      <Item size="sm" role="listitem" className="flex-nowrap">
        {body}
      </Item>
    )
  }
  return (
    <Item
      asChild
      size="sm"
      role="listitem"
      className="flex-nowrap text-left hover:bg-muted/70 active:bg-muted"
    >
      <button type="button" onClick={onClick}>
        {body}
      </button>
    </Item>
  )
}

export function ListGroup({
  title,
  action,
  children,
  className,
}: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn("flex flex-col gap-2", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between px-2">
          {title && (
            <h2 className="text-sm font-medium text-muted-foreground">
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      <Card className="gap-0 p-1.5">
        <ItemGroup className="gap-0">{children}</ItemGroup>
      </Card>
    </section>
  )
}
