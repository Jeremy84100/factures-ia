import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  BadgeCheck,
  Eye,
  Pencil,
  RotateCw,
  Trash2,
  TriangleAlert,
} from "lucide-react"
import { Fragment, useState } from "react"

import { type DocumentPublic, DocumentsService } from "@/client"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import {
  formatAmount,
  formatDate,
  formatQuantity,
  groupIban,
  isBusy,
  KIND_LONG,
  plural,
} from "@/lib/documents"
import { openPdf } from "@/lib/pdf"
import { handleError } from "@/utils"
import DeleteDocument from "./DeleteDocument"
import { DocumentBadge } from "./DocumentRow"
import EditDocument from "./EditDocument"

const SWITCH_MS = 280
const MODE = {
  pickup: "Retrait",
  standard: "Livraison standard",
  express: "Express",
}

function Details({ document }: { document: DocumentPublic }) {
  const money = (value: string | null | undefined) =>
    formatAmount(value, document.currency ?? "EUR")
  const rows: [string, string][] = [
    ["Date", formatDate(document.document_date)],
  ]
  if (document.kind !== "order" && document.order_reference)
    rows.push(["N° de commande", document.order_reference])
  if (document.kind === "order" || document.kind === "delivery") {
    const mode = document.delivery_mode ? MODE[document.delivery_mode] : null
    const method = document.delivery_method ?? mode
    if (method) rows.push(["Livraison", method])
    if (document.expected_delivery_date)
      rows.push(["Promise le", formatDate(document.expected_delivery_date)])
  }
  if (document.kind !== "delivery") {
    // HT and VAT on one line: they are read together, the TTC is on top.
    const totals = [
      document.amount_excl_tax && `${money(document.amount_excl_tax)} HT`,
      document.vat_amount && `TVA ${money(document.vat_amount)}`,
    ].filter(Boolean)
    if (totals.length) rows.push(["Montants", totals.join(" · ")])
  }
  if (
    document.kind === "invoice" &&
    (document.due_date || document.payment_terms)
  )
    rows.push([
      "Échéance",
      [
        document.due_date && formatDate(document.due_date),
        document.payment_terms &&
          (document.due_date
            ? `(${document.payment_terms})`
            : document.payment_terms),
      ]
        .filter(Boolean)
        .join(" "),
    ])
  if (document.iban) rows.push(["IBAN", groupIban(document.iban)])
  if (document.supplier_email) rows.push(["E-mail", document.supplier_email])
  return (
    <Card size="sm" className="py-3">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 px-4 text-sm">
        {rows.map(([label, value]) => (
          <Fragment key={label}>
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-right font-medium break-words">{value}</dd>
          </Fragment>
        ))}
      </dl>
    </Card>
  )
}

function Lines({ document }: { document: DocumentPublic }) {
  const lines = document.lines ?? []
  if (lines.length === 0) return null
  const priced = document.kind !== "delivery"
  const head = "h-9 px-2 text-right text-xs text-muted-foreground"
  return (
    <section className="flex flex-col gap-2">
      <h2 className="px-1 text-sm font-semibold">
        {plural(lines.length, "article", "articles")}
      </h2>
      <Card size="sm" className="py-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="h-9 text-xs text-muted-foreground">
                Article
              </TableHead>
              <TableHead className={head}>Qté</TableHead>
              {priced && <TableHead className={head}>HT</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.map((line, index) => {
              const detail = [
                line.description && line.reference,
                line.unit_price && `${formatAmount(line.unit_price)} l'unité`,
              ]
                .filter(Boolean)
                .join(" · ")
              return (
                <TableRow
                  key={`${line.reference}-${index}`}
                  className="hover:bg-transparent"
                >
                  <TableCell className="py-2 whitespace-normal">
                    <p className="font-medium">
                      {line.description ?? line.reference}
                    </p>
                    {detail && (
                      <p className="text-xs text-muted-foreground">{detail}</p>
                    )}
                  </TableCell>
                  <TableCell className="px-2 py-2 text-right tabular-nums">
                    {formatQuantity(line.quantity)} {line.unit ?? ""}
                  </TableCell>
                  {priced && (
                    <TableCell className="px-2 py-2 text-right tabular-nums">
                      {formatAmount(line.amount_excl_tax)}
                    </TableCell>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Card>
    </section>
  )
}

export function DocumentSheet({
  document,
  open,
  onOpenChange,
}: {
  document: DocumentPublic | undefined
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [editing, setEditing] = useState(false)
  // A new form each time it opens, filled with the latest values.
  const [editRound, setEditRound] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const retry = useMutation({
    mutationFn: (id: string) =>
      DocumentsService.retryDocument({ path: { id } }),
    onSuccess: () => onOpenChange(false),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
    },
  })

  if (!document) return null
  const busy = isBusy(document)
  const money = (value: string) =>
    formatAmount(value, document.currency ?? "EUR")
  // A delivery note has no price: what counts is what came.
  const [label, figure] =
    document.kind === "delivery"
      ? ["Livré", plural(document.lines?.length ?? 0, "article", "articles")]
      : document.amount_incl_tax != null
        ? ["Total TTC", money(document.amount_incl_tax)]
        : document.amount_excl_tax != null
          ? ["Total HT", money(document.amount_excl_tax)]
          : ["Total", "—"]
  // The detail slides away first, then the next panel comes up: never two at once.
  const switchTo = (setter: (value: boolean) => void) => {
    onOpenChange(false)
    window.setTimeout(() => setter(true), SWITCH_MS)
  }

  return (
    <>
      <ResponsiveSheet
        open={open}
        onOpenChange={onOpenChange}
        title={document.supplier ?? document.filename}
        description={[
          document.is_credit_note ? "Avoir" : KIND_LONG[document.kind],
          document.number,
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <div className="flex flex-col gap-5">
          <section className="flex flex-col gap-1">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <DocumentBadge document={document} />
              <span>{label}</span>
            </div>
            <p className="text-3xl font-semibold tracking-tight tabular-nums">
              {figure}
            </p>
            {document.from_einvoice && (
              <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <BadgeCheck className="size-4" />
                Facture électronique : chiffres lus dans le fichier, sans IA
              </p>
            )}
            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                size="sm"
                onClick={() =>
                  openPdf(document.id).catch(() =>
                    showErrorToast("Impossible d'ouvrir le document"),
                  )
                }
              >
                <Eye data-icon="inline-start" />
                Voir le PDF
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setEditRound((round) => round + 1)
                  switchTo(setEditing)
                }}
              >
                <Pencil data-icon="inline-start" />
                Corriger
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy || retry.isPending}
                onClick={() => retry.mutate(document.id)}
              >
                {retry.isPending ? (
                  <Spinner data-icon="inline-start" />
                ) : (
                  <RotateCw data-icon="inline-start" />
                )}
                Relire avec l'IA
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                className="text-destructive"
                aria-label="Supprimer"
                onClick={() => switchTo(setDeleting)}
              >
                <Trash2 />
              </Button>
            </div>
          </section>

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

          <Details document={document} />
          <Lines document={document} />
          <p className="px-1 text-xs break-all text-muted-foreground">
            Fichier : {document.filename}
          </p>
        </div>
      </ResponsiveSheet>
      <EditDocument
        key={`edit-${document.id}-${editRound}`}
        document={document}
        open={editing}
        onOpenChange={setEditing}
      />
      <DeleteDocument
        id={document.id}
        open={deleting}
        onOpenChange={setDeleting}
      />
    </>
  )
}
