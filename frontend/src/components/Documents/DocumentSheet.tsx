import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Eye, Pencil, RotateCw, Trash2, TriangleAlert } from "lucide-react"
import { type ReactNode, useState } from "react"

import { type DocumentPublic, DocumentsService } from "@/client"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import useCustomToast from "@/hooks/useCustomToast"
import {
  formatAmount,
  formatDate,
  formatQuantity,
  isBusy,
  KIND_LONG,
  STATUS,
  STATUS_TONE,
  TONE_CLASSES,
} from "@/lib/documents"
import { openPdf } from "@/lib/pdf"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import DeleteDocument from "./DeleteDocument"
import { documentAmount } from "./DocumentRow"
import EditDocument from "./EditDocument"

const SWITCH_MS = 280
const MODE = {
  pickup: "Retrait",
  standard: "Livraison standard",
  express: "Express",
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  )
}

function Details({ document }: { document: DocumentPublic }) {
  const money = (value: string | null | undefined) =>
    formatAmount(value, document.currency ?? "EUR")
  const rows: [string, ReactNode][] = [
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
  rows.push([
    "Fichier",
    <span key="file" className="break-all">
      {document.filename}
    </span>,
  ])
  return (
    <Card className="gap-0 divide-y divide-border/70 px-5 py-1">
      {rows.map(([label, value]) => (
        <Detail key={label} label={label}>
          {value}
        </Detail>
      ))}
    </Card>
  )
}

function Lines({ document }: { document: DocumentPublic }) {
  const lines = document.lines ?? []
  if (lines.length === 0) return null
  return (
    <section className="flex flex-col gap-1">
      <h3 className="px-1 pb-1 text-sm font-medium text-muted-foreground">
        {lines.length > 1 ? `${lines.length} articles` : "1 article"}
      </h3>
      <Card className="gap-0 divide-y divide-border/70 px-5 py-1">
        {lines.map((line, index) => (
          <div
            key={`${line.reference}-${index}`}
            className="flex items-baseline justify-between gap-4 py-2.5"
          >
            <span className="min-w-0">
              <span className="block truncate">
                {line.description ?? line.reference}
              </span>
              <span className="text-sm text-muted-foreground">
                {formatQuantity(line.quantity)} {line.unit ?? ""}
                {line.unit_price ? ` × ${formatAmount(line.unit_price)}` : ""}
              </span>
            </span>
            {line.amount_excl_tax && (
              <span className="shrink-0 tabular-nums">
                {formatAmount(line.amount_excl_tax)}
              </span>
            )}
          </div>
        ))}
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
  const tone = STATUS_TONE[document.status]
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
          <div className="flex flex-col gap-3">
            <Badge className={cn("h-7 px-3 text-sm", TONE_CLASSES[tone])}>
              {STATUS[document.status].label}
            </Badge>
            {amount && (
              <span className="text-4xl font-semibold tracking-tight tabular-nums">
                {amount}
              </span>
            )}
            {document.issues.length > 0 && (
              <ul className="flex flex-col gap-3">
                {document.issues.map((issue) => (
                  <li key={issue} className="flex gap-3">
                    <TriangleAlert className="mt-0.5 size-5 shrink-0 text-warning" />
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Button
              variant="secondary"
              className="h-12 rounded-2xl"
              onClick={() =>
                openPdf(document.id).catch(() =>
                  showErrorToast("Impossible d'ouvrir le document"),
                )
              }
            >
              <Eye />
              Voir
            </Button>
            <Button
              variant="secondary"
              className="h-12 rounded-2xl"
              disabled={busy}
              onClick={() => {
                setEditRound((round) => round + 1)
                switchTo(setEditing)
              }}
            >
              <Pencil />
              Corriger
            </Button>
            <Button
              variant="secondary"
              className="h-12 rounded-2xl"
              disabled={busy || retry.isPending}
              onClick={() => retry.mutate(document.id)}
            >
              <RotateCw />
              Relire
            </Button>
            <Button
              variant="secondary"
              className="h-12 rounded-2xl text-destructive"
              onClick={() => switchTo(setDeleting)}
            >
              <Trash2 />
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
