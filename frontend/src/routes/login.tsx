import { zodResolver } from "@hookform/resolvers/zod"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { ArrowRight, Camera, GitCompareArrows, ShieldCheck } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { Body_login_login_access_token as AccessToken } from "@/client"
import {
  PasswordField,
  SubmitButton,
  TextField,
} from "@/components/App/FormFields"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { Logo } from "@/components/Common/Logo"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
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
    <div className="flex flex-col items-start gap-2">
      <Button
        size="lg"
        disabled={demoMutation.isPending}
        onClick={() => demoMutation.mutate()}
        data-testid="demo-button"
      >
        {demoMutation.isPending ? (
          <>
            <Spinner data-icon="inline-start" />
            Préparation de la démo…
          </>
        ) : (
          <>
            Essayer la démo
            <ArrowRight data-icon="inline-end" />
          </>
        )}
      </Button>
      <p className="text-sm text-muted-foreground">
        Sans inscription · 10 achats d'exemple déjà lus
      </p>
    </div>
  )
}

function LoginCard() {
  const { loginMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    defaultValues: { username: "", password: "" },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Déjà un compte ?</CardTitle>
        <CardDescription>Connectez-vous avec votre e-mail.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          id="login-form"
          onSubmit={form.handleSubmit((data) => {
            if (!loginMutation.isPending) loginMutation.mutate(data)
          })}
        >
          <FieldGroup>
            <TextField
              control={form.control}
              name="username"
              label="E-mail"
              type="email"
              autoComplete="email"
              placeholder="vous@exemple.fr"
              data-testid="email-input"
            />
            <PasswordField
              control={form.control}
              name="password"
              label="Mot de passe"
              autoComplete="current-password"
              placeholder="Mot de passe"
              data-testid="password-input"
              labelEnd={
                <Button variant="link" size="xs" asChild>
                  <RouterLink to="/recover-password">Oublié ?</RouterLink>
                </Button>
              }
            />
          </FieldGroup>
        </form>
      </CardContent>
      <CardFooter className="flex-col gap-3">
        <SubmitButton
          form="login-form"
          variant="secondary"
          className="w-full"
          pending={loginMutation.isPending}
        >
          Se connecter
        </SubmitButton>
        <p className="text-sm text-muted-foreground">
          Pas encore de compte ?{" "}
          <Button variant="link" size="xs" asChild>
            <RouterLink to="/signup">S'inscrire</RouterLink>
          </Button>
        </p>
      </CardFooter>
    </Card>
  )
}

function Login() {
  return (
    <div className="mx-auto flex min-h-svh max-w-6xl flex-col gap-10 p-6 md:p-10">
      <Logo asLink={false} />
      <div className="grid flex-1 items-center gap-10 md:grid-cols-[1.2fr_1fr] md:gap-16">
        <section className="flex flex-col gap-8">
          <div className="flex flex-col gap-4">
            <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">
              Ne payez que ce que vous avez reçu.
            </h1>
            <p className="max-w-xl text-lg text-muted-foreground">
              Déposez vos bons de commande, bons de livraison et factures. L'IA
              les lit, les compare ligne par ligne et vous dit quoi payer.
            </p>
          </div>
          <DemoButton />
          <ListGroup>
            {STEPS.map(({ icon, title, text }) => (
              <ListRow
                key={title}
                icon={icon}
                title={title}
                subtitle={text}
                wrap
              />
            ))}
          </ListGroup>
        </section>
        <LoginCard />
      </div>
    </div>
  )
}
