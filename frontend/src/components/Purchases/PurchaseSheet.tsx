import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Check,
  ChevronRight,
  CircleCheck,
  ClipboardList,
  Copy,
  Info,
  Link2,
  Mail,
  Receipt,
  RotateCcw,
  ShieldAlert,
  TriangleAlert,
  Truck,
} from "lucide-react"
import { type ReactNode, useState } from "react"

import {
  type DocumentRef,
  DocumentsService,
  type LineMatch,
  type Purchase,
  ReconciliationsService,
  type UnlinkedDocument,
} from "@/client"
import { ResponsiveSheet } from "@/components/App/ResponsiveSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Item,
  ItemActions,
  ItemContent,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item"
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
  afterLabel,
  days,
  daysUntil,
  formatAmount,
  formatDate,
  formatQuantity,
  groupIban,
  KIND_LONG,
  PURCHASE_STATUS,
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
      ? `TTC, échéance du ${date} dépassée de ${days(-left)} : le fournisseur peut réclamer 40 € d'indemnité`
      : left === 0
        ? "TTC, à payer aujourd'hui"
        : `TTC, à payer avant le ${date}`
  return purchase.due_date_assumed
    ? `${when} (délai légal de 30 jours : aucune échéance sur la facture)`
    : when
}

// What the purchase comes to, in three short lines.
function verdict(purchase: Purchase): [string, string, string | null] {
  const extra = overbilled(purchase)
  const toPay = Number(purchase.to_pay_incl_tax ?? 0)
  const invoiced = purchase.invoiced_incl_tax ?? purchase.invoiced_excl_tax
  if (purchase.status === "paid")
    return [`Payé le ${paidOn(purchase)}`, formatAmount(invoiced), "TTC"]
  if (purchase.status === "to_pay" && isCredit(purchase))
    return [
      "Avoir à déduire",
      formatAmount(-toPay),
      "TTC, de votre prochain paiement à ce fournisseur",
    ]
  if (purchase.status === "to_pay")
    return ["À payer", formatAmount(toPay), dueText(purchase)]
  if (purchase.status === "dispute" && extra > 0.02)
    return [
      "Facturé en trop",
      formatAmount(extra),
      `TTC, sur ${formatAmount(invoiced)} facturés`,
    ]
  if (purchase.status === "dispute")
    return ["Litige", "À ne pas payer tout de suite", null]
  if (purchase.iban_warning)
    return ["En attente", "Ne payez pas avant d'avoir appelé", null]
  return ["En attente", "Pas encore payable", null]
}

function Summary({
  purchase,
  children,
}: {
  purchase: Purchase
  children: ReactNode
}) {
  const [label, amount, footer] = verdict(purchase)
  return (
    <section className="flex flex-col gap-1">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <PurchaseBadge purchase={purchase} />
        {label !== PURCHASE_STATUS[purchase.status].label && (
          <span>{label}</span>
        )}
      </div>
      <p
        className={
          footer
            ? "text-3xl font-semibold tracking-tight tabular-nums"
            : "text-lg font-semibold"
        }
      >
        {amount}
      </p>
      {footer && <p className="text-sm text-muted-foreground">{footer}</p>}
      {purchase.iban && purchase.status === "to_pay" && !isCredit(purchase) && (
        <p className="text-sm whitespace-nowrap text-muted-foreground">
          IBAN{" "}
          <span className="font-medium text-foreground tabular-nums">
            {groupIban(purchase.iban)}
          </span>
        </p>
      )}
      <div className="flex flex-wrap gap-2 pt-2">{children}</div>
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

type Column = {
  label: string
  short: string
  value: (line: LineMatch) => string
  word: string
}

// Only the columns this purchase has documents for.
function columnsOf(purchase: Purchase): Column[] {
  const columns: Column[] = []
  if (purchase.orders?.length)
    columns.push({
      label: "Commandé",
      short: "Cmd",
      value: (line) => formatQuantity(line.ordered),
      word: "commandé",
    })
  if (purchase.deliveries?.length)
    columns.push({
      label: "Livré",
      short: "Livré",
      value: (line) => (line.fee ? "—" : formatQuantity(line.delivered)),
      word: "livré",
    })
  if (purchase.invoices?.length)
    columns.push({
      label: "Facturé",
      short: "Fact.",
      value: (line) => formatQuantity(line.invoiced),
      word: "facturé",
    })
  return columns
}

// One article per row: its name, then what was ordered, delivered and
// invoiced on the same line, the figure at fault in red. Reference, price
// change and notes fit in one small line under the name.
function Articles({ purchase }: { purchase: Purchase }) {
  const settled = !!purchase.settled_at
  const columns = columnsOf(purchase)
  return (
    <section className="flex flex-col gap-2">
      <h2 className="px-1 text-sm font-semibold">Articles</h2>
      <Card size="sm" className="py-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="h-9 text-xs text-muted-foreground">
                Article
              </TableHead>
              {columns.map((column) => (
                <TableHead
                  key={column.label}
                  className="h-9 px-2 text-right text-xs text-muted-foreground"
                >
                  <span className="sm:hidden">{column.short}</span>
                  <span className="hidden sm:inline">{column.label}</span>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {purchase.lines?.map((line) => {
              const issues = settled ? [] : (line.issues ?? [])
              const notes = settled
                ? [...(line.issues ?? []), ...(line.notes ?? [])]
                : (line.notes ?? [])
              const flagged = (word: string) =>
                issues.some((issue) => issue.includes(word))
              const priceChanged =
                line.invoice_price != null &&
                line.order_price != null &&
                Number(line.invoice_price) !== Number(line.order_price)
              const price = line.invoice_price ?? line.order_price
              const details: { text: string; alert: boolean }[] = []
              if (line.reference)
                details.push({ text: line.reference, alert: false })
              if (priceChanged)
                details.push({
                  text: `prix ${formatAmount(line.order_price)} commandé, ${formatAmount(line.invoice_price)} facturé`,
                  alert: flagged("prix"),
                })
              else if (purchase.invoice_only && price != null)
                details.push({
                  text: `${formatAmount(price)} HT l'unité`,
                  alert: false,
                })
              if (line.fee && !purchase.invoice_only)
                details.push({
                  text: "frais, sur la quantité commandée",
                  alert: false,
                })
              for (const text of [...issues, ...notes])
                if (!text.includes("prix") && !REPEATS_FIGURES.test(text))
                  details.push({
                    text: afterLabel(text),
                    alert: issues.includes(text),
                  })
              return (
                <TableRow
                  key={`${line.reference}-${line.label}`}
                  className="hover:bg-transparent"
                >
                  <TableCell className="py-2 whitespace-normal">
                    <p className="font-medium">{line.label}</p>
                    {details.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {details.map((detail, index) => (
                          <span
                            key={detail.text}
                            className={
                              detail.alert ? "text-destructive" : undefined
                            }
                          >
                            {index > 0 && " · "}
                            {detail.text}
                          </span>
                        ))}
                      </p>
                    )}
                  </TableCell>
                  {columns.map((column) => (
                    <TableCell
                      key={column.label}
                      className={
                        flagged(column.word)
                          ? "px-2 py-2 text-right font-medium text-destructive tabular-nums"
                          : "px-2 py-2 text-right tabular-nums"
                      }
                    >
                      {column.value(line)}
                    </TableCell>
                  ))}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Card>
    </section>
  )
}

// The PDFs, one thin row each.
function Documents({ documents }: { documents: DocumentRef[] }) {
  const { showErrorToast } = useCustomToast()
  return (
    <section className="flex flex-col gap-2">
      <h2 className="px-1 text-sm font-semibold">Documents</h2>
      <Card size="sm" className="gap-0 py-1">
        <ItemGroup className="gap-0">
          {documents.map((document) => {
            const Icon =
              KIND_ICON[document.kind as keyof typeof KIND_ICON] ?? Receipt
            return (
              <Item key={document.id} size="sm" asChild>
                <button
                  type="button"
                  className="text-left active:bg-muted"
                  onClick={() =>
                    openPdf(document.id).catch(() =>
                      showErrorToast("Impossible d'ouvrir le document"),
                    )
                  }
                >
                  <ItemMedia variant="icon" className="text-muted-foreground">
                    <Icon />
                  </ItemMedia>
                  <ItemContent className="min-w-0">
                    <ItemTitle className="block w-full truncate font-normal">
                      {KIND_LONG[document.kind]} {document.number ?? ""}
                    </ItemTitle>
                  </ItemContent>
                  <ItemActions className="text-sm text-muted-foreground">
                    {formatDate(document.document_date)}
                    <ChevronRight className="size-4" />
                  </ItemActions>
                </button>
              </Item>
            )
          })}
        </ItemGroup>
      </Card>
    </section>
  )
}

function useRefresh() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ["purchases"] })
    queryClient.invalidateQueries({ queryKey: ["documents"] })
  }
}

// The fraud small firms meet most: a supplier who "changes bank". Nothing is
// paid until someone has called them on a number they already know.
function IbanWarning({ purchase }: { purchase: Purchase }) {
  const refresh = useRefresh()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const confirm = useMutation({
    mutationFn: (id: string) => DocumentsService.confirmIban({ path: { id } }),
    onSuccess: () => showSuccessToast("IBAN confirmé : la facture est à payer"),
    onError: handleError.bind(showErrorToast),
    onSettled: refresh,
  })
  if (!purchase.iban_warning || !purchase.iban_document_id) return null
  const id = purchase.iban_document_id
  return (
    <Alert variant="destructive">
      <ShieldAlert />
      <AlertTitle>Nouvel IBAN : ne payez pas sans appeler</AlertTitle>
      <AlertDescription>
        <p>
          {
            purchase.iban_warning
              .replace(/^Nouvel IBAN : /, "Il ")
              .split(". Appelez")[0]
          }
          .
        </p>
        <p>
          Appelez le fournisseur à un numéro que vous aviez déjà, pas celui de
          cette facture : un faux changement de RIB est l'arnaque la plus
          courante.
        </p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={confirm.isPending}
            onClick={() => confirm.mutate(id)}
          >
            J'ai appelé, l'IBAN est bon
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  )
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
  return (
    <>
      {proposals.map((document) => (
        <Alert key={document.id}>
          <Link2 />
          <AlertTitle>
            {KIND_LONG[document.kind]} {document.number} à ranger ici ?
          </AlertTitle>
          <AlertDescription>
            <p>
              Même fournisseur, daté du {formatDate(document.document_date)},
              sans numéro de commande.
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

function ActionButton({
  icon: Icon,
  label,
  onClick,
  pending,
  disabled,
  main,
}: {
  icon: typeof Check
  label: string
  onClick: () => void
  pending?: boolean
  disabled?: boolean
  main?: boolean
}) {
  return (
    <Button
      size="sm"
      variant={main ? "default" : "secondary"}
      disabled={disabled || pending}
      onClick={onClick}
    >
      {pending ? (
        <Spinner data-icon="inline-start" />
      ) : (
        <Icon data-icon="inline-start" />
      )}
      {label}
    </Button>
  )
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
  const { showSuccessToast, showErrorToast } = useCustomToast()
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
  const seeInvoice = invoice && (
    <ActionButton
      icon={Receipt}
      label={credit ? "Voir l'avoir" : "Voir la facture"}
      onClick={() =>
        openPdf(invoice.id).catch(() =>
          showErrorToast("Impossible d'ouvrir la facture"),
        )
      }
    />
  )
  const write = (label: string, main = false) => (
    <ActionButton
      icon={Mail}
      label={label}
      main={main}
      disabled={writing}
      onClick={onWrite}
    />
  )

  switch (purchase.status) {
    case "paid":
      return (
        <>
          {seeInvoice}
          <ActionButton
            icon={RotateCcw}
            label="Annuler le paiement"
            pending={unpay.isPending}
            onClick={() => unpay.mutate()}
          />
        </>
      )
    case "to_pay":
      return (
        <>
          <ActionButton
            icon={Check}
            label={credit ? "Marquer déduit" : "Marquer payé"}
            main
            pending={pay.isPending}
            onClick={() => pay.mutate()}
          />
          {purchase.iban && !credit && (
            <ActionButton
              icon={Copy}
              label="Copier l'IBAN"
              onClick={() =>
                navigator.clipboard
                  .writeText(purchase.iban ?? "")
                  .then(() => showSuccessToast("IBAN copié"))
                  .catch(() => showErrorToast("Impossible de copier l'IBAN"))
              }
            />
          )}
          {seeInvoice}
          {purchase.settled_at && (
            <ActionButton
              icon={RotateCcw}
              label="Rouvrir le litige"
              pending={reopen.isPending}
              onClick={() => reopen.mutate()}
            />
          )}
        </>
      )
    case "dispute":
      return (
        <>
          {write("Écrire au fournisseur", true)}
          {!purchase.paid_at && (
            <ActionButton
              icon={Check}
              label="Litige réglé"
              pending={settle.isPending}
              onClick={() => settle.mutate()}
            />
          )}
        </>
      )
    default:
      return purchase.late ? write("Relancer le fournisseur", true) : null
  }
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
      <div className="flex flex-col gap-5">
        <Summary purchase={purchase}>
          <Actions
            purchase={purchase}
            writing={writing === purchase.key}
            onWrite={() => setWriting(purchase.key)}
          />
        </Summary>
        <IbanWarning purchase={purchase} />
        <LinkProposals purchase={purchase} unlinked={unlinked} />
        <Reasons purchase={purchase} />
        {writing === purchase.key && canWrite && (
          <SupplierEmailSection purchaseKey={purchase.key} />
        )}
        {(purchase.lines?.length ?? 0) > 0 && <Articles purchase={purchase} />}
        <Documents documents={documents} />
      </div>
    </ResponsiveSheet>
  )
}
