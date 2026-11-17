import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"
import { AxiosError } from "axios"

import { AppSidebar, TabBar, TITLES } from "@/components/App/Navigation"
import { UploadButton } from "@/components/App/UploadButton"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"
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

function Layout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 bg-background px-4 md:h-16 md:border-b">
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
          <UploadButton size="sm" className="ml-auto">
            Ajouter
          </UploadButton>
        </header>
        <div className="flex flex-1 flex-col gap-6 px-4 pt-2 pb-28 md:p-8">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
            <Outlet />
          </div>
        </div>
        <TabBar />
      </SidebarInset>
    </SidebarProvider>
  )
}
