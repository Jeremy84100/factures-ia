import { Logo } from "@/components/Common/Logo"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="flex min-h-svh flex-col px-5 pt-[max(1.25rem,env(safe-area-inset-top))] pb-8">
      <Logo />
      <div className="flex flex-1 items-center justify-center py-10">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  )
}
