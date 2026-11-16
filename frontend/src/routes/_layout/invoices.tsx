import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { FileText } from "lucide-react"
import { Suspense, useState } from "react"

import { type InvoiceStatus, InvoicesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { columns } from "@/components/Invoices/columns"
import UploadInvoices from "@/components/Invoices/UploadInvoices"
import PendingInvoices from "@/components/Pending/PendingInvoices"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { isBusy } from "@/lib/invoices"

const FILTERS: { value: InvoiceStatus | "all"; label: string }[] = [
  { value: "all", label: "Toutes" },
  { value: "to_check", label: "À vérifier" },
  { value: "unreadable", label: "Illisibles" },
  { value: "failed", label: "Erreurs IA" },
  { value: "ok", label: "Validées" },
]

function getInvoicesQueryOptions(status: InvoiceStatus | "all") {
  return {
    queryFn: async () =>
      (
        await InvoicesService.readInvoices({
          query: {
            skip: 0,
            limit: 500,
            status: status === "all" ? undefined : status,
          },
        })
      ).data,
    queryKey: ["invoices", status],
  }
}

export const Route = createFileRoute("/_layout/invoices")({
  component: Invoices,
  head: () => ({
    meta: [{ title: "Factures - Factures IA" }],
  }),
})

function InvoicesTableContent({ status }: { status: InvoiceStatus | "all" }) {
  const { data: invoices } = useSuspenseQuery({
    ...getInvoicesQueryOptions(status),
    refetchInterval: (query) =>
      query.state.data?.data.some(isBusy) ? 2000 : false,
  })

  if (invoices.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4 rounded-full bg-muted p-4">
          <FileText className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">Aucune facture ici</h3>
        <p className="text-muted-foreground">
          Déposez des PDF : ils sont lus, vérifiés et rangés automatiquement.
        </p>
      </div>
    )
  }

  return <DataTable columns={columns} data={invoices.data} />
}

function Invoices() {
  const [status, setStatus] = useState<InvoiceStatus | "all">("all")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Factures</h1>
          <p className="text-muted-foreground">
            Lues par l'IA, vérifiées automatiquement, corrigeables à la main
          </p>
        </div>
        <UploadInvoices />
      </div>
      <Tabs
        value={status}
        onValueChange={(value) => setStatus(value as InvoiceStatus | "all")}
      >
        <TabsList>
          {FILTERS.map(({ value, label }) => (
            <TabsTrigger key={value} value={value}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Suspense fallback={<PendingInvoices />}>
        <InvoicesTableContent status={status} />
      </Suspense>
    </div>
  )
}
