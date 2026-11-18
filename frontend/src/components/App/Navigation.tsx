import { Link, useNavigate, useRouterState } from "@tanstack/react-router"
import {
  ChevronsUpDown,
  CircleUser,
  House,
  LogOut,
  type LucideIcon,
  Monitor,
  Moon,
  ScanText,
  Settings,
  ShoppingBag,
  Sun,
  Upload,
  Users,
} from "lucide-react"
import { useTheme } from "next-themes"

import { useFilePicker } from "@/components/App/UploadButton"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import { Spinner } from "@/components/ui/spinner"
import useAuth from "@/hooks/useAuth"
import { DEMO_DOMAIN } from "@/lib/queries"
import { getInitials } from "@/utils"

type Path = "/" | "/documents" | "/reconciliations"

// Three places only: what to pay, the purchases, the account. Documents are
// reached from the purchases, where they are used.
const NAV: { to: Path; label: string; icon: LucideIcon }[] = [
  { to: "/", label: "Accueil", icon: House },
  { to: "/reconciliations", label: "Achats", icon: ShoppingBag },
]

export const TITLES: Record<string, string> = {
  "/": "Accueil",
  "/documents": "Documents",
  "/reconciliations": "Achats",
  "/settings": "Mon compte",
  "/admin": "Utilisateurs",
}

const THEMES = [
  { value: "light", label: "Clair", icon: Sun },
  { value: "dark", label: "Sombre", icon: Moon },
  { value: "system", label: "Comme l'appareil", icon: Monitor },
]

export function displayName(user?: {
  full_name?: string | null
  email: string
}) {
  if (!user) return ""
  return user.full_name || user.email.split("@")[0]
}

export const isDemoUser = (user?: { email: string } | null) =>
  !!user?.email.endsWith(DEMO_DOMAIN)

// Theme, account and logout: shared by the sidebar (computer) and the
// "Compte" tab (phone).
function AccountMenuItems() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const { setOpenMobile } = useSidebar()
  return (
    <>
      <DropdownMenuLabel>Apparence</DropdownMenuLabel>
      <DropdownMenuRadioGroup value={theme} onValueChange={setTheme}>
        {THEMES.map(({ value, label, icon: Icon }) => (
          <DropdownMenuRadioItem key={value} value={value}>
            <Icon />
            {label}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
      <DropdownMenuSeparator />
      <DropdownMenuGroup>
        <DropdownMenuItem asChild>
          <Link to="/settings" onClick={() => setOpenMobile(false)}>
            <Settings />
            Mon compte
          </Link>
        </DropdownMenuItem>
        {user?.is_superuser && (
          <DropdownMenuItem asChild>
            <Link to="/admin" onClick={() => setOpenMobile(false)}>
              <Users />
              Utilisateurs
            </Link>
          </DropdownMenuItem>
        )}
      </DropdownMenuGroup>
      <DropdownMenuSeparator />
      <DropdownMenuItem onClick={logout}>
        <LogOut />
        Se déconnecter
      </DropdownMenuItem>
    </>
  )
}

function NavUser() {
  const { user } = useAuth()
  const { isMobile } = useSidebar()
  const name = displayName(user ?? undefined)
  const subtitle = isDemoUser(user) ? "Compte de démonstration" : user?.email

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" data-testid="user-menu">
              <Avatar>
                <AvatarFallback>{getInitials(name || "?")}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{name}</span>
                <span className="truncate text-xs">{subtitle}</span>
              </div>
              <ChevronsUpDown className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={isMobile ? "bottom" : "right"}
            align="end"
            className="min-w-56"
          >
            <AccountMenuItems />
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

function UploadMenuItem() {
  const { picker, open, isPending } = useFilePicker()
  return (
    <SidebarMenuItem>
      {picker}
      {/* The one action of the app, in the primary colour, like the
          "Quick Create" button of the shadcn dashboard. */}
      <SidebarMenuButton
        onClick={open}
        disabled={isPending}
        tooltip="Ajouter des documents"
        className="min-w-8 bg-primary text-primary-foreground duration-200 ease-linear hover:bg-primary/90 hover:text-primary-foreground active:bg-primary/90 active:text-primary-foreground"
      >
        {isPending ? <Spinner /> : <Upload />}
        <span>{isPending ? "Envoi…" : "Ajouter des documents"}</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { setOpenMobile } = useSidebar()

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/" onClick={() => setOpenMobile(false)}>
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <ScanText className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">Factures IA</span>
                  <span className="truncate text-xs">
                    Commande, livraison, facture
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent className="flex flex-col gap-2">
            <SidebarMenu>
              <UploadMenuItem />
            </SidebarMenu>
            <SidebarMenu>
              {NAV.map(({ to, label, icon: Icon }) => (
                <SidebarMenuItem key={to}>
                  <SidebarMenuButton
                    asChild
                    isActive={
                      to === "/" ? pathname === "/" : pathname.startsWith(to)
                    }
                    tooltip={label}
                  >
                    <Link to={to} onClick={() => setOpenMobile(false)}>
                      <Icon />
                      <span>{label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

export function DemoBanner() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!isDemoUser(user)) return null
  return (
    <Alert>
      <AlertTitle>Vous êtes dans la démo</AlertTitle>
      <AlertDescription>
        Des exemples déjà lus, visibles par vous seul.{" "}
        <Button
          variant="link"
          size="sm"
          className="h-auto p-0"
          onClick={() => {
            logout()
            navigate({ to: "/signup" })
          }}
        >
          Créer mon compte
        </Button>
      </AlertDescription>
    </Alert>
  )
}

// Phone navigation: tabs at the bottom, within reach of the thumb.
export function TabBar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const isActive = (to: Path) =>
    to === "/"
      ? pathname === "/"
      : pathname.startsWith(to) ||
        (to === "/reconciliations" && pathname.startsWith("/documents"))
  const tab = (active: boolean) =>
    active
      ? "h-auto flex-1 flex-col gap-0.5 rounded-full bg-muted py-1.5 text-xs"
      : "h-auto flex-1 flex-col gap-0.5 rounded-full py-1.5 text-xs text-muted-foreground"
  return (
    <nav className="fixed inset-x-4 bottom-[max(1rem,env(safe-area-inset-bottom))] z-40 flex gap-1 rounded-full border bg-background/90 p-1.5 shadow-lg backdrop-blur md:hidden">
      {NAV.map(({ to, label, icon: Icon }) => (
        <Button key={to} variant="ghost" className={tab(isActive(to))} asChild>
          <Link to={to} aria-current={isActive(to) ? "page" : undefined}>
            <Icon className="size-5" />
            {label}
          </Link>
        </Button>
      ))}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className={tab(pathname.startsWith("/settings"))}
            data-testid="account-tab"
          >
            <CircleUser className="size-5" />
            Compte
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="end" className="min-w-56">
          <AccountMenuItems />
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
  )
}
