import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"

import { InvoicesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
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
import useAuth from "@/hooks/useAuth"
import { formatAmount } from "@/lib/invoices"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [{ title: "Tableau de bord - Factures IA" }],
  }),
})

const YEAR = new Date().getFullYear()

function useCount(status: "to_check" | "unreadable" | "failed" | "ok") {
  return useQuery({
    queryKey: ["invoices", "count", status],
    queryFn: async () =>
      (await InvoicesService.readInvoices({ query: { status, limit: 1 } })).data
        .count,
  })
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl tabular-nums">{value ?? "…"}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function Dashboard() {
  const { user: currentUser } = useAuth()
  const ok = useCount("ok")
  const toCheck = useCount("to_check")
  const unreadable = useCount("unreadable")
  const failed = useCount("failed")
  const totals = useQuery({
    queryKey: ["invoices", "totals", YEAR],
    queryFn: async () =>
      (await InvoicesService.readSupplierTotals({ query: { year: YEAR } }))
        .data,
  })

  const problems = (unreadable.data ?? 0) + (failed.data ?? 0)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="max-w-sm truncate text-2xl">
          Bonjour {currentUser?.full_name || currentUser?.email}
        </h1>
        <p className="text-muted-foreground">Où en sont vos factures</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Validées" value={ok.data} />
        <Stat label="À vérifier" value={toCheck.data} />
        <Stat label="Illisibles ou en erreur" value={problems} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Dépenses {YEAR} par fournisseur</CardTitle>
          <CardDescription>Factures validées uniquement, TTC</CardDescription>
        </CardHeader>
        <CardContent>
          {totals.data && totals.data.data.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fournisseur</TableHead>
                  <TableHead className="text-right">Factures</TableHead>
                  <TableHead className="text-right">Total TTC</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {totals.data.data.map((row) => (
                  <TableRow key={row.supplier}>
                    <TableCell className="font-medium">
                      {row.supplier}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.count}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatAmount(row.total_incl_tax)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-start gap-3">
              <p className="text-muted-foreground">
                Aucune facture validée cette année.
              </p>
              <Button asChild>
                <Link to="/invoices">Déposer des factures</Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
