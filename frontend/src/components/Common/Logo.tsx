import { Link } from "@tanstack/react-router"
import { ScanText } from "lucide-react"

import { cn } from "@/lib/utils"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const content = (
    <span
      className={cn(
        "flex items-center gap-2.5 text-[17px] font-semibold tracking-tight",
        className,
      )}
    >
      <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
        <ScanText className="size-[18px]" />
      </span>
      {variant !== "icon" && <span>Factures IA</span>}
    </span>
  )

  if (!asLink) return content
  return <Link to="/">{content}</Link>
}
