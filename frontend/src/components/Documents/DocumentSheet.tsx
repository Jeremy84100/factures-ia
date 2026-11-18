import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  BadgeCheck,
  Eye,
  Pencil,
  RotateCw,
  Trash2,
  TriangleAlert,
} from "lucide-react"
import { useState } from "react"

import { type DocumentPublic, DocumentsService } from "@/client"
import {
  BigAmount,
  QuickAction,
  QuickActions,
} from "@/components/App/QuickAction"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card } from "@/components/ui/card"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemTitle,
} from "@/components/ui/item"
import useCustomToast from "@/hooks/useCustomToast"
import {
  formatAmount,
  formatDate,
  formatQuantity,
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
    if (document.amount_excl_tax)
      rows.push(["Total HT", money(document.amount_excl_tax)])
    if (document.vat_amount) rows.push(["TVA", money(document.vat_amount)])
    if (document.amount_incl_tax)
      rows.push(["Total TTC", money(document.amount_incl_tax)])
  }
  if (document.kind === "invoice") {
    if (document.payment_terms)
      rows.push(["Conditions de paiement", document.payment_terms])
    if (document.due_date)
      rows.push(["Échéance", formatDate(document.due_date)])
  }
  rows.push(["Fichier", document.filename])
  return (
    <Card size="sm" className="gap-0 py-1.5">
      <ItemGroup className="gap-0">
        {rows.map(([label, value]) => (
          <Item key={label} size="sm" className="flex-nowrap">
            <ItemContent>
              <ItemDescription>{label}</ItemDescription>
            </ItemContent>
            <ItemActions className="min-w-0 text-right">
              <span className="font-medium break-all">{value}</span>
            </ItemActions>
          </Item>
        ))}
      </ItemGroup>
    </Card>
  )
}

function Lines({ document }: { document: DocumentPublic }) {
  const lines = document.lines ?? []
  if (lines.length === 0) return null
  return (
    <section className="flex flex-col gap-3">
      <h2 className="px-1 text-base font-semibold">
        {lines.length > 1 ? `${lines.length} articles` : "1 article"}
      </h2>
      <Card size="sm" className="gap-0 py-1.5">
        <ItemGroup className="gap-0">
          {lines.map((line, index) => (
            <Item key={`${line.reference}-${index}`} className="flex-nowrap">
              <ItemContent className="min-w-0">
                <ItemTitle className="block w-full">
                  {line.description ?? line.reference}
                </ItemTitle>
                {line.unit_price && (
                  <ItemDescription>
                    {formatAmount(line.unit_price)} l'unité
                  </ItemDescription>
                )}
              </ItemContent>
              <ItemActions className="flex-col items-end gap-1 text-right">
                <span className="font-medium tabular-nums">
                  {formatAmount(line.amount_excl_tax)}
                </span>
                <span className="text-muted-foreground tabular-nums">
                  {formatQuantity(line.quantity)} {line.unit ?? ""}
                </span>
              </ItemActions>
            </Item>
          ))}
        </ItemGroup>
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
        <div className="flex flex-col gap-6">
          <section className="flex flex-col items-center gap-2 text-center">
            <DocumentBadge document={document} />
            <p className="text-sm text-muted-foreground">{label}</p>
            <BigAmount text={figure} size="md" />
          </section>

          {document.from_einvoice && (
            <Alert>
              <BadgeCheck />
              <AlertTitle>Facture électronique</AlertTitle>
              <AlertDescription>
                Chiffres lus tels quels dans le fichier joint au PDF, sans IA.
              </AlertDescription>
            </Alert>
          )}

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

          <QuickActions>
            <QuickAction
              icon={Eye}
              label="Voir"
              onClick={() =>
                openPdf(document.id).catch(() =>
                  showErrorToast("Impossible d'ouvrir le document"),
                )
              }
            />
            <QuickAction
              icon={Pencil}
              label="Corriger"
              disabled={busy}
              onClick={() => {
                setEditRound((round) => round + 1)
                switchTo(setEditing)
              }}
            />
            <QuickAction
              icon={RotateCw}
              label="Relire"
              disabled={busy}
              pending={retry.isPending}
              onClick={() => retry.mutate(document.id)}
            />
            <QuickAction
              icon={Trash2}
              label="Supprimer"
              destructive
              onClick={() => switchTo(setDeleting)}
            />
          </QuickActions>

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
