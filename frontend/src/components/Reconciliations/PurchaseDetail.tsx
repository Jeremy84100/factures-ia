import { FileText } from "lucide-react"

import type { DocumentRef, Purchase } from "@/client"
import { openPdf } from "@/components/Documents/DocumentActionsMenu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  formatAmount,
  formatDate,
  formatQuantity,
  KIND,
  PURCHASE_STATUS,
} from "@/lib/documents"
import { cn } from "@/lib/utils"

function DocumentLink({ document }: { document: DocumentRef }) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => openPdf(document.id)}
      title={document.filename}
    >
      <FileText />
      {KIND[document.kind]} {document.number ?? document.filename}
      <span className="text-muted-foreground">
        {formatDate(document.document_date)}
      </span>
    </Button>
  )
}

export function PurchaseDetail({ purchase }: { purchase: Purchase }) {
  const { label, variant } = PURCHASE_STATUS[purchase.status]
  const documents = [
    ...(purchase.orders ?? []),
    ...(purchase.deliveries ?? []),
    ...(purchase.invoices ?? []),
  ]

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          Détail
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            Commande {purchase.order_reference}
            <Badge variant={variant}>{label}</Badge>
          </DialogTitle>
          <DialogDescription>{purchase.supplier ?? "—"}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap gap-2">
          {documents.map((document) => (
            <DocumentLink key={document.id} document={document} />
          ))}
        </div>

        {(purchase.issues?.length ?? 0) > 0 && (
          <ul className="list-disc rounded-md bg-destructive/10 p-3 pl-7 text-sm">
            {purchase.issues?.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        )}
        {(purchase.notes?.length ?? 0) > 0 && (
          <ul className="list-disc rounded-md bg-muted p-3 pl-7 text-sm text-muted-foreground">
            {purchase.notes?.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        )}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Article</TableHead>
              <TableHead className="text-right">Commandé</TableHead>
              <TableHead className="text-right">Livré</TableHead>
              <TableHead className="text-right">Facturé</TableHead>
              <TableHead className="text-right">Prix commandé</TableHead>
              <TableHead className="text-right">Prix facturé</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(purchase.lines ?? []).map((line) => {
              const issues = line.issues ?? []
              const notes = line.notes ?? []
              const flagged = (word: string) =>
                issues.some((issue) => issue.includes(word))
              const cell = (word: string) =>
                cn(
                  "text-right tabular-nums",
                  flagged(word) && "font-semibold text-destructive",
                )
              return (
                <TableRow
                  key={`${line.reference}-${line.label}`}
                  className={cn(issues.length > 0 && "bg-destructive/5")}
                >
                  <TableCell className="whitespace-normal">
                    <div className="font-medium">{line.label}</div>
                    {line.reference && (
                      <div className="font-mono text-xs text-muted-foreground">
                        {line.reference}
                      </div>
                    )}
                    {[...issues, ...notes].map((text) => (
                      <div
                        key={text}
                        className={cn(
                          "text-xs",
                          issues.includes(text)
                            ? "text-destructive"
                            : "text-muted-foreground",
                        )}
                      >
                        {text.slice(text.indexOf(" : ") + 3)}
                      </div>
                    ))}
                  </TableCell>
                  <TableCell className={cell("commandé")}>
                    {formatQuantity(line.ordered)}
                  </TableCell>
                  <TableCell className={cell("livré")}>
                    {formatQuantity(line.delivered)}
                  </TableCell>
                  <TableCell className={cell("facturé")}>
                    {formatQuantity(line.invoiced)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {formatAmount(line.order_price)}
                  </TableCell>
                  <TableCell className={cell("prix")}>
                    {formatAmount(line.invoice_price)}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </DialogContent>
    </Dialog>
  )
}
