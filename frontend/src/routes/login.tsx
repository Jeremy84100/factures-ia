import { zodResolver } from "@hookform/resolvers/zod"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import {
  ArrowRight,
  Camera,
  GitCompareArrows,
  Loader2,
  ShieldCheck,
} from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { Body_login_login_access_token as AccessToken } from "@/client"
import { IconBubble } from "@/components/App/ListRow"
import { Logo } from "@/components/Common/Logo"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { PasswordInput } from "@/components/ui/password-input"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"

const formSchema = z.object({
  username: z.email({ message: "Adresse e-mail invalide" }),
  password: z
    .string()
    .min(1, { message: "Mot de passe obligatoire" })
    .min(8, { message: "8 caractères minimum" }),
}) satisfies z.ZodType<AccessToken>

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/login")({
  component: Login,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({ to: "/" })
    }
  },
  head: () => ({
    meta: [{ title: "Factures IA · Ne payez que ce que vous avez reçu" }],
  }),
})

const STEPS = [
  {
    icon: Camera,
    title: "Déposez tout en vrac",
    text: "Commandes, bons de livraison, factures. En PDF ou en photo.",
  },
  {
    icon: GitCompareArrows,
    title: "L'IA compare ligne par ligne",
    text: "Quantités, prix, articles, mode et date de livraison.",
  },
  {
    icon: ShieldCheck,
    title: "Vous savez quoi payer",
    text: "Bon à payer, litige ou en attente, avec la raison en clair.",
  },
]

function DemoButton() {
  const { demoMutation } = useAuth()
  return (
    <div className="flex flex-col gap-2">
      <Button
        size="lg"
        className="h-14 w-full rounded-full text-base sm:w-auto sm:px-8"
        disabled={demoMutation.isPending}
        onClick={() => demoMutation.mutate()}
        data-testid="demo-button"
      >
        {demoMutation.isPending ? (
          <>
            <Loader2 className="animate-spin" />
            Préparation de la démo…
          </>
        ) : (
          <>
            Essayer la démo
            <ArrowRight />
          </>
        )}
      </Button>
      <p className="text-sm text-muted-foreground">
        Sans inscription · 10 achats d'exemple déjà lus
      </p>
    </div>
  )
}

function LoginForm() {
  const { loginMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { username: "", password: "" },
  })

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((data) => {
          if (!loginMutation.isPending) loginMutation.mutate(data)
        })}
        className="flex flex-col gap-4"
      >
        <h2 className="text-lg font-semibold">Déjà un compte ?</h2>
        <FormField
          control={form.control}
          name="username"
          render={({ field }) => (
            <FormItem>
              <FormLabel>E-mail</FormLabel>
              <FormControl>
                <Input
                  data-testid="email-input"
                  placeholder="vous@exemple.fr"
                  type="email"
                  autoComplete="email"
                  className="h-12 rounded-xl"
                  {...field}
                />
              </FormControl>
              <FormMessage className="text-xs" />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <div className="flex items-center">
                <FormLabel>Mot de passe</FormLabel>
                <RouterLink
                  to="/recover-password"
                  className="ml-auto text-sm text-muted-foreground hover:text-foreground"
                >
                  Oublié ?
                </RouterLink>
              </div>
              <FormControl>
                <PasswordInput
                  data-testid="password-input"
                  placeholder="Mot de passe"
                  autoComplete="current-password"
                  className="h-12 rounded-xl"
                  {...field}
                />
              </FormControl>
              <FormMessage className="text-xs" />
            </FormItem>
          )}
        />
        <LoadingButton
          type="submit"
          variant="secondary"
          className="h-12 rounded-full"
          loading={loginMutation.isPending}
        >
          Se connecter
        </LoadingButton>
        <p className="text-center text-sm text-muted-foreground">
          Pas encore de compte ?{" "}
          <RouterLink to="/signup" className="font-medium text-foreground">
            S'inscrire
          </RouterLink>
        </p>
      </form>
    </Form>
  )
}

function Login() {
  return (
    <div className="mx-auto flex min-h-svh max-w-6xl flex-col px-5 pt-[max(1.25rem,env(safe-area-inset-top))] pb-10 md:px-10">
      <header className="flex items-center justify-between">
        <Logo asLink={false} />
      </header>

      <div className="grid flex-1 items-center gap-14 py-10 md:grid-cols-[1.2fr_1fr] md:gap-20 md:py-16">
        <section className="flex flex-col gap-8">
          <div className="flex flex-col gap-4">
            <h1 className="text-[40px] leading-[1.05] font-semibold md:text-6xl">
              Ne payez que ce que vous avez reçu.
            </h1>
            <p className="max-w-xl text-lg text-muted-foreground">
              Déposez vos bons de commande, bons de livraison et factures. L'IA
              les lit, les compare ligne par ligne et vous dit quoi payer.
            </p>
          </div>
          <DemoButton />
          <ul className="flex flex-col gap-5">
            {STEPS.map(({ icon, title, text }) => (
              <li key={title} className="flex items-start gap-4">
                <IconBubble
                  icon={icon}
                  className="bg-primary/10 text-primary"
                />
                <span className="flex flex-col">
                  <span className="font-medium">{title}</span>
                  <span className="text-muted-foreground">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-3xl bg-surface p-6 md:p-8">
          <LoginForm />
        </section>
      </div>
    </div>
  )
}
