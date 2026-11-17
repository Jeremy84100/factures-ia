import { useMutation, useQueryClient } from "@tanstack/react-query"

import { DocumentsService } from "@/client"
import { ConfirmDialog } from "@/components/App/ConfirmDialog"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteDocumentProps {
  id: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

const DeleteDocument = ({ id, open, onOpenChange }: DeleteDocumentProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => DocumentsService.deleteDocument({ path: { id } }),
    onSuccess: () => {
      showSuccessToast("Document supprimé")
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
    },
  })

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Supprimer le document ?"
      description="Le document et son PDF seront supprimés définitivement."
      pending={mutation.isPending}
      onConfirm={() => mutation.mutate()}
    />
  )
}

export default DeleteDocument
