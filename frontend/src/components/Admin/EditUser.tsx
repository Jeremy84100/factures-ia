import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type UserPublic, UsersService } from "@/client"
import {
  CheckboxField,
  PasswordField,
  SubmitButton,
  TextField,
} from "@/components/App/FormFields"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { FieldGroup } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    email: z.email({ message: "Adresse e-mail invalide" }),
    full_name: z.string().optional(),
    password: z
      .string()
      .min(8, { message: "8 caractères minimum" })
      .optional()
      .or(z.literal("")),
    confirm_password: z.string().optional(),
    is_superuser: z.boolean().optional(),
    is_active: z.boolean().optional(),
  })
  .refine((data) => !data.password || data.password === data.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

const PASSWORD_HINT = "Facultatif, 8 caractères minimum"

interface EditUserProps {
  user: UserPublic
  onSuccess: () => void
}

const EditUser = ({ user, onSuccess }: EditUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: user.email,
      full_name: user.full_name ?? undefined,
      is_superuser: user.is_superuser,
      is_active: user.is_active,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      UsersService.updateUser({ path: { user_id: user.id }, body: data }),
    onSuccess: () => {
      showSuccessToast("Utilisateur modifié")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const onSubmit = (data: FormData) => {
    // exclude confirm_password from submission data and remove password if empty
    const { confirm_password: _, ...submitData } = data
    if (!submitData.password) {
      delete submitData.password
    }
    mutation.mutate(submitData)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        Modifier l'utilisateur
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Modifier l'utilisateur</DialogTitle>
          <DialogDescription>
            Laissez le mot de passe vide pour le garder.
          </DialogDescription>
        </DialogHeader>
        <form id="edit-user-form" onSubmit={form.handleSubmit(onSubmit)}>
          <FieldGroup>
            <TextField
              control={form.control}
              name="email"
              label="E-mail"
              type="email"
              placeholder="nom@entreprise.fr"
            />
            <TextField control={form.control} name="full_name" label="Nom" />
            <PasswordField
              control={form.control}
              name="password"
              label="Mot de passe"
              autoComplete="new-password"
              description={PASSWORD_HINT}
            />
            <PasswordField
              control={form.control}
              name="confirm_password"
              label="Confirmez le mot de passe"
              autoComplete="new-password"
            />
            <CheckboxField
              control={form.control}
              name="is_superuser"
              label="Administrateur"
              description="Peut gérer les autres utilisateurs."
            />
            <CheckboxField
              control={form.control}
              name="is_active"
              label="Compte actif"
            />
          </FieldGroup>
        </form>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Annuler
            </Button>
          </DialogClose>
          <SubmitButton form="edit-user-form" pending={mutation.isPending}>
            Enregistrer
          </SubmitButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default EditUser
