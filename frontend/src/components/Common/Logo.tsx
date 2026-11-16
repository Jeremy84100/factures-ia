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
        "flex items-center gap-2 font-semibold tracking-tight",
        variant === "full" && "text-lg",
        className,
      )}
    >
      <ScanText className="size-5 shrink-0 text-primary" />
      {variant !== "icon" && (
        <span
          className={cn(
            variant === "responsive" && "group-data-[collapsible=icon]:hidden",
          )}
        >
          Factures IA
        </span>
      )}
    </span>
  )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
