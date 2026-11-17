import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import { useFieldArray, useForm } from "react-hook-form"
import { z } from "zod"

import {
  type DeliveryMode,
  type DocumentKind,
  type DocumentPublic,
  DocumentsService,
} from "@/client"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const decimal = (places: number) =>
  z.string().regex(new RegExp(`^-?\\d*([.,]\\d{0,${places}})?$`), {
    message: "Nombre invalide",
  })

const amount = decimal(2)

const lineSchema = z.object({
  reference: z.string().max(100),
  description: z.string().max(255),
  quantity: decimal(3),
  unit: z.string().max(20),
  unit_price: decimal(4),
  amount_excl_tax: amount,
})

const formSchema = z.object({
  kind: z.enum(["unknown", "invoice", "order", "delivery"]),
  supplier: z.string(),
  number: z.string(),
  document_date: z.string(),
  order_reference: z.string().max(100),
  amount_excl_tax: amount,
  vat_amount: amount,
  amount_incl_tax: amount,
  currency: z.string().max(3),
  vat_exemption: z.string().max(255),
  delivery_method: z.string().max(100),
  expected_delivery_date: z.string(),
  delivery_mode: z.enum(["none", "pickup", "standard", "express"]),
  is_credit_note: z.boolean(),
  lines: z.array(lineSchema),
})

type FormData = z.infer<typeof formSchema>
type LineData = z.infer<typeof lineSchema>
type TextField = Exclude<
  keyof FormData,
  "kind" | "delivery_mode" | "is_credit_note" | "lines"
>

const KIND_OPTIONS: { value: DocumentKind; label: string }[] = [
  { value: "invoice", label: "Facture ou avoir" },
  { value: "order", label: "Bon de commande" },
  { value: "delivery", label: "Bon de livraison" },
  { value: "unknown", label: "Autre document" },
]

const MODE_OPTIONS: { value: DeliveryMode | "none"; label: string }[] = [
  { value: "none", label: "Non indiqué" },
  { value: "standard", label: "Livraison standard" },
  { value: "express", label: "Livraison express" },
  { value: "pickup", label: "Retrait par le client" },
]

const WIDE: TextField[] = ["supplier", "vat_exemption"]
const NUMERIC = new Set([
  "amount_excl_tax",
  "vat_amount",
  "amount_incl_tax",
  "quantity",
  "unit_price",
])

const FIELDS: {
  name: TextField
  label: string
  type?: string
  kinds?: DocumentKind[]
}[] = [
  { name: "supplier", label: "Fournisseur" },
  { name: "number", label: "Numéro du document" },
  { name: "document_date", label: "Date", type: "date" },
  {
    name: "order_reference",
    label: "N° de la commande",
    kinds: ["invoice", "delivery"],
  },
  { name: "amount_excl_tax", label: "Total HT", kinds: ["invoice", "order"] },
  { name: "vat_amount", label: "TVA", kinds: ["invoice", "order"] },
  { name: "amount_incl_tax", label: "Total TTC", kinds: ["invoice", "order"] },
  { name: "currency", label: "Devise", kinds: ["invoice", "order"] },
  {
    name: "vat_exemption",
    label: "Mention d'exonération de TVA",
    kinds: ["invoice"],
  },
  {
    name: "delivery_method",
    label: "Mode de livraison écrit",
    kinds: ["order", "delivery"],
  },
  {
    name: "expected_delivery_date",
    label: "Livraison promise le",
    type: "date",
    kinds: ["order"],
  },
]

const LINE_FIELDS: {
  name: keyof LineData
  label: string
  className: string
  numeric?: boolean
}[] = [
  { name: "reference", label: "Réf.", className: "w-24" },
  {
    name: "description",
    label: "Désignation",
    className:
      "order-first basis-full sm:order-none sm:basis-auto sm:min-w-40 sm:flex-1",
  },
  { name: "quantity", label: "Qté", className: "w-20", numeric: true },
  { name: "unit", label: "Unité", className: "w-16" },
  { name: "unit_price", label: "Prix HT", className: "w-24", numeric: true },
  {
    name: "amount_excl_tax",
    label: "Montant",
    className: "w-24",
    numeric: true,
  },
]

const EMPTY_LINE: LineData = {
  reference: "",
  description: "",
  quantity: "",
  unit: "",
  unit_price: "",
  amount_excl_tax: "",
}

const toText = (value: string | number | null | undefined) =>
  value === null || value === undefined ? "" : String(value)

const toNumberText = (value: string | number | null | undefined) =>
  value === null || value === undefined ? "" : String(Number(value))

const toValue = (value: string, numeric: boolean) => {
  const trimmed = numeric ? value.trim().replace(",", ".") : value.trim()
  return trimmed === "" ? null : trimmed
}

const toValues = <T extends Record<string, string>>(values: T) =>
  Object.fromEntries(
    Object.entries(values).map(([key, value]) => [
      key,
      toValue(value, NUMERIC.has(key)),
    ]),
  )

interface EditDocumentProps {
  document: DocumentPublic
  open: boolean
  onOpenChange: (open: boolean) => void
}

const EditDocument = ({ document, open, onOpenChange }: EditDocumentProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      ...Object.fromEntries(
        FIELDS.map(({ name }) => [name, toText(document[name])]),
      ),
      kind: document.kind,
      delivery_mode: document.delivery_mode ?? "none",
      is_credit_note: document.is_credit_note ?? false,
      lines: (document.lines ?? []).map((line) => ({
        reference: toText(line.reference),
        description: toText(line.description),
        quantity: toNumberText(line.quantity),
        unit: toText(line.unit),
        unit_price: toNumberText(line.unit_price),
        amount_excl_tax: toText(line.amount_excl_tax),
      })),
    } as FormData,
  })
  const lines = useFieldArray({ control: form.control, name: "lines" })
  const kind = form.watch("kind")

  const mutation = useMutation({
    mutationFn: ({
      kind,
      delivery_mode,
      is_credit_note,
      lines,
      ...text
    }: FormData) =>
      DocumentsService.updateDocument({
        path: { id: document.id },
        body: {
          ...toValues(text),
          kind,
          delivery_mode: delivery_mode === "none" ? null : delivery_mode,
          is_credit_note,
          lines: lines.map(toValues),
        },
      }),
    onSuccess: ({ data }) => {
      showSuccessToast(
        data.status === "ok"
          ? "Document corrigé et validé"
          : "Document corrigé, il reste des points à vérifier",
      )
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
    },
  })

  return (
    <ResponsiveSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Corriger le document"
      description={document.filename}
      wide
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit((data) => mutation.mutate(data))}>
          {document.issues.length > 0 && (
            <ul className="list-disc rounded-2xl bg-warning/10 p-3 pl-7 text-sm">
              {document.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
          <div className="grid grid-cols-1 gap-4 py-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="kind"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Type de document</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {KIND_OPTIONS.map(({ value, label }) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormItem>
              )}
            />
            {FIELDS.filter(({ kinds }) => !kinds || kinds.includes(kind)).map(
              ({ name, label, type }) => (
                <FormField
                  key={name}
                  control={form.control}
                  name={name}
                  render={({ field }) => (
                    <FormItem
                      className={WIDE.includes(name) ? "sm:col-span-2" : ""}
                    >
                      <FormLabel>{label}</FormLabel>
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
              ),
            )}
            {(kind === "order" || kind === "delivery") && (
              <FormField
                control={form.control}
                name="delivery_mode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Type de livraison</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {MODE_OPTIONS.map(({ value, label }) => (
                          <SelectItem key={value} value={value}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
            )}
            {kind === "invoice" && (
              <FormField
                control={form.control}
                name="is_credit_note"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-2 sm:col-span-2">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={(checked) =>
                          field.onChange(checked === true)
                        }
                      />
                    </FormControl>
                    <FormLabel>
                      C'est un avoir (les montants seront comptés en négatif)
                    </FormLabel>
                  </FormItem>
                )}
              />
            )}
          </div>

          <div className="flex flex-col gap-2 pb-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">Lignes d'articles</h3>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => lines.append(EMPTY_LINE)}
              >
                <Plus />
                Ajouter une ligne
              </Button>
            </div>
            {lines.fields.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucune ligne.</p>
            )}
            {lines.fields.map((line, index) => (
              <div
                key={line.id}
                className="flex flex-wrap items-end gap-2 rounded-2xl bg-muted/50 p-2 sm:flex-nowrap sm:bg-transparent sm:p-0"
              >
                {LINE_FIELDS.map(({ name, label, className, numeric }) => (
                  <FormField
                    key={name}
                    control={form.control}
                    name={`lines.${index}.${name}`}
                    render={({ field }) => (
                      <FormItem className={className}>
                        <FormLabel
                          className={cn("text-xs", index > 0 && "sm:hidden")}
                        >
                          {label}
                        </FormLabel>
                        <FormControl>
                          <Input
                            aria-label={`${label}, ligne ${index + 1}`}
                            inputMode={numeric ? "decimal" : undefined}
                            className={numeric ? "text-right" : ""}
                            {...field}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                ))}
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Supprimer la ligne ${index + 1}`}
                  onClick={() => lines.remove(index)}
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
          </div>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="secondary"
              className="h-12 rounded-full sm:h-10"
              disabled={mutation.isPending}
              onClick={() => onOpenChange(false)}
            >
              Annuler
            </Button>
            <LoadingButton
              type="submit"
              className="h-12 rounded-full sm:h-10"
              loading={mutation.isPending}
            >
              Enregistrer
            </LoadingButton>
          </div>
        </form>
      </Form>
    </ResponsiveSheet>
  )
}

export default EditDocument
