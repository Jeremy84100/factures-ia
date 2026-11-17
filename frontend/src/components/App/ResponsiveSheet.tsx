import type { ReactNode } from "react"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer"
import { useIsMobile } from "@/hooks/useMobile"
import { cn } from "@/lib/utils"

interface ResponsiveSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  wide?: boolean
}

// Slides up from the bottom on a phone, opens as a window on a computer.
export function ResponsiveSheet({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide = false,
}: ResponsiveSheetProps) {
  const isMobile = useIsMobile()

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent className="max-h-[92svh] rounded-t-3xl border-none bg-background">
          <DrawerHeader className="px-5 pt-3 pb-2 text-left">
            <DrawerTitle className="text-xl font-semibold">{title}</DrawerTitle>
            {description && (
              <DrawerDescription>{description}</DrawerDescription>
            )}
          </DrawerHeader>
          <div className="overflow-y-auto px-5 pb-[calc(2rem+env(safe-area-inset-bottom))]">
            {children}
          </div>
        </DrawerContent>
      </Drawer>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "max-h-[88vh] gap-0 overflow-y-auto rounded-3xl border-none bg-background p-0",
          wide ? "sm:max-w-4xl" : "sm:max-w-2xl",
        )}
      >
        <DialogHeader className="px-7 pt-7 pb-3">
          <DialogTitle className="text-2xl font-semibold">{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="px-7 pb-7">{children}</div>
      </DialogContent>
    </Dialog>
  )
}
