import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

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
      <Icon className={cn("size-[18px]", spin && "animate-spin")} />
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
  const content = (
    <>
      <IconBubble icon={icon} tone={tone} spin={spin} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate font-medium">{title}</span>
        {subtitle && (
          <span className="truncate text-sm text-muted-foreground">
            {subtitle}
          </span>
        )}
      </span>
      {(end || endSub) && (
        <span className="flex shrink-0 flex-col items-end">
          {end && <span className="font-medium tabular-nums">{end}</span>}
          {endSub && <span className="text-sm">{endSub}</span>}
        </span>
      )}
    </>
  )
  const base =
    "flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left md:px-4"
  if (!onClick) return <div className={base}>{content}</div>
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        base,
        "transition-colors hover:bg-muted/70 active:bg-muted focus-visible:outline-2",
      )}
    >
      {content}
    </button>
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
    <section className={cn("flex flex-col gap-1", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between px-1 pb-1">
          {title && (
            <h2 className="text-sm font-medium text-muted-foreground">
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      <div className="flex flex-col rounded-3xl bg-surface p-1.5">
        {children}
      </div>
    </section>
  )
}
