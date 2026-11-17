import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

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
  actions?: ReactNode
  onClick?: () => void
}

// shadcn Item, used as in its examples: outline variant, icon media,
// title and description, actions on the right.
export function ListRow({
  icon: Icon,
  spin,
  title,
  subtitle,
  actions,
  onClick,
}: ListRowProps) {
  const body = (
    <>
      <ItemMedia variant="icon">{spin ? <Spinner /> : <Icon />}</ItemMedia>
      <ItemContent>
        <ItemTitle>{title}</ItemTitle>
        {subtitle && <ItemDescription>{subtitle}</ItemDescription>}
      </ItemContent>
      {actions && <ItemActions>{actions}</ItemActions>}
    </>
  )
  if (!onClick) return <Item variant="outline">{body}</Item>
  return (
    <Item variant="outline" asChild>
      <button type="button" onClick={onClick} className="text-left">
        {body}
      </button>
    </Item>
  )
}

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
        <div className="flex items-center justify-between gap-2">
          {title && (
            <h2 className="text-sm font-medium text-muted-foreground">
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      <ItemGroup>{children}</ItemGroup>
    </section>
  )
}
