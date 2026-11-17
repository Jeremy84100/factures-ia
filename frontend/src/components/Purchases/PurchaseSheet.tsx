import {
  ClipboardList,
  Info,
  Receipt,
  TriangleAlert,
  Truck,
} from "lucide-react"

import type { DocumentRef, LineMatch, Purchase } from "@/client"
import { Amount } from "@/components/App/Amount"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Badge } from "@/components/ui/badge"
import useCustomToast from "@/hooks/useCustomToast"
import {
  afterLabel,
  formatAmount,
  formatDate,
  formatQuantity,
  KIND_LONG,
  PURCHASE_STATUS,
  PURCHASE_TONE,
  TONE_CLASSES,
} from "@/lib/documents"
import { openPdf } from "@/lib/pdf"
import { cn } from "@/lib/utils"
import { overbilled } from "./PurchaseRow"

const KIND_ICON = { order: ClipboardList, delivery: Truck, invoice: Receipt }
// "facturé 50, livré 45": already shown in red by the three figures.
const REPEATS_FIGURES = /(facturé|livré) \S+, (livré|commandé) \S+/

function Verdict({ purchase }: { purchase: Purchase }) {
  const extra = overbilled(purchase)
  const invoiced = Number(purchase.invoiced_excl_tax ?? 0)
  switch (purchase.status) {
    case "to_pay":
      return (
        <div className="flex flex-col">
          <span className="text-muted-foreground">Vous pouvez payer</span>
          <Amount value={invoiced} className="text-4xl" />
          <span className="text-sm text-muted-foreground">hors taxes</span>
        </div>
      )
    case "dispute":
      return extra > 0.02 ? (
        <div className="flex flex-col">
          <span className="text-muted-foreground">Facturé en trop</span>
          <Amount value={extra} className="text-4xl text-destructive" />
          <span className="text-sm text-muted-foreground">
            hors taxes, sur {formatAmount(invoiced)} facturés
          </span>
        </div>
      ) : (
        <p className="text-2xl font-semibold">Ne payez pas tout de suite.</p>
      )
    case "waiting":
      return <p className="text-2xl font-semibold">Pas encore payable.</p>
    default:
      return (
        <p className="text-2xl font-semibold">
          Livraison et facture comparées entre elles.
        </p>
      )
  }
}

function Reasons({ purchase }: { purchase: Purchase }) {
  const issues = purchase.issues ?? []
  const notes = purchase.notes ?? []
  if (issues.length + notes.length === 0) return null
  return (
    <ul className="flex flex-col gap-3">
      {issues.map((text) => (
        <li key={text} className="flex gap-3">
          <TriangleAlert className="mt-0.5 size-5 shrink-0 text-destructive" />
          <span>{text}</span>
        </li>
      ))}
      {notes.map((text) => (
        <li key={text} className="flex gap-3 text-muted-foreground">
          <Info className="mt-0.5 size-5 shrink-0" />
          <span>{text}</span>
        </li>
      ))}
    </ul>
  )
}

function Figure({
  label,
  value,
  alert,
}: {
  label: string
  value: string
  alert: boolean
}) {
  return (
    <span className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span
        className={cn(
          "tabular-nums",
          alert ? "font-semibold text-destructive" : "font-medium",
        )}
      >
        {value}
      </span>
    </span>
  )
}

function Line({ line }: { line: LineMatch }) {
  const issues = line.issues ?? []
  const notes = line.notes ?? []
  const flagged = (word: string) => issues.some((issue) => issue.includes(word))
  const priceChanged =
    line.invoice_price !== null &&
    line.invoice_price !== undefined &&
    line.order_price !== null &&
    line.order_price !== undefined &&
    Number(line.invoice_price) !== Number(line.order_price)
  return (
    <div className="flex flex-col gap-2 px-3 py-3 md:px-4">
      <div className="flex flex-col">
        <span className="font-medium">{line.label}</span>
        {line.reference && (
          <span className="text-xs text-muted-foreground">
            {line.reference}
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Figure
          label="Commandé"
          value={formatQuantity(line.ordered)}
          alert={flagged("commandé")}
        />
        <Figure
          label="Livré"
          value={line.fee ? "—" : formatQuantity(line.delivered)}
          alert={flagged("livré")}
        />
        <Figure
          label="Facturé"
          value={formatQuantity(line.invoiced)}
          alert={flagged("facturé")}
        />
      </div>
      {line.fee && (
        <span className="text-sm text-muted-foreground">
          Frais : payés sur la quantité commandée
        </span>
      )}
      {priceChanged && (
        <span
          className={cn(
            "text-sm",
            flagged("prix") ? "text-destructive" : "text-muted-foreground",
          )}
        >
          Prix {formatAmount(line.order_price)} commandé,{" "}
          {formatAmount(line.invoice_price)} facturé
        </span>
      )}
      {[...issues, ...notes]
        .filter((text) => !text.includes("prix") && !REPEATS_FIGURES.test(text))
        .map((text) => (
          <span
            key={text}
            className={cn(
              "text-sm",
              issues.includes(text)
                ? "text-destructive"
                : "text-muted-foreground",
            )}
          >
            {afterLabel(text)}
          </span>
        ))}
    </div>
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
      end={<span className="text-sm text-primary">Voir</span>}
      onClick={() =>
        openPdf(document.id).catch(() =>
          showErrorToast("Impossible d'ouvrir le document"),
        )
      }
    />
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
  if (!purchase) return null
  const tone = PURCHASE_TONE[purchase.status]
  const documents = [
    ...(purchase.orders ?? []),
    ...(purchase.deliveries ?? []),
    ...(purchase.invoices ?? []),
  ]
  return (
    <ResponsiveSheet
      open={open}
      onOpenChange={onOpenChange}
      title={purchase.supplier ?? `Commande ${purchase.order_reference}`}
      description={`Commande ${purchase.order_reference}`}
    >
      <div className="flex flex-col gap-7">
        <div className="flex flex-col gap-4">
          <Badge className={cn("h-7 px-3 text-sm", TONE_CLASSES[tone])}>
            {PURCHASE_STATUS[purchase.status].label}
          </Badge>
          <Verdict purchase={purchase} />
          <Reasons purchase={purchase} />
        </div>

        {(purchase.lines?.length ?? 0) > 0 && (
          <ListGroup title="Articles">
            <div className="flex flex-col divide-y divide-border/70">
              {purchase.lines?.map((line) => (
                <Line key={`${line.reference}-${line.label}`} line={line} />
              ))}
            </div>
          </ListGroup>
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
