import { Link, useNavigate, useRouterState } from "@tanstack/react-router"
import {
  ChevronsUpDown,
  FileText,
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
import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert"
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

const NAV: { to: Path; label: string; icon: LucideIcon }[] = [
  { to: "/", label: "Accueil", icon: House },
  { to: "/documents", label: "Documents", icon: FileText },
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

function NavUser() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const { isMobile, setOpenMobile } = useSidebar()
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
      <SidebarMenuButton
        onClick={open}
        disabled={isPending}
        tooltip="Ajouter des documents"
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
    <Sidebar collapsible="icon">
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
          <SidebarGroupContent>
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
              <UploadMenuItem />
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
      <AlertTitle>Démo</AlertTitle>
      <AlertDescription>
        Des exemples déjà lus. Ce que vous déposez reste privé.
      </AlertDescription>
      <AlertAction>
        <Button
          size="sm"
          onClick={() => {
            logout()
            navigate({ to: "/signup" })
          }}
        >
          Créer mon compte
        </Button>
      </AlertAction>
    </Alert>
  )
}
