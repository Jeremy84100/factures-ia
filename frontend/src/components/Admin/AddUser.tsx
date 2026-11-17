import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type UserCreate, UsersService } from "@/client"
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
  DialogTrigger,
} from "@/components/ui/dialog"
import { FieldGroup } from "@/components/ui/field"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    email: z.email({ message: "Adresse e-mail invalide" }),
    full_name: z.string().optional(),
    password: z
      .string()
      .min(1, { message: "Mot de passe obligatoire" })
      .min(8, { message: "8 caractères minimum" }),
    confirm_password: z
      .string()
      .min(1, { message: "Confirmez le mot de passe" }),
    is_superuser: z.boolean(),
    is_active: z.boolean(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

const PASSWORD_HINT = "8 caractères minimum"

const AddUser = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      full_name: "",
      password: "",
      confirm_password: "",
      is_superuser: false,
      is_active: false,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: UserCreate) => UsersService.createUser({ body: data }),
    onSuccess: () => {
      showSuccessToast("Utilisateur créé")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus data-icon="inline-start" />
          Ajouter un utilisateur
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Ajouter un utilisateur</DialogTitle>
          <DialogDescription>
            Remplissez le formulaire pour ajouter un utilisateur.
          </DialogDescription>
        </DialogHeader>
        <form id="add-user-form" onSubmit={form.handleSubmit(onSubmit)}>
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
          <SubmitButton form="add-user-form" pending={mutation.isPending}>
            Ajouter
          </SubmitButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default AddUser
