import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type InvoicePublic, InvoicesService } from "@/client"
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { isBusy } from "@/lib/invoices"
import { handleError } from "@/utils"

const amount = z
  .string()
  .regex(/^-?\d*([.,]\d{0,2})?$/, { message: "Montant invalide" })

const formSchema = z.object({
  supplier: z.string(),
  invoice_number: z.string(),
  invoice_date: z.string(),
  amount_excl_tax: amount,
  vat_amount: amount,
  amount_incl_tax: amount,
  currency: z.string().max(3),
})

type FormData = z.infer<typeof formSchema>

const FIELDS: {
  name: keyof FormData
  label: string
  type?: string
  required?: boolean
}[] = [
  { name: "supplier", label: "Fournisseur", required: true },
  { name: "invoice_number", label: "Numéro" },
  { name: "invoice_date", label: "Date", type: "date", required: true },
  { name: "amount_excl_tax", label: "Total HT" },
  { name: "vat_amount", label: "TVA" },
  { name: "amount_incl_tax", label: "Total TTC", required: true },
  { name: "currency", label: "Devise" },
]

const toText = (value: string | number | null | undefined) =>
  value === null || value === undefined ? "" : String(value)

const toValue = (value: string) => {
  const trimmed = value.trim().replace(",", ".")
  return trimmed === "" ? null : trimmed
}

interface EditInvoiceProps {
  invoice: InvoicePublic
  onSuccess: () => void
}

const EditInvoice = ({ invoice, onSuccess }: EditInvoiceProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: Object.fromEntries(
      FIELDS.map(({ name }) => [name, toText(invoice[name])]),
    ) as FormData,
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      InvoicesService.updateInvoice({
        path: { id: invoice.id },
        body: Object.fromEntries(
          Object.entries(data).map(([key, value]) => [key, toValue(value)]),
        ),
      }),
    onSuccess: ({ data }) => {
      showSuccessToast(
        data.status === "ok"
          ? "Facture corrigée et validée"
          : "Facture corrigée, il reste des points à vérifier",
      )
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        disabled={isBusy(invoice)}
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        Corriger
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <Form {...form}>
          <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
            <DialogHeader>
              <DialogTitle>Corriger la facture</DialogTitle>
              <DialogDescription>{invoice.filename}</DialogDescription>
            </DialogHeader>
            {invoice.issues.length > 0 && (
              <ul className="mt-4 list-disc rounded-md bg-muted p-3 pl-7 text-sm">
                {invoice.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
            <div className="grid grid-cols-2 gap-4 py-4">
              {FIELDS.map(({ name, label, type, required }) => (
                <FormField
                  key={name}
                  control={form.control}
                  name={name}
                  render={({ field }) => (
                    <FormItem
                      className={name === "supplier" ? "col-span-2" : ""}
                    >
                      <FormLabel>
                        {label}
                        {required && (
                          <span className="text-destructive">*</span>
                        )}
                      </FormLabel>
                      <FormControl>
                        <Input
                          type={type ?? "text"}
                          inputMode={
                            name.includes("amount") ? "decimal" : undefined
                          }
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ))}
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Annuler
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Enregistrer
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditInvoice
