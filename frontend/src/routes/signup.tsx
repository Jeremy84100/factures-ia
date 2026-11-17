import { zodResolver } from "@hookform/resolvers/zod"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"
import {
  PasswordField,
  SubmitButton,
  TextField,
} from "@/components/App/FormFields"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import useAuth, { isLoggedIn } from "@/hooks/useAuth"

const formSchema = z
  .object({
    email: z.email({ message: "Adresse e-mail invalide" }),
    full_name: z.string().min(1, { message: "Nom obligatoire" }),
    password: z
      .string()
      .min(1, { message: "Mot de passe obligatoire" })
      .min(8, { message: "8 caractères minimum" }),
    confirm_password: z
      .string()
      .min(1, { message: "Confirmez le mot de passe" }),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/signup")({
  component: SignUp,
  beforeLoad: async () => {
    if (isLoggedIn()) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Inscription - Factures IA",
      },
    ],
  }),
})

function SignUp() {
  const { signUpMutation } = useAuth()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
    },
  })

  const onSubmit = (data: FormData) => {
    if (signUpMutation.isPending) return

    // exclude confirm_password from submission data
    const { confirm_password: _confirm_password, ...submitData } = data
    signUpMutation.mutate(submitData)
  }

  return (
    <AuthLayout
      title="Créer un compte"
      description="Gratuit, pour déposer vos propres documents."
      footer={
        <>
          <SubmitButton
            form="signup-form"
            className="w-full"
            pending={signUpMutation.isPending}
          >
            Créer le compte
          </SubmitButton>
          <p>
            Déjà un compte ?{" "}
            <Button variant="link" size="xs" asChild>
              <RouterLink to="/login">Se connecter</RouterLink>
            </Button>
          </p>
        </>
      }
    >
      <form id="signup-form" onSubmit={form.handleSubmit(onSubmit)}>
        <FieldGroup>
          <TextField
            control={form.control}
            name="full_name"
            label="Nom"
            placeholder="Prénom Nom"
            autoComplete="name"
            data-testid="full-name-input"
          />
          <TextField
            control={form.control}
            name="email"
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
            autoComplete="new-password"
            description="8 caractères minimum"
            data-testid="password-input"
          />
          <PasswordField
            control={form.control}
            name="confirm_password"
            label="Confirmez le mot de passe"
            autoComplete="new-password"
            data-testid="confirm-password-input"
          />
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
