import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

// Round buttons with a label underneath, as under the balance of a banking app.
export function QuickAction({
  icon: Icon,
  label,
  onClick,
  disabled,
  pending,
  destructive,
}: {
  icon: LucideIcon
  label: string
  onClick: () => void
  disabled?: boolean
  pending?: boolean
  destructive?: boolean
}) {
  return (
    <div className="flex w-20 flex-col items-center gap-2">
      <Button
        variant={destructive ? "destructive" : "secondary"}
        size="icon-lg"
        aria-label={label}
        onClick={onClick}
        disabled={disabled || pending}
        className="transition-transform active:scale-95"
      >
        {pending ? <Spinner /> : <Icon />}
      </Button>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

export function QuickActions({ children }: { children: ReactNode }) {
  return <div className="flex justify-center gap-2">{children}</div>
}

// A large amount, euros bigger than cents.
export function BigAmount({
  text,
  size = "lg",
}: {
  text: string
  size?: "lg" | "md"
}) {
  const comma = text.indexOf(",")
  const [main, small] =
    size === "lg" ? ["text-5xl", "text-3xl"] : ["text-4xl", "text-2xl"]
  return (
    <p className={`${main} font-semibold tracking-tight tabular-nums`}>
      {comma < 0 ? (
        text
      ) : (
        <>
          {text.slice(0, comma)}
          <span className={small}>{text.slice(comma)}</span>
        </>
      )}
    </p>
  )
}
