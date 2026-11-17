import { useMutation, useQueryClient } from "@tanstack/react-query"

import { UsersService } from "@/client"
import { ConfirmDialog } from "@/components/App/ConfirmDialog"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const DeleteConfirmation = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { logout } = useAuth()

  const mutation = useMutation({
    mutationFn: () => UsersService.deleteUserMe(),
    onSuccess: () => {
      showSuccessToast("Votre compte a été supprimé")
      logout()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["currentUser"] })
    },
  })

  return (
    <ConfirmDialog
      trigger={<Button variant="destructive">Supprimer mon compte</Button>}
      title="Supprimer votre compte ?"
      description="Toutes les données de votre compte seront supprimées définitivement."
      pending={mutation.isPending}
      onConfirm={() => mutation.mutate()}
    />
  )
}

export default DeleteConfirmation
