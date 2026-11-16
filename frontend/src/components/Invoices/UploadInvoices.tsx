import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Upload } from "lucide-react"
import { useRef } from "react"

import { InvoicesService } from "@/client"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const UploadInvoices = () => {
  const input = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: async (files: File[]) => {
      for (const file of files) {
        await InvoicesService.uploadInvoices({ body: { files: [file] } })
        queryClient.invalidateQueries({ queryKey: ["invoices"] })
      }
      return files.length
    },
    onSuccess: (count) => {
      showSuccessToast(
        count > 1
          ? `${count} factures envoyées, lecture en cours`
          : "Facture envoyée, lecture en cours",
      )
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      if (input.current) input.current.value = ""
      queryClient.invalidateQueries({ queryKey: ["invoices"] })
    },
  })

  return (
    <>
      <input
        ref={input}
        type="file"
        accept="application/pdf"
        multiple
        hidden
        data-testid="invoice-input"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          if (files.length > 0) mutation.mutate(files)
        }}
      />
      <LoadingButton
        className="my-4"
        loading={mutation.isPending}
        onClick={() => input.current?.click()}
      >
        <Upload className="mr-2" />
        Déposer des factures
      </LoadingButton>
    </>
  )
}

export default UploadInvoices
