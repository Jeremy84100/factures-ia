import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { UsersService } from "@/client"
import { ConfirmDialog } from "@/components/App/ConfirmDialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteUserProps {
  id: string
  onSuccess: () => void
}

const DeleteUser = ({ id, onSuccess }: DeleteUserProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => UsersService.deleteUser({ path: { user_id: id } }),
    onSuccess: () => {
      showSuccessToast("Utilisateur supprimé")
      setOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries(),
  })

  return (
    <>
      <DropdownMenuItem
        variant="destructive"
        onSelect={(event) => {
          event.preventDefault()
          setOpen(true)
        }}
      >
        <Trash2 />
        Supprimer l'utilisateur
      </DropdownMenuItem>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Supprimer l'utilisateur ?"
        description="Ses documents seront aussi supprimés définitivement."
        pending={mutation.isPending}
        onConfirm={() => mutation.mutate()}
      />
    </>
  )
}

export default DeleteUser
