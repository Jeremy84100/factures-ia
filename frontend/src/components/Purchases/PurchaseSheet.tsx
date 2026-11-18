import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Check,
  CircleCheck,
  ClipboardList,
  Info,
  Link2,
  Mail,
  Receipt,
  RotateCcw,
  TriangleAlert,
  Truck,
} from "lucide-react"

import { Fragment, useState } from "react"

import {
  type DocumentRef,
  DocumentsService,
  type LineMatch,
  type Purchase,
  ReconciliationsService,
  type UnlinkedDocument,
} from "@/client"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { QuickAction, QuickActions } from "@/components/App/QuickAction"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
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
  days,
  daysUntil,
  formatAmount,
  formatDate,
  formatQuantity,
  KIND_LONG,
} from "@/lib/documents"
import { openPdf } from "@/lib/pdf"
import { handleError } from "@/utils"
import {
  allIssues,
  isCredit,
  overbilled,
  PurchaseBadge,
  paidOn,
  purchaseSubtitle,
  purchaseTitle,
} from "./PurchaseRow"
import { SupplierEmailSection } from "./SupplierEmail"

const KIND_ICON = { order: ClipboardList, delivery: Truck, invoice: Receipt }
// "facturé 50, livré 45": the figures already show it in red.
const REPEATS_FIGURES = /(facturé|livré) \S+, (livré|commandé) \S+/

// "TTC, avant le 20/11/2026", with why that date when nothing was written.
function dueText(purchase: Purchase) {
  if (!purchase.due_date) return "TTC"
  const left = daysUntil(purchase.due_date)
  const date = formatDate(purchase.due_date)
  const when =
    left < 0
      ? `TTC, échéance du ${date} dépassée de ${days(-left)}`
      : left === 0
        ? "TTC, à payer aujourd'hui"
        : `TTC, à payer avant le ${date}`
  return purchase.due_date_assumed
    ? `${when} (30 jours, le délai légal : aucune échéance sur la facture)`
    : when
}

function Verdict({ purchase }: { purchase: Purchase }) {
  const extra = overbilled(purchase)
  const toPay = Number(purchase.to_pay_incl_tax ?? 0)
  const invoiced = purchase.invoiced_incl_tax ?? purchase.invoiced_excl_tax
  const [label, amount, footer]: [string, string, string | null] =
    purchase.status === "paid"
      ? [`Payé le ${paidOn(purchase)}`, formatAmount(invoiced), "TTC"]
      : purchase.status === "to_pay" && isCredit(purchase)
        ? [
            "Avoir à déduire",
            formatAmount(-toPay),
            "TTC, de votre prochain paiement à ce fournisseur",
          ]
        : purchase.status === "to_pay"
          ? ["Montant", formatAmount(toPay), dueText(purchase)]
          : purchase.status === "dispute" && extra > 0.02
            ? [
                "Facturé en trop",
                formatAmount(extra),
                `TTC, sur ${formatAmount(invoiced)} facturés`,
              ]
            : purchase.status === "dispute"
              ? ["Verdict", "À ne pas payer tout de suite", null]
              : ["Verdict", "Pas encore payable", null]
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
            <p>Un avoir est prévu ? Déposez-le : il sera déduit d'ici.</p>
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
// the figure at fault in red. Only the columns this purchase has documents for.
function LineRow({ line, purchase }: { line: LineMatch; purchase: Purchase }) {
  const settled = !!purchase.settled_at
  const issues = settled ? [] : (line.issues ?? [])
  const notes = settled
    ? [...(line.issues ?? []), ...(line.notes ?? [])]
    : (line.notes ?? [])
  const flagged = (word: string) => issues.some((issue) => issue.includes(word))
  const priceChanged =
    line.invoice_price != null &&
    line.order_price != null &&
    Number(line.invoice_price) !== Number(line.order_price)
  const price = line.invoice_price ?? line.order_price
  const extra = [...issues, ...notes].filter(
    (text) => !text.includes("prix") && !REPEATS_FIGURES.test(text),
  )
  return (
    <Item>
      <ItemContent className="min-w-0">
        <ItemTitle className="block w-full">{line.label}</ItemTitle>
        {line.reference && <ItemDescription>{line.reference}</ItemDescription>}
        {line.fee && !purchase.invoice_only && (
          <ItemDescription>
            Frais : payés sur la quantité commandée
          </ItemDescription>
        )}
        {priceChanged ? (
          <ItemDescription
            className={flagged("prix") ? "text-destructive" : undefined}
          >
            Prix {formatAmount(line.order_price)} commandé,{" "}
            {formatAmount(line.invoice_price)} facturé
          </ItemDescription>
        ) : (
          purchase.invoice_only &&
          price != null && (
            <ItemDescription>{formatAmount(price)} HT l'unité</ItemDescription>
          )
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
        {(purchase.orders?.length ?? 0) > 0 && (
          <Figure
            label="Commandé"
            value={formatQuantity(line.ordered)}
            flagged={flagged("commandé")}
          />
        )}
        {(purchase.deliveries?.length ?? 0) > 0 && (
          <Figure
            label="Livré"
            value={line.fee ? "—" : formatQuantity(line.delivered)}
            flagged={flagged("livré")}
          />
        )}
        {(purchase.invoices?.length ?? 0) > 0 && (
          <Figure
            label="Facturé"
            value={formatQuantity(line.invoiced)}
            flagged={flagged("facturé")}
          />
        )}
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

function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ["purchases"] })
    queryClient.invalidateQueries({ queryKey: ["documents"] })
  }
}

// A delivery note or an invoice left aside, that may be this purchase's:
// one tap files it here instead of typing the order number.
function LinkProposals({
  purchase,
  unlinked,
}: {
  purchase: Purchase
  unlinked: UnlinkedDocument[]
}) {
  const refresh = useRefresh()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const link = useMutation({
    mutationFn: (id: string) =>
      DocumentsService.updateDocument({
        path: { id },
        body: { order_reference: purchase.order_reference },
      }),
    onSuccess: () => showSuccessToast("Document rangé dans cet achat"),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })
  const proposals = unlinked.filter((document) =>
    document.suggestions?.some((s) => s.key === purchase.key),
  )
  if (proposals.length === 0) return null
  return (
    <>
      {proposals.map((document) => (
        <Alert key={document.id}>
          <Link2 />
          <AlertTitle>
            {KIND_LONG[document.kind]} {document.number} à ranger
          </AlertTitle>
          <AlertDescription>
            <p>
              Du même fournisseur, daté du {formatDate(document.document_date)}{" "}
              et sans numéro de commande. Est-ce celui de cet achat ?
            </p>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                size="sm"
                disabled={link.isPending}
                onClick={() => link.mutate(document.id)}
              >
                Oui, le ranger ici
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  openPdf(document.id).catch(() =>
                    showErrorToast("Impossible d'ouvrir le document"),
                  )
                }
              >
                Voir le document
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ))}
    </>
  )
}

function usePurchaseAction(call: () => Promise<unknown>, message: string) {
  const refresh = useRefresh()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  return useMutation({
    mutationFn: call,
    onSuccess: () => showSuccessToast(message),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })
}

// What to do now: pay, write to the supplier, settle, or undo.
function Actions({
  purchase,
  writing,
  onWrite,
}: {
  purchase: Purchase
  writing: boolean
  onWrite: () => void
}) {
  const { showErrorToast } = useCustomToast()
  const path = { path: { key: purchase.key } }
  const credit = isCredit(purchase)
  const pay = usePurchaseAction(
    () => ReconciliationsService.payPurchase(path),
    credit
      ? "Avoir noté comme déduit"
      : "Payé : l'achat est rangé dans les payés",
  )
  const unpay = usePurchaseAction(
    () => ReconciliationsService.unpayPurchase(path),
    "L'achat est de nouveau à payer",
  )
  const settle = usePurchaseAction(
    () => ReconciliationsService.settlePurchase(path),
    "Litige réglé : l'achat passe dans les achats à payer",
  )
  const reopen = usePurchaseAction(
    () => ReconciliationsService.reopenPurchase(path),
    "Le litige est de nouveau ouvert",
  )
  const invoice = purchase.invoices?.[0]
  const openInvoice = () =>
    invoice &&
    openPdf(invoice.id).catch(() =>
      showErrorToast("Impossible d'ouvrir la facture"),
    )
  const write = (label: string) => (
    <QuickAction
      icon={Mail}
      label={label}
      disabled={writing}
      onClick={onWrite}
    />
  )

  if (purchase.status === "paid")
    return (
      <QuickActions>
        {invoice && (
          <QuickAction icon={Receipt} label="Facture" onClick={openInvoice} />
        )}
        <QuickAction
          icon={RotateCcw}
          label="Pas payé"
          pending={unpay.isPending}
          onClick={() => unpay.mutate()}
        />
      </QuickActions>
    )
  if (purchase.status === "to_pay")
    return (
      <QuickActions>
        <QuickAction
          icon={Check}
          label={credit ? "Déduit" : "Payé"}
          pending={pay.isPending}
          onClick={() => pay.mutate()}
        />
        {invoice && (
          <QuickAction
            icon={Receipt}
            label={credit ? "Avoir" : "Facture"}
            onClick={openInvoice}
          />
        )}
        {purchase.settled_at && (
          <QuickAction
            icon={RotateCcw}
            label="Rouvrir"
            pending={reopen.isPending}
            onClick={() => reopen.mutate()}
          />
        )}
      </QuickActions>
    )
  if (purchase.status === "dispute")
    return (
      <QuickActions>
        {write("Écrire")}
        {!purchase.paid_at && (
          <QuickAction
            icon={Check}
            label="Réglé"
            pending={settle.isPending}
            onClick={() => settle.mutate()}
          />
        )}
      </QuickActions>
    )
  if (purchase.late) return <QuickActions>{write("Relancer")}</QuickActions>
  return null
}

export function PurchaseSheet({
  purchase,
  unlinked = [],
  open,
  onOpenChange,
}: {
  purchase: Purchase | undefined
  unlinked?: UnlinkedDocument[]
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
  const canWrite =
    purchase.status === "dispute" ||
    (purchase.status === "waiting" && !!purchase.late)
  return (
    <ResponsiveSheet
      open={open}
      onOpenChange={(next) => {
        if (!next) setWriting(null)
        onOpenChange(next)
      }}
      title={purchaseTitle(purchase)}
      description={purchaseSubtitle(purchase)}
    >
      <div className="flex flex-col gap-6">
        <Verdict purchase={purchase} />
        <Actions
          purchase={purchase}
          writing={writing === purchase.key}
          onWrite={() => setWriting(purchase.key)}
        />
        <LinkProposals purchase={purchase} unlinked={unlinked} />
        <Reasons purchase={purchase} />
        {writing === purchase.key && canWrite && (
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
                    <LineRow line={line} purchase={purchase} />
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
