import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"

import { DocumentsService } from "@/client"
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
import { LoadingButton } from "@/components/ui/loading-button"
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
  const { handleSubmit } = useForm()

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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl border-none sm:max-w-md">
        <form onSubmit={handleSubmit(() => mutation.mutate())}>
          <DialogHeader>
            <DialogTitle>Supprimer le document</DialogTitle>
            <DialogDescription>
              Le document et son PDF seront supprimés définitivement.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                Annuler
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              type="submit"
              loading={mutation.isPending}
            >
              Supprimer
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteDocument
