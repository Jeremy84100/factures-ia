import type { QueryClient } from "@tanstack/react-query"
import {
  createRootRouteWithContext,
  HeadContent,
  Outlet,
} from "@tanstack/react-router"
import ErrorComponent from "@/components/Common/ErrorComponent"
import NotFound from "@/components/Common/NotFound"

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()(
  {
    component: () => (
      <>
        <HeadContent />
        <Outlet />
      </>
    ),
    notFoundComponent: () => <NotFound />,
    errorComponent: () => <ErrorComponent />,
  },
)
