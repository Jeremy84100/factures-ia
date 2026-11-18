import { useMutation, useSuspenseQuery } from "@tanstack/react-query"
import { Download } from "lucide-react"
import { useState } from "react"

import { DocumentsService } from "@/client"
import DeleteAllDocuments from "@/components/Documents/DeleteAllDocuments"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import useCustomToast from "@/hooks/useCustomToast"
import { documentsQuery } from "@/lib/queries"
import { handleError } from "@/utils"
import DeleteAccount from "./DeleteAccount"

const ALL = "all"

const monthName = (month: string) =>
  new Date(`${month}-01T00:00:00`).toLocaleDateString("fr-FR", {
    month: "long",
    year: "numeric",
  })

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

// The invoices and their PDFs in one zip, for the accountant.
function ExportInvoices() {
  const { data } = useSuspenseQuery(documentsQuery)
  const { showErrorToast } = useCustomToast()
  const months = [
    ...new Set(
      data.data
        .filter((d) => d.kind === "invoice" && d.document_date)
        .map((d) => (d.document_date ?? "").slice(0, 7)),
    ),
  ]
    .sort()
    .reverse()
  const [month, setMonth] = useState(ALL)
  const download = useMutation({
    mutationFn: async () =>
      (
        await DocumentsService.exportInvoices({
          query: month === ALL ? {} : { month },
          responseType: "blob",
        })
      ).data as Blob,
    onSuccess: (blob) =>
      save(blob, `factures-${month === ALL ? "toutes" : month}.zip`),
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pour le comptable</CardTitle>
        <CardDescription>
          Un tableau des factures (échéance, date de paiement) et leurs PDF,
          dans un seul fichier à lui envoyer.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Field>
          <FieldLabel htmlFor="export-month">Période</FieldLabel>
          <Select value={month} onValueChange={setMonth}>
            <SelectTrigger id="export-month">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Toutes les factures</SelectItem>
              {months.map((value) => (
                <SelectItem key={value} value={value}>
                  {monthName(value)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </CardContent>
      <CardFooter>
        <Button
          disabled={months.length === 0 || download.isPending}
          onClick={() => download.mutate()}
        >
          {download.isPending ? (
            <Spinner data-icon="inline-start" />
          ) : (
            <Download data-icon="inline-start" />
          )}
          Télécharger
        </Button>
      </CardFooter>
    </Card>
  )
}

function DeleteDocuments() {
  const { data } = useSuspenseQuery(documentsQuery)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Supprimer mes documents</CardTitle>
        <CardDescription>
          Efface tous les documents déposés, en gardant le compte.
        </CardDescription>
      </CardHeader>
      <CardFooter>
        {data.count > 0 ? (
          <DeleteAllDocuments count={data.count} />
        ) : (
          <p className="text-sm text-muted-foreground">Aucun document.</p>
        )}
      </CardFooter>
    </Card>
  )
}

const MyData = () => (
  <div className="flex flex-col gap-6">
    <ExportInvoices />
    <DeleteDocuments />
    <DeleteAccount />
  </div>
)

export default MyData
