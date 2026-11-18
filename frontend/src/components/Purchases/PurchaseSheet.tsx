import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Check,
  CircleCheck,
  ClipboardList,
  Info,
  Mail,
  Receipt,
  RotateCcw,
  TriangleAlert,
  Truck,
} from "lucide-react"

import { Fragment, useState } from "react"

import {
  type DocumentRef,
  type LineMatch,
  type Purchase,
  ReconciliationsService,
} from "@/client"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { QuickAction, QuickActions } from "@/components/App/QuickAction"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card } from "@/components/ui/card"
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemFooter,
  ItemGroup,
  ItemSeparator,
  ItemTitle,
} from "@/components/ui/item"
import useCustomToast from "@/hooks/useCustomToast"
import {
  afterLabel,
  formatAmount,
  formatDate,
  formatQuantity,
  KIND_LONG,
} from "@/lib/documents"
import { openPdf } from "@/lib/pdf"
import { handleError } from "@/utils"
import { allIssues, overbilled, PurchaseBadge } from "./PurchaseRow"
import { SupplierEmailSection } from "./SupplierEmail"

const KIND_ICON = { order: ClipboardList, delivery: Truck, invoice: Receipt }
// "facturé 50, livré 45": the figures already show it in red.
const REPEATS_FIGURES = /(facturé|livré) \S+, (livré|commandé) \S+/

function Verdict({ purchase }: { purchase: Purchase }) {
  const extra = overbilled(purchase)
  const invoiced = Number(purchase.invoiced_excl_tax ?? 0)
  const [label, amount, footer] =
    purchase.status === "to_pay" && purchase.settled_at && extra > 0.02
      ? [
          "Vous pouvez payer",
          formatAmount(invoiced),
          `Hors taxes, moins l'avoir de ${formatAmount(extra)} s'il est accordé`,
        ]
      : purchase.status === "to_pay"
        ? ["Vous pouvez payer", formatAmount(invoiced), "Hors taxes"]
        : purchase.status === "dispute" && extra > 0.02
          ? [
              "Facturé en trop",
              formatAmount(extra),
              `Hors taxes, sur ${formatAmount(invoiced)} facturés`,
            ]
          : purchase.status === "dispute"
            ? ["Verdict", "À ne pas payer tout de suite", null]
            : purchase.status === "waiting"
              ? ["Verdict", "Pas encore payable", null]
              : ["Verdict", "Livraison et facture comparées entre elles", null]
  return (
    <section className="flex flex-col items-center gap-2 text-center">
      <PurchaseBadge purchase={purchase} />
      <p className="text-sm text-muted-foreground">{label}</p>
      <p
        className={
          footer
            ? "text-4xl font-semibold tracking-tight tabular-nums"
            : "text-xl font-semibold"
        }
      >
        {amount}
      </p>
      {footer && <p className="text-sm text-muted-foreground">{footer}</p>}
    </section>
  )
}

const settledOn = (purchase: Purchase) =>
  new Date(purchase.settled_at ?? "").toLocaleDateString("fr-FR")

function Reasons({ purchase }: { purchase: Purchase }) {
  const issues = purchase.issues ?? []
  const notes = purchase.notes ?? []
  return (
    <>
      {purchase.settled_at && (
        <Alert>
          <CircleCheck />
          <AlertTitle>Litige réglé le {settledOn(purchase)}</AlertTitle>
          <AlertDescription>
            <p>Écarts réglés avec le fournisseur :</p>
            <ul className="list-disc pl-4">
              {allIssues(purchase).map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {issues.length > 0 && !purchase.settled_at && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>À régler avant de payer</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {issues.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {notes.length > 0 && (
        <Alert>
          <Info />
          <AlertTitle>À savoir</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {notes.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </>
  )
}

function Figure({
  label,
  value,
  flagged,
}: {
  label: string
  value: string
  flagged: boolean
}) {
  return (
    <div className="flex flex-1 flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span
        className={
          flagged
            ? "font-medium text-destructive tabular-nums"
            : "font-medium tabular-nums"
        }
      >
        {value}
      </span>
    </div>
  )
}

// One article: its name, then ordered / delivered / invoiced side by side,
// the figure at fault in red.
function LineRow({ line, settled }: { line: LineMatch; settled: boolean }) {
  const issues = settled ? [] : (line.issues ?? [])
  const notes = settled
    ? [...(line.issues ?? []), ...(line.notes ?? [])]
    : (line.notes ?? [])
  const flagged = (word: string) => issues.some((issue) => issue.includes(word))
  const priceChanged =
    line.invoice_price != null &&
    line.order_price != null &&
    Number(line.invoice_price) !== Number(line.order_price)
  const extra = [...issues, ...notes].filter(
    (text) => !text.includes("prix") && !REPEATS_FIGURES.test(text),
  )
  return (
    <Item>
      <ItemContent className="min-w-0">
        <ItemTitle className="block w-full">{line.label}</ItemTitle>
        {line.reference && <ItemDescription>{line.reference}</ItemDescription>}
        {line.fee && (
          <ItemDescription>
            Frais : payés sur la quantité commandée
          </ItemDescription>
        )}
        {priceChanged && (
          <ItemDescription
            className={flagged("prix") ? "text-destructive" : undefined}
          >
            Prix {formatAmount(line.order_price)} commandé,{" "}
            {formatAmount(line.invoice_price)} facturé
          </ItemDescription>
        )}
        {extra.map((text) => (
          <ItemDescription
            key={text}
            className={issues.includes(text) ? "text-destructive" : undefined}
          >
            {afterLabel(text)}
          </ItemDescription>
        ))}
      </ItemContent>
      <ItemFooter className="gap-4">
        <Figure
          label="Commandé"
          value={formatQuantity(line.ordered)}
          flagged={flagged("commandé")}
        />
        <Figure
          label="Livré"
          value={line.fee ? "—" : formatQuantity(line.delivered)}
          flagged={flagged("livré")}
        />
        <Figure
          label="Facturé"
          value={formatQuantity(line.invoiced)}
          flagged={flagged("facturé")}
        />
      </ItemFooter>
    </Item>
  )
}

function DocumentLink({ document }: { document: DocumentRef }) {
  const { showErrorToast } = useCustomToast()
  const kind = document.kind as keyof typeof KIND_ICON
  return (
    <ListRow
      icon={KIND_ICON[kind] ?? Receipt}
      title={`${KIND_LONG[document.kind]} ${document.number ?? ""}`}
      subtitle={formatDate(document.document_date)}
      chevron
      onClick={() =>
        openPdf(document.id).catch(() =>
          showErrorToast("Impossible d'ouvrir le document"),
        )
      }
    />
  )
}

// What to do about a dispute: write to the supplier, then mark it as settled
// once the credit note or the agreement is there. Settling can be undone.
function DisputeActions({
  purchase,
  writing,
  onWrite,
}: {
  purchase: Purchase
  writing: boolean
  onWrite: () => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const path = { path: { key: purchase.key } }
  const settle = useMutation({
    mutationFn: () => ReconciliationsService.settlePurchase(path),
    onSuccess: () =>
      showSuccessToast("Litige réglé : l'achat passe dans les bons à payer"),
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["purchases"] }),
  })
  const reopen = useMutation({
    mutationFn: () => ReconciliationsService.reopenPurchase(path),
    onSuccess: () => showSuccessToast("Le litige est de nouveau ouvert"),
    onError: handleError.bind(showErrorToast),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["purchases"] }),
  })

  if (purchase.settled_at)
    return (
      <QuickActions>
        <QuickAction
          icon={RotateCcw}
          label="Rouvrir"
          pending={reopen.isPending}
          onClick={() => reopen.mutate()}
        />
      </QuickActions>
    )
  if (purchase.status !== "dispute") return null
  return (
    <QuickActions>
      <QuickAction
        icon={Mail}
        label="Écrire"
        disabled={writing}
        onClick={onWrite}
      />
      <QuickAction
        icon={Check}
        label="Réglé"
        pending={settle.isPending}
        onClick={() => settle.mutate()}
      />
    </QuickActions>
  )
}

export function PurchaseSheet({
  purchase,
  open,
  onOpenChange,
}: {
  purchase: Purchase | undefined
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [writing, setWriting] = useState<string | null>(null)
  if (!purchase) return null
  const documents = [
    ...(purchase.orders ?? []),
    ...(purchase.deliveries ?? []),
    ...(purchase.invoices ?? []),
  ]
  return (
    <ResponsiveSheet
      open={open}
      onOpenChange={(next) => {
        if (!next) setWriting(null)
        onOpenChange(next)
      }}
      title={purchase.supplier ?? `Commande ${purchase.order_reference}`}
      description={`Commande ${purchase.order_reference}`}
    >
      <div className="flex flex-col gap-6">
        <Verdict purchase={purchase} />
        <DisputeActions
          purchase={purchase}
          writing={writing === purchase.key}
          onWrite={() => setWriting(purchase.key)}
        />
        <Reasons purchase={purchase} />
        {writing === purchase.key && purchase.status === "dispute" && (
          <SupplierEmailSection purchaseKey={purchase.key} />
        )}

        {(purchase.lines?.length ?? 0) > 0 && (
          <section className="flex flex-col gap-3">
            <h2 className="px-1 text-base font-semibold">Articles</h2>
            <Card size="sm" className="gap-0 py-1.5">
              <ItemGroup className="gap-0">
                {purchase.lines?.map((line, index) => (
                  <Fragment key={`${line.reference}-${line.label}`}>
                    {index > 0 && <ItemSeparator className="my-0" />}
                    <LineRow line={line} settled={!!purchase.settled_at} />
                  </Fragment>
                ))}
              </ItemGroup>
            </Card>
          </section>
        )}

        <ListGroup title="Documents">
          {documents.map((document) => (
            <DocumentLink key={document.id} document={document} />
          ))}
        </ListGroup>
      </div>
    </ResponsiveSheet>
  )
}
