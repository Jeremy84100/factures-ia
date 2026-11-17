import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { FileText } from "lucide-react"
import { Suspense, useState } from "react"

import {
  type DocumentKind,
  type DocumentStatus,
  DocumentsService,
} from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { columns } from "@/components/Documents/columns"
import UploadDocuments from "@/components/Documents/UploadDocuments"
import PendingDocuments from "@/components/Pending/PendingDocuments"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { isBusy } from "@/lib/documents"

type Filter = { kind?: DocumentKind; status?: DocumentStatus }

const FILTERS: { value: string; label: string; filter: Filter }[] = [
  { value: "all", label: "Tous", filter: {} },
  { value: "invoice", label: "Factures", filter: { kind: "invoice" } },
  { value: "order", label: "Commandes", filter: { kind: "order" } },
  { value: "delivery", label: "Livraisons", filter: { kind: "delivery" } },
  { value: "to_check", label: "À vérifier", filter: { status: "to_check" } },
  {
    value: "unreadable",
    label: "Illisibles",
    filter: { status: "unreadable" },
  },
  { value: "failed", label: "Erreurs IA", filter: { status: "failed" } },
]

function getDocumentsQueryOptions(value: string) {
  const { filter } = FILTERS.find((f) => f.value === value) ?? FILTERS[0]
  return {
    queryFn: async () =>
      (
        await DocumentsService.readDocuments({
          query: { skip: 0, limit: 500, ...filter },
        })
      ).data,
    queryKey: ["documents", value],
  }
}

export const Route = createFileRoute("/_layout/documents")({
  component: Documents,
  head: () => ({
    meta: [{ title: "Documents - Factures IA" }],
  }),
})

function DocumentsTableContent({ value }: { value: string }) {
  const { data: documents } = useSuspenseQuery({
    ...getDocumentsQueryOptions(value),
    refetchInterval: (query) =>
      query.state.data?.data.some(isBusy) ? 2000 : false,
  })

  if (documents.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-muted p-4">
          <FileText className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">Aucun document ici</h3>
        <p className="text-muted-foreground">
          Déposez des factures, bons de commande et bons de livraison en vrac :
          ils sont triés, lus et vérifiés automatiquement.
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={documents.data} />
}

function Documents() {
  const [value, setValue] = useState("all")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Documents</h1>
          <p className="text-muted-foreground">
            Factures, commandes et livraisons, triées et lues par l'IA,
            vérifiées automatiquement
          </p>
        </div>
        <UploadDocuments />
      </div>
      <Tabs value={value} onValueChange={setValue}>
        <TabsList>
          {FILTERS.map(({ value, label }) => (
            <TabsTrigger key={value} value={value}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Suspense fallback={<PendingDocuments />}>
        <DocumentsTableContent value={value} />
      </Suspense>
    </div>
  )
}
