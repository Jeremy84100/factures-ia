import {
  ChevronRight,
  ClipboardList,
  Info,
  Receipt,
  TriangleAlert,
  Truck,
} from "lucide-react"

import type { DocumentRef, LineMatch, Purchase } from "@/client"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
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
  afterLabel,
  formatAmount,
  formatDate,
  formatQuantity,
  KIND_LONG,
} from "@/lib/documents"
import { openPdf } from "@/lib/pdf"
import { overbilled, PurchaseBadge } from "./PurchaseRow"

const KIND_ICON = { order: ClipboardList, delivery: Truck, invoice: Receipt }
// "facturé 50, livré 45": the table already shows it in red.
const REPEATS_FIGURES = /(facturé|livré) \S+, (livré|commandé) \S+/

function Verdict({ purchase }: { purchase: Purchase }) {
  const extra = overbilled(purchase)
  const invoiced = Number(purchase.invoiced_excl_tax ?? 0)
  const [label, amount, footer] =
    purchase.status === "to_pay"
      ? ["Vous pouvez payer", formatAmount(invoiced), "Hors taxes"]
      : purchase.status === "dispute" && extra > 0.02
        ? [
            "Facturé en trop",
            formatAmount(extra),
            `Hors taxes, sur ${formatAmount(invoiced)} facturés`,
          ]
        : purchase.status === "dispute"
          ? ["Verdict", "Ne payez pas tout de suite", null]
          : purchase.status === "waiting"
            ? ["Verdict", "Pas encore payable", null]
            : ["Verdict", "Livraison et facture comparées entre elles", null]
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{amount}</CardTitle>
        <CardAction>
          <PurchaseBadge purchase={purchase} />
        </CardAction>
      </CardHeader>
      {footer && (
        <CardFooter className="text-sm text-muted-foreground">
          {footer}
        </CardFooter>
      )}
    </Card>
  )
}

function Reasons({ purchase }: { purchase: Purchase }) {
  const issues = purchase.issues ?? []
  const notes = purchase.notes ?? []
  return (
    <>
      {issues.length > 0 && (
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

function LineRow({ line }: { line: LineMatch }) {
  const issues = line.issues ?? []
  const notes = line.notes ?? []
  const flagged = (word: string) => issues.some((issue) => issue.includes(word))
  const cell = (word: string) =>
    flagged(word)
      ? "text-right font-medium text-destructive tabular-nums"
      : "text-right tabular-nums"
  const priceChanged =
    line.invoice_price != null &&
    line.order_price != null &&
    Number(line.invoice_price) !== Number(line.order_price)
  const extra = [...issues, ...notes].filter(
    (text) => !text.includes("prix") && !REPEATS_FIGURES.test(text),
  )
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <div className="font-medium">{line.label}</div>
        {line.reference && (
          <div className="text-muted-foreground">{line.reference}</div>
        )}
        {line.fee && (
          <div className="text-muted-foreground">
            Frais : payés sur la quantité commandée
          </div>
        )}
        {priceChanged && (
          <div
            className={
              flagged("prix") ? "text-destructive" : "text-muted-foreground"
            }
          >
            Prix {formatAmount(line.order_price)} commandé,{" "}
            {formatAmount(line.invoice_price)} facturé
          </div>
        )}
        {extra.map((text) => (
          <div
            key={text}
            className={
              issues.includes(text)
                ? "text-destructive"
                : "text-muted-foreground"
            }
          >
            {afterLabel(text)}
          </div>
        ))}
      </TableCell>
      <TableCell className={cell("commandé")}>
        {formatQuantity(line.ordered)}
      </TableCell>
      <TableCell className={cell("livré")}>
        {line.fee ? "—" : formatQuantity(line.delivered)}
      </TableCell>
      <TableCell className={cell("facturé")}>
        {formatQuantity(line.invoiced)}
      </TableCell>
    </TableRow>
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
      actions={<ChevronRight />}
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
      <div className="flex flex-col gap-6">
        <Verdict purchase={purchase} />
        <Reasons purchase={purchase} />

        {(purchase.lines?.length ?? 0) > 0 && (
          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-medium text-muted-foreground">
              Articles
            </h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Article</TableHead>
                  <TableHead className="text-right">Commandé</TableHead>
                  <TableHead className="text-right">Livré</TableHead>
                  <TableHead className="text-right">Facturé</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {purchase.lines?.map((line) => (
                  <LineRow
                    key={`${line.reference}-${line.label}`}
                    line={line}
                  />
                ))}
              </TableBody>
            </Table>
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
