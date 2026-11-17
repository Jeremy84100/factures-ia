import { Link } from "@tanstack/react-router"
import { ScanText } from "lucide-react"

interface LogoProps {
  asLink?: boolean
}

// Same mark as the sidebar header.
export function Logo({ asLink = true }: LogoProps) {
  const content = (
    <span className="flex items-center gap-2 font-medium">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <ScanText className="size-4" />
      </span>
      Factures IA
    </span>
  )
  if (!asLink) return content
  return <Link to="/">{content}</Link>
}
