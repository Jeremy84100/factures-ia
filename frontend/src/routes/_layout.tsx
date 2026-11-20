import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"
import { AxiosError } from "axios"
import { Upload } from "lucide-react"
import { useEffect, useEffectEvent, useState } from "react"

import { AppSidebar, TabBar, TITLES } from "@/components/App/Navigation"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"
import { useUpload } from "@/hooks/useUpload"
import { currentUserQuery } from "@/lib/queries"

export const Route = createFileRoute("/_layout")({
  beforeLoad: () => {
    if (!isLoggedIn()) throw redirect({ to: "/login" })
  },
  // The account is known before the first paint: the name and the demo banner
  // are there at once instead of popping in.
  loader: async ({ context }) => {
    try {
      await context.queryClient.ensureQueryData(currentUserQuery)
    } catch (error) {
      if (error instanceof AxiosError && error.response) {
        localStorage.removeItem("access_token")
        throw redirect({ to: "/login" })
      }
      throw error
    }
  },
  component: Layout,
})

function hasFiles(event: DragEvent) {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files")
}

// Files can be dropped anywhere in the app from a computer.
function GlobalDropZone() {
  const { upload } = useUpload()
  const onFiles = useEffectEvent(upload)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    let depth = 0
    const reset = () => {
      depth = 0
      setDragging(false)
    }
    const onDragEnter = (event: DragEvent) => {
      if (!hasFiles(event)) return
      event.preventDefault()
      depth += 1
      setDragging(true)
    }
    const onDragOver = (event: DragEvent) => {
      if (!hasFiles(event)) return
      event.preventDefault()
    }
    const onDragLeave = (event: DragEvent) => {
      if (!hasFiles(event)) return
      depth = Math.max(0, depth - 1)
      if (depth === 0) setDragging(false)
    }
    const onDrop = (event: DragEvent) => {
      if (!hasFiles(event)) return
      event.preventDefault()
      reset()
      onFiles(Array.from(event.dataTransfer?.files ?? []))
    }

    window.addEventListener("dragenter", onDragEnter)
    window.addEventListener("dragover", onDragOver)
    window.addEventListener("dragleave", onDragLeave)
    window.addEventListener("drop", onDrop)
    window.addEventListener("blur", reset)
    return () => {
      window.removeEventListener("dragenter", onDragEnter)
      window.removeEventListener("dragover", onDragOver)
      window.removeEventListener("dragleave", onDragLeave)
      window.removeEventListener("drop", onDrop)
      window.removeEventListener("blur", reset)
    }
  }, [])

  if (!dragging) return null
  return (
    <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-6 backdrop-blur-xs">
      <div className="flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-primary bg-card px-10 py-8 text-center shadow-lg">
        <Upload className="size-8 text-primary" />
        <p className="text-base font-semibold">Déposez vos documents ici</p>
        <p className="text-sm text-muted-foreground">
          Commandes, bons de livraison et factures (PDF ou photo)
        </p>
      </div>
    </div>
  )
}

function Layout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  return (
    <SidebarProvider>
      <GlobalDropZone />
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 bg-background px-4 md:static md:h-14 md:rounded-t-2xl md:border-b">
          <div className="hidden items-center gap-2 md:flex">
            <SidebarTrigger className="-ml-1" />
            <Separator
              orientation="vertical"
              className="mr-2 data-vertical:h-4 data-vertical:self-auto"
            />
          </div>
          <h1 className="text-lg font-semibold md:text-sm md:font-medium">
            {TITLES[pathname] ?? ""}
          </h1>
        </header>
        <div className="flex flex-1 flex-col gap-6 px-4 pt-2 pb-32 md:p-8">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
            <Outlet />
          </div>
        </div>
        <TabBar />
      </SidebarInset>
    </SidebarProvider>
  )
}
