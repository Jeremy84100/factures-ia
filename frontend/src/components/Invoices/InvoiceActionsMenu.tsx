import { useMutation, useQueryClient } from "@tanstack/react-query"
import { EllipsisVertical, FileText, RotateCw } from "lucide-react"
import { useState } from "react"

import { type InvoicePublic, InvoicesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { isBusy } from "@/lib/invoices"
import { handleError } from "@/utils"
import DeleteInvoice from "./DeleteInvoice"
import EditInvoice from "./EditInvoice"

interface InvoiceActionsMenuProps {
  invoice: InvoicePublic
}

export const InvoiceActionsMenu = ({ invoice }: InvoiceActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const retry = useMutation({
    mutationFn: () =>
      InvoicesService.retryInvoice({ path: { id: invoice.id } }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] })
    },
  })

  const openPdf = async () => {
    const { data } = await InvoicesService.readInvoiceFile({
      path: { id: invoice.id },
      responseType: "blob",
    })
    window.open(URL.createObjectURL(data as Blob), "_blank")
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Actions">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={openPdf}>
          <FileText />
          Voir le PDF
        </DropdownMenuItem>
        <EditInvoice invoice={invoice} onSuccess={() => setOpen(false)} />
        <DropdownMenuItem
          disabled={isBusy(invoice)}
          onClick={() => retry.mutate()}
        >
          <RotateCw />
          Relire avec l'IA
        </DropdownMenuItem>
        <DeleteInvoice id={invoice.id} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
