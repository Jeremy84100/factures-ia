import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2, TriangleAlert } from "lucide-react"
import { Controller, useFieldArray, useForm } from "react-hook-form"
import { z } from "zod"

import {
  type DeliveryMode,
  type DocumentKind,
  type DocumentPublic,
  DocumentsService,
} from "@/client"
import { SubmitButton } from "@/components/App/FormFields"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
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
  payment_terms: z.string().max(100),
  due_date: z.string(),
  iban: z.string().max(42),
  supplier_email: z.string().max(255),
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

const WIDE: TextField[] = [
  "supplier",
  "vat_exemption",
  "due_date",
  "iban",
  "supplier_email",
]
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
    name: "payment_terms",
    label: "Conditions de paiement",
    kinds: ["invoice"],
  },
  {
    name: "due_date",
    label: "Échéance (vide : calculée depuis les conditions)",
    type: "date",
    kinds: ["invoice"],
  },
  { name: "iban", label: "IBAN du fournisseur", kinds: ["invoice"] },
  { name: "supplier_email", label: "E-mail du fournisseur" },
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
  width: string
  numeric?: boolean
}[] = [
  { name: "reference", label: "Réf.", width: "min-w-24" },
  { name: "description", label: "Désignation", width: "min-w-56" },
  { name: "quantity", label: "Qté", width: "min-w-20", numeric: true },
  { name: "unit", label: "Unité", width: "min-w-16" },
  { name: "unit_price", label: "Prix HT", width: "min-w-24", numeric: true },
  {
    name: "amount_excl_tax",
    label: "Montant",
    width: "min-w-24",
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
          ...toValues({ ...text, iban: text.iban.replace(/\s/g, "") }),
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

  const textField = (name: TextField, label: string, type?: string) => (
    <Controller
      key={name}
      control={form.control}
      name={name}
      render={({ field, fieldState }) => (
        <Field
          data-invalid={fieldState.invalid}
          className={WIDE.includes(name) ? "sm:col-span-2" : undefined}
        >
          <FieldLabel htmlFor={name}>{label}</FieldLabel>
          <Input
            {...field}
            id={name}
            type={type ?? "text"}
            inputMode={NUMERIC.has(name) ? "decimal" : undefined}
            aria-invalid={fieldState.invalid}
          />
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  )

  return (
    <ResponsiveSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Corriger le document"
      description={document.filename}
      wide
    >
      <form
        id="edit-document-form"
        onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
        className="flex flex-col gap-6"
      >
        {document.issues.length > 0 && (
          <Alert>
            <TriangleAlert />
            <AlertTitle>À vérifier</AlertTitle>
            <AlertDescription>
              <ul className="list-disc pl-4">
                {document.issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        <FieldGroup className="grid gap-4 sm:grid-cols-2">
          <Controller
            control={form.control}
            name="kind"
            render={({ field }) => (
              <Field className="sm:col-span-2">
                <FieldLabel htmlFor="kind">Type de document</FieldLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="kind" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {KIND_OPTIONS.map(({ value, label }) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            )}
          />
          {FIELDS.filter(({ kinds }) => !kinds || kinds.includes(kind)).map(
            ({ name, label, type }) => textField(name, label, type),
          )}
          {(kind === "order" || kind === "delivery") && (
            <Controller
              control={form.control}
              name="delivery_mode"
              render={({ field }) => (
                <Field>
                  <FieldLabel htmlFor="delivery_mode">
                    Type de livraison
                  </FieldLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="delivery_mode" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MODE_OPTIONS.map(({ value, label }) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              )}
            />
          )}
          {kind === "invoice" && (
            <Controller
              control={form.control}
              name="is_credit_note"
              render={({ field }) => (
                <Field orientation="horizontal" className="sm:col-span-2">
                  <Checkbox
                    id="is_credit_note"
                    checked={field.value}
                    onCheckedChange={(checked) =>
                      field.onChange(checked === true)
                    }
                  />
                  <FieldLabel htmlFor="is_credit_note">
                    C'est un avoir (les montants seront comptés en négatif)
                  </FieldLabel>
                </Field>
              )}
            />
          )}
        </FieldGroup>

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-medium">Lignes d'articles</h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => lines.append(EMPTY_LINE)}
            >
              <Plus data-icon="inline-start" />
              Ajouter une ligne
            </Button>
          </div>
          {lines.fields.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune ligne.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  {LINE_FIELDS.map(({ name, label, numeric }) => (
                    <TableHead
                      key={name}
                      className={numeric ? "text-right" : undefined}
                    >
                      {label}
                    </TableHead>
                  ))}
                  <TableHead>
                    <span className="sr-only">Supprimer</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lines.fields.map((line, index) => (
                  <TableRow key={line.id}>
                    {LINE_FIELDS.map(({ name, label, width, numeric }) => (
                      <TableCell key={name} className={width}>
                        <Controller
                          control={form.control}
                          name={`lines.${index}.${name}`}
                          render={({ field, fieldState }) => (
                            <Input
                              {...field}
                              aria-label={`${label}, ligne ${index + 1}`}
                              aria-invalid={fieldState.invalid}
                              inputMode={numeric ? "decimal" : undefined}
                              className={numeric ? "text-right" : undefined}
                            />
                          )}
                        />
                      </TableCell>
                    ))}
                    <TableCell>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label={`Supprimer la ligne ${index + 1}`}
                        onClick={() => lines.remove(index)}
                      >
                        <Trash2 />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            disabled={mutation.isPending}
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

export default EditDocument
