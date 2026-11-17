import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Eye, Pencil, RotateCw, Trash2, TriangleAlert } from "lucide-react"
import { useState } from "react"

import { type DocumentPublic, DocumentsService } from "@/client"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
  isBusy,
  KIND_LONG,
} from "@/lib/documents"
import { openPdf } from "@/lib/pdf"
import { handleError } from "@/utils"
import DeleteDocument from "./DeleteDocument"
import { DocumentBadge, documentAmount } from "./DocumentRow"
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
    if (document.amount_excl_tax)
      rows.push(["Total HT", money(document.amount_excl_tax)])
    if (document.vat_amount) rows.push(["TVA", money(document.vat_amount)])
    if (document.amount_incl_tax)
      rows.push(["Total TTC", money(document.amount_incl_tax)])
  }
  rows.push(["Fichier", document.filename])
  return (
    <Table>
      <TableBody>
        {rows.map(([label, value]) => (
          <TableRow key={label}>
            <TableCell className="text-muted-foreground">{label}</TableCell>
            <TableCell className="text-right font-medium whitespace-normal break-all">
              {value}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Lines({ document }: { document: DocumentPublic }) {
  const lines = document.lines ?? []
  if (lines.length === 0) return null
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {lines.length > 1 ? `${lines.length} articles` : "1 article"}
      </h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Article</TableHead>
            <TableHead className="text-right">Qté</TableHead>
            <TableHead className="text-right">Montant HT</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line, index) => (
            <TableRow key={`${line.reference}-${index}`}>
              <TableCell className="whitespace-normal">
                <div>{line.description ?? line.reference}</div>
                {line.unit_price && (
                  <div className="text-muted-foreground">
                    {formatAmount(line.unit_price)} l'unité
                  </div>
                )}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatQuantity(line.quantity)} {line.unit ?? ""}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatAmount(line.amount_excl_tax)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
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
  const amount = documentAmount(document)
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
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardDescription>
                {document.kind === "invoice" ? "Total TTC" : "Total HT"}
              </CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {amount ?? "—"}
              </CardTitle>
              <CardAction>
                <DocumentBadge document={document} />
              </CardAction>
            </CardHeader>
          </Card>

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

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Button
              variant="outline"
              onClick={() =>
                openPdf(document.id).catch(() =>
                  showErrorToast("Impossible d'ouvrir le document"),
                )
              }
            >
              <Eye data-icon="inline-start" />
              Voir
            </Button>
            <Button
              variant="outline"
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
              variant="outline"
              disabled={busy || retry.isPending}
              onClick={() => retry.mutate(document.id)}
            >
              <RotateCw data-icon="inline-start" />
              Relire
            </Button>
            <Button variant="destructive" onClick={() => switchTo(setDeleting)}>
              <Trash2 data-icon="inline-start" />
              Supprimer
            </Button>
          </div>

          <Details document={document} />
          <Lines document={document} />
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
