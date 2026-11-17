import type { ReactNode } from "react"

import { Logo } from "@/components/Common/Logo"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

// shadcn's login block: a centred Card with header, form and footer.
export function AuthLayout({
  title,
  description,
  footer,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  footer?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 p-6 md:p-10">
      <Logo />
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>{children}</CardContent>
        {footer && (
          <CardFooter className="flex-col gap-3 text-sm text-muted-foreground">
            {footer}
          </CardFooter>
        )}
      </Card>
    </div>
  )
}
