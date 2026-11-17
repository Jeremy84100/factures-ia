import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import {
  createFileRoute,
  Link as RouterLink,
  redirect,
  useNavigate,
} from "@tanstack/react-router"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { LoginService } from "@/client"
import { PasswordField, SubmitButton } from "@/components/App/FormFields"
import { AuthLayout } from "@/components/Common/AuthLayout"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { isLoggedIn } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const searchSchema = z.object({
  token: z.string().catch(""),
})

const formSchema = z
  .object({
    new_password: z
      .string()
      .min(1, { message: "Mot de passe obligatoire" })
      .min(8, { message: "8 caractères minimum" }),
    confirm_password: z
      .string()
      .min(1, { message: "Confirmez le mot de passe" }),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

export const Route = createFileRoute("/reset-password")({
  component: ResetPassword,
  validateSearch: searchSchema,
  beforeLoad: async ({ search }) => {
    if (isLoggedIn()) {
      throw redirect({ to: "/" })
    }
    if (!search.token) {
      throw redirect({ to: "/login" })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Nouveau mot de passe - Factures IA",
      },
    ],
  }),
})

function ResetPassword() {
  const { token } = Route.useSearch()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const navigate = useNavigate()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      new_password: "",
      confirm_password: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: { new_password: string; token: string }) =>
      LoginService.resetPassword({ body: data }),
    onSuccess: () => {
      showSuccessToast("Mot de passe modifié")
      form.reset()
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate({ new_password: data.new_password, token })
  }

  return (
    <AuthLayout
      title="Nouveau mot de passe"
      footer={
        <>
          <SubmitButton
            form="reset-form"
            className="w-full"
            pending={mutation.isPending}
          >
            Changer le mot de passe
          </SubmitButton>
          <Button variant="link" size="xs" asChild>
            <RouterLink to="/login">Retour à la connexion</RouterLink>
          </Button>
        </>
      }
    >
      <form id="reset-form" onSubmit={form.handleSubmit(onSubmit)}>
        <FieldGroup>
          <PasswordField
            control={form.control}
            name="new_password"
            label="Nouveau mot de passe"
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
