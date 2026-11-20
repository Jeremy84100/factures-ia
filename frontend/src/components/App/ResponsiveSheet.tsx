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
import { ScrollArea } from "@/components/ui/scroll-area"
import { useIsMobile } from "@/hooks/useMobile"

interface ResponsiveSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  wide?: boolean
}

// shadcn's responsive dialog: a Drawer on a phone, a Dialog on a computer.
// Opening by touch does not put a focus ring on the first row.
export function ResponsiveSheet({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide = false,
}: ResponsiveSheetProps) {
  const isMobile = useIsMobile()
  const ignoreToast = (event: {
    target: EventTarget | null
    preventDefault: () => void
  }) => {
    if (
      event.target instanceof HTMLElement &&
      event.target.closest("[data-sonner-toaster]")
    )
      event.preventDefault()
  }

  if (isMobile) {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent
          onOpenAutoFocus={(event) => event.preventDefault()}
          onPointerDownOutside={ignoreToast}
          onInteractOutside={ignoreToast}
        >
          <DrawerHeader className="pb-0 group-data-[vaul-drawer-direction=bottom]/drawer-content:text-left">
            <DrawerTitle>{title}</DrawerTitle>
            {description && (
              <DrawerDescription>{description}</DrawerDescription>
            )}
          </DrawerHeader>
          <div className="overflow-y-auto p-4">{children}</div>
        </DrawerContent>
      </Drawer>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        onOpenAutoFocus={(event) => event.preventDefault()}
        onPointerDownOutside={ignoreToast}
        onInteractOutside={ignoreToast}
        className={wide ? "sm:max-w-4xl" : "sm:max-w-lg"}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {/* shadcn ScrollArea: a thin bar that shows only while scrolling,
            instead of the browser's grey one. */}
        <ScrollArea className="-mx-6 **:data-[slot=scroll-area-viewport]:max-h-[calc(90vh-9rem)]">
          <div className="px-6 py-1">{children}</div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
