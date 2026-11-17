import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { client } from "./client/client.gen"
import { ThemeProvider } from "next-themes"
import { Toaster } from "./components/ui/sonner"
import { TooltipProvider } from "./components/ui/tooltip"
import "./index.css"
import { routeTree } from "./routeTree.gen"

client.setConfig({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  auth: () => localStorage.getItem("access_token") || "",
})

// A token that no longer works (expired, or demo account removed after 24 h)
// sends the visitor back to the home page instead of an error screen.
const isSessionGone = (error: Error) =>
  error instanceof AxiosError &&
  ([401, 403].includes(error.response?.status ?? 0) ||
    (error.response?.status === 404 &&
      (error.config?.url ?? "").endsWith("/users/me")))

const handleApiError = (error: Error) => {
  if (isSessionGone(error) && localStorage.getItem("access_token")) {
    localStorage.removeItem("access_token")
    queryClient.clear()
    router.navigate({ to: "/login", replace: true })
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, error) => !isSessionGone(error) && count < 2,
      refetchOnWindowFocus: false,
    },
  },
  queryCache: new QueryCache({ onError: handleApiError }),
  mutationCache: new MutationCache({ onError: handleApiError }),
})

// Pages load their data before showing (preloaded as soon as a finger or the
// mouse touches a link), so nothing appears empty then fills in.
const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
  defaultPreloadStaleTime: 0,
  defaultPendingMs: 400,
  defaultPendingMinMs: 300,
  scrollRestoration: true,
})

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      storageKey="vite-ui-theme"
    >
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <RouterProvider router={router} />
        </TooltipProvider>
        <Toaster position="top-center" />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
