import { ChevronRight, type LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
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

interface ListRowProps {
  icon: LucideIcon
  spin?: boolean
  title: ReactNode
  subtitle?: ReactNode
  /** Right side, first line: usually an amount. */
  value?: ReactNode
  /** Right side, second line: a short status. */
  meta?: ReactNode
  /** Draws the status in red. */
  alert?: boolean
  /** Shows a chevron when there is no value on the right. */
  chevron?: boolean
  /** Lets the detail run on several lines (explanations, not lists). */
  wrap?: boolean
  onClick?: () => void
  onPrefetch?: () => void
}

// A banking-app row: round icon, name and one line of detail on the left,
// amount and status on the right. Long names are cut; the detail keeps two lines.
export function ListRow({
  icon: Icon,
  spin,
  title,
  subtitle,
  value,
  meta,
  alert,
  chevron,
  wrap,
  onClick,
  onPrefetch,
}: ListRowProps) {
  const body = (
    <>
      <ItemMedia>
        <Avatar size="lg">
          <AvatarFallback>{spin ? <Spinner /> : <Icon />}</AvatarFallback>
        </Avatar>
      </ItemMedia>
      <ItemContent className="min-w-0">
        <ItemTitle className="block w-full truncate">{title}</ItemTitle>
        {subtitle && (
          <ItemDescription className={wrap ? "line-clamp-none" : undefined}>
            {subtitle}
          </ItemDescription>
        )}
      </ItemContent>
      {(value || meta) && (
        <ItemActions className="flex-col items-end gap-1 text-right">
          {value && (
            <span className="text-sm font-medium tabular-nums">{value}</span>
          )}
          {meta && (
            <span
              className={
                alert
                  ? "text-sm text-destructive"
                  : "text-sm text-muted-foreground"
              }
            >
              {meta}
            </span>
          )}
        </ItemActions>
      )}
      {chevron && (
        <ItemActions className="text-muted-foreground">
          <ChevronRight />
        </ItemActions>
      )}
    </>
  )
  if (!onClick) return <Item className="flex-nowrap">{body}</Item>
  return (
    <Item asChild className="flex-nowrap transition-colors active:bg-muted">
      <button
        type="button"
        onClick={onClick}
        onPointerEnter={onPrefetch}
        onFocus={onPrefetch}
        className="text-left"
      >
        {body}
      </button>
    </Item>
  )
}

// One rounded block holding all the rows, like the transaction list of a
// banking app, instead of one frame per row.
export function ListGroup({
  title,
  action,
  children,
}: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="flex flex-col gap-3">
      {(title || action) && (
        <div className="flex items-center justify-between gap-2 px-1">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {action}
        </div>
      )}
      <Card size="sm" className="gap-0 py-1.5">
        <ItemGroup className="gap-0">{children}</ItemGroup>
      </Card>
    </section>
  )
}
