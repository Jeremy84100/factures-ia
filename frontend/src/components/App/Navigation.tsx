import { Link, useNavigate } from "@tanstack/react-router"
import {
  CircleUserRound,
  FileText,
  House,
  LogOut,
  type LucideIcon,
  Monitor,
  Moon,
  Settings,
  ShoppingBag,
  Sun,
  Users,
} from "lucide-react"

import { Logo } from "@/components/Common/Logo"
import { type Theme, useTheme } from "@/components/theme-provider"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import { DEMO_DOMAIN } from "@/lib/queries"
import { cn } from "@/lib/utils"
import { getInitials } from "@/utils"
import { UploadButton, UploadFab } from "./UploadButton"

interface NavItem {
  to: "/" | "/documents" | "/reconciliations" | "/settings"
  label: string
  icon: LucideIcon
}

const NAV: NavItem[] = [
  { to: "/", label: "Accueil", icon: House },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/reconciliations", label: "Achats", icon: ShoppingBag },
]

export const THEMES: { value: Theme; label: string; icon: LucideIcon }[] = [
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

function UserMenu({ compact = false }: { compact?: boolean }) {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const name = displayName(user ?? undefined)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          data-testid="user-menu"
          aria-label="Mon compte"
          className={cn(
            "flex items-center gap-3 rounded-2xl text-left transition-colors hover:bg-muted/70",
            compact ? "p-1" : "w-full p-2",
          )}
        >
          <Avatar className="size-9">
            <AvatarFallback className="bg-primary/12 text-sm font-medium text-primary">
              {getInitials(name || "?")}
            </AvatarFallback>
          </Avatar>
          {!compact && (
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-medium">{name}</span>
              <span className="truncate text-xs text-muted-foreground">
                {isDemoUser(user) ? "Compte de démonstration" : user?.email}
              </span>
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={compact ? "end" : "start"}
        side={compact ? "bottom" : "top"}
        className="w-60 rounded-2xl p-1.5"
      >
        <DropdownMenuLabel className="font-normal text-muted-foreground">
          Apparence
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={theme}
          onValueChange={(value) => setTheme(value as Theme)}
        >
          {THEMES.map(({ value, label, icon: Icon }) => (
            <DropdownMenuRadioItem key={value} value={value} className="gap-2">
              <Icon className="size-4" />
              {label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/settings">
            <Settings />
            Mon compte
          </Link>
        </DropdownMenuItem>
        {user?.is_superuser && (
          <DropdownMenuItem asChild>
            <Link to="/admin">
              <Users />
              Utilisateurs
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={logout}>
          <LogOut />
          Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function SideNav() {
  return (
    <aside className="sticky top-0 hidden h-svh w-64 shrink-0 flex-col gap-8 px-4 py-6 md:flex">
      <div className="px-2">
        <Logo />
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            activeOptions={{ exact: to === "/" }}
            className="flex h-11 items-center gap-3 rounded-2xl px-3 font-medium text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground data-[status=active]:bg-muted data-[status=active]:text-foreground"
          >
            <Icon className="size-5" />
            {label}
          </Link>
        ))}
      </nav>
      <UploadButton className="w-full" />
      <div className="mt-auto">
        <UserMenu />
      </div>
    </aside>
  )
}

export function MobileTopBar() {
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between bg-background/85 px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-2 backdrop-blur-xl md:hidden">
      <Logo />
      <UserMenu compact />
    </header>
  )
}

function TabLink({ to, label, icon: Icon }: NavItem) {
  return (
    <Link
      to={to}
      activeOptions={{ exact: to === "/" }}
      className="flex flex-1 flex-col items-center gap-1 py-2 text-[11px] font-medium text-muted-foreground transition-colors data-[status=active]:text-foreground"
    >
      <Icon className="size-6" />
      {label}
    </Link>
  )
}

export function BottomNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-border/60 bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden">
      <div className="mx-auto flex max-w-md items-start px-2">
        <TabLink {...NAV[0]} />
        <TabLink {...NAV[1]} />
        <div className="flex flex-1 justify-center">
          <UploadFab />
        </div>
        <TabLink {...NAV[2]} />
        <TabLink to="/settings" label="Compte" icon={CircleUserRound} />
      </div>
    </nav>
  )
}

export function DemoBanner() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!isDemoUser(user)) return null
  return (
    <div className="mx-4 mt-1 flex items-center justify-between gap-3 rounded-full bg-primary/10 py-2 pr-2 pl-4 text-sm md:mx-10 md:mt-6">
      <span className="min-w-0 truncate">
        <span className="font-medium text-primary">Démo</span>
        <span className="text-muted-foreground">
          {" "}
          · exemples déjà lus
          <span className="hidden sm:inline">
            , vos documents restent privés
          </span>
        </span>
      </span>
      <button
        type="button"
        className="shrink-0 rounded-full bg-primary px-3 py-1 font-medium text-primary-foreground"
        onClick={() => {
          logout()
          navigate({ to: "/signup" })
        }}
      >
        Créer mon compte
      </button>
    </div>
  )
}
