import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"

import { DocumentsService } from "@/client"
import { ConfirmDialog } from "@/components/App/ConfirmDialog"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { plural } from "@/lib/documents"
import { handleError } from "@/utils"

const DeleteAllDocuments = ({ count }: { count: number }) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => DocumentsService.deleteAllDocuments(),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
    },
  })

  return (
    <ConfirmDialog
      trigger={
        <Button variant="ghost">
          <Trash2 data-icon="inline-start" />
          Tout supprimer
        </Button>
      }
      title="Tout supprimer ?"
      description={`${plural(count, "document", "documents")} et leurs PDF seront supprimés définitivement, avec les achats qui en dépendent.`}
      confirmLabel="Tout supprimer"
      pending={mutation.isPending}
      onConfirm={(close) =>
        mutation.mutate(undefined, {
          onSuccess: ({ data }) => {
            showSuccessToast(data.message)
            close()
          },
        })
      }
    />
  )
}

export default DeleteAllDocuments
