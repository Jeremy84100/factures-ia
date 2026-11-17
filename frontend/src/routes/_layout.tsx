import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { AxiosError } from "axios"

import {
  BottomNav,
  DemoBanner,
  MobileTopBar,
  SideNav,
} from "@/components/App/Navigation"
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
  return (
    <div className="min-h-svh md:flex">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileTopBar />
        <DemoBanner />
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 pt-3 pb-[calc(7rem+env(safe-area-inset-bottom))] md:px-10 md:pt-8 md:pb-16">
          <Outlet />
        </main>
      </div>
      <BottomNav />
    </div>
  )
}
