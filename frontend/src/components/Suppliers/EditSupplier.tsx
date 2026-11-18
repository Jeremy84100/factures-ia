import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"

import { type SupplierDetail, SuppliersService } from "@/client"
import { SubmitButton, TextField } from "@/components/App/FormFields"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, { message: "Le nom est obligatoire" })
    .max(255),
  country: z
    .string()
    .trim()
    .regex(/^([A-Za-z]{2})?$/, { message: "Code à 2 lettres : FR, DE, US…" }),
  date_order: z.enum(["auto", "day_first", "month_first"]),
  payment_terms: z.string().max(100),
  email: z.union([
    z.literal(""),
    z.string().trim().email({ message: "Adresse e-mail invalide" }),
  ]),
  iban: z.string().max(42),
})

type FormData = z.infer<typeof formSchema>

const ORDERS = [
  { value: "auto", label: "Selon le pays" },
  { value: "day_first", label: "Jour/mois (08/01 = 8 janvier)" },
  { value: "month_first", label: "Mois/jour (08/01 = 1er août)" },
] as const

export function EditSupplier({
  supplier,
  open,
  onOpenChange,
}: {
  supplier: SupplierDetail
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    values: {
      name: supplier.name,
      country: supplier.country ?? "",
      date_order: supplier.date_order ?? "auto",
      payment_terms: supplier.payment_terms ?? "",
      email: supplier.email ?? "",
      iban: supplier.iban ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      SuppliersService.updateSupplier({
        path: { id: supplier.id },
        body: {
          name: data.name,
          country: data.country.toUpperCase() || null,
          date_order: data.date_order === "auto" ? null : data.date_order,
          payment_terms: data.payment_terms || null,
          email: data.email || null,
          iban: data.iban.replace(/\s/g, "") || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Fournisseur enregistré, ses documents sont à jour")
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] })
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
    },
  })

  return (
    <ResponsiveSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Modifier le fournisseur"
      description={supplier.name}
    >
      <form
        onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
        className="flex flex-col gap-4"
      >
        <TextField control={form.control} name="name" label="Nom" />
        <div className="grid gap-4 sm:grid-cols-[6rem_1fr]">
          <TextField
            control={form.control}
            name="country"
            label="Pays"
            placeholder="FR"
            maxLength={2}
            autoCapitalize="characters"
          />
          <Controller
            control={form.control}
            name="date_order"
            render={({ field }) => (
              <Field>
                <FieldLabel htmlFor="date_order">Dates écrites en</FieldLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="date_order" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ORDERS.map((order) => (
                      <SelectItem key={order.value} value={order.value}>
                        {order.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            )}
          />
        </div>
        <TextField
          control={form.control}
          name="payment_terms"
          label="Conditions de paiement"
          placeholder="30 jours fin de mois"
        />
        <TextField
          control={form.control}
          name="email"
          label="E-mail"
          type="email"
          placeholder="compta@fournisseur.fr"
        />
        <TextField
          control={form.control}
          name="iban"
          label="IBAN"
          autoComplete="off"
          description="Ne le changez qu'après avoir appelé le fournisseur à un numéro que vous connaissez."
        />
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Annuler
          </Button>
          <SubmitButton pending={mutation.isPending}>Enregistrer</SubmitButton>
        </div>
      </form>
    </ResponsiveSheet>
  )
}
