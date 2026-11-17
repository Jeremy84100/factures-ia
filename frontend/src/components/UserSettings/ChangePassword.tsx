import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type UpdatePassword, UsersService } from "@/client"
import { PasswordField, SubmitButton } from "@/components/App/FormFields"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FieldGroup } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    current_password: z
      .string()
      .min(1, { message: "Mot de passe obligatoire" })
      .min(8, { message: "8 caractères minimum" }),
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

const ChangePassword = () => {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onSubmit",
    criteriaMode: "all",
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: UpdatePassword) =>
      UsersService.updatePasswordMe({ body: data }),
    onSuccess: () => {
      showSuccessToast("Mot de passe modifié")
      form.reset()
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = async (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mot de passe</CardTitle>
        <CardDescription>8 caractères minimum.</CardDescription>
      </CardHeader>
      <CardContent>
        <form id="password-form" onSubmit={form.handleSubmit(onSubmit)}>
          <FieldGroup>
            <PasswordField
              control={form.control}
              name="current_password"
              label="Mot de passe actuel"
              autoComplete="current-password"
            />
            <PasswordField
              control={form.control}
              name="new_password"
              label="Nouveau mot de passe"
              autoComplete="new-password"
            />
            <PasswordField
              control={form.control}
              name="confirm_password"
              label="Confirmez le nouveau mot de passe"
              autoComplete="new-password"
            />
          </FieldGroup>
        </form>
      </CardContent>
      <CardFooter>
        <SubmitButton form="password-form" pending={mutation.isPending}>
          Changer le mot de passe
        </SubmitButton>
      </CardFooter>
    </Card>
  )
}

export default ChangePassword
