import { useMutation, useQueryClient } from "@tanstack/react-query"
import { EllipsisVertical, FileText, RotateCw } from "lucide-react"
import { useState } from "react"

import { type DocumentPublic, DocumentsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { isBusy } from "@/lib/documents"
import { handleError } from "@/utils"
import DeleteDocument from "./DeleteDocument"
import EditDocument from "./EditDocument"

export async function openPdf(id: string) {
  const { data } = await DocumentsService.readDocumentFile({
    path: { id },
    responseType: "blob",
  })
  window.open(URL.createObjectURL(data as Blob), "_blank")
}

export const DocumentActionsMenu = ({
  document,
}: {
  document: DocumentPublic
}) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const retry = useMutation({
    mutationFn: () =>
      DocumentsService.retryDocument({ path: { id: document.id } }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
    },
  })

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Actions">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => openPdf(document.id)}>
          <FileText />
          Voir le PDF
        </DropdownMenuItem>
        <EditDocument document={document} onSuccess={() => setOpen(false)} />
        <DropdownMenuItem
          disabled={isBusy(document)}
          onClick={() => retry.mutate()}
        >
          <RotateCw />
          Relire avec l'IA
        </DropdownMenuItem>
        <DeleteDocument id={document.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
