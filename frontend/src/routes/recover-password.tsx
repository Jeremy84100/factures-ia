import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
} from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { LoginService } from "@/client"
import { SubmitButton, TextField } from "@/components/App/FormFields"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { isLoggedIn } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  email: z.email({ message: "Adresse e-mail invalide" }),
})

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/recover-password")({
  component: RecoverPassword,
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
        title: "Mot de passe oublié - Factures IA",
      },
    ],
  }),
})

function RecoverPassword() {
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
    },
  })
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const recoverPassword = async (data: FormData) => {
    await LoginService.recoverPassword({
      path: { email: data.email },
    })
  }

  const mutation = useMutation({
    mutationFn: recoverPassword,
    onSuccess: () => {
      showSuccessToast("E-mail de récupération envoyé")
      form.reset()
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = async (data: FormData) => {
    if (mutation.isPending) return
    mutation.mutate(data)
  }

  return (
    <AuthLayout
      title="Mot de passe oublié"
      description="Vous recevrez un lien par e-mail pour en choisir un nouveau."
      footer={
        <>
          <SubmitButton
            form="recover-form"
            className="w-full"
            pending={mutation.isPending}
          >
            Continuer
          </SubmitButton>
          <p>
            Vous vous en souvenez ?{" "}
            <Button variant="link" size="xs" asChild>
              <RouterLink to="/login">Se connecter</RouterLink>
            </Button>
          </p>
        </>
      }
    >
      <form id="recover-form" onSubmit={form.handleSubmit(onSubmit)}>
        <FieldGroup>
          <TextField
            control={form.control}
            name="email"
            label="E-mail"
            type="email"
            autoComplete="email"
            placeholder="vous@exemple.fr"
            data-testid="email-input"
          />
        </FieldGroup>
      </form>
    </AuthLayout>
  )
}
