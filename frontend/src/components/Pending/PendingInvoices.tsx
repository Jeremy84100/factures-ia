import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const HEADERS = ["Statut", "Fournisseur", "Numéro", "Date", "HT", "TTC"]

const PendingInvoices = () => (
  <Table>
    <TableHeader>
      <TableRow>
        {HEADERS.map((header) => (
          <TableHead key={header}>{header}</TableHead>
        ))}
        <TableHead>
          <span className="sr-only">Actions</span>
        </TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      {Array.from({ length: 5 }).map((_, index) => (
        <TableRow key={index}>
          {HEADERS.map((header) => (
            <TableCell key={header}>
              <Skeleton className="h-4 w-20" />
            </TableCell>
          ))}
          <TableCell>
            <div className="flex justify-end">
              <Skeleton className="size-8 rounded-md" />
            </div>
          </TableCell>
        </TableRow>
      ))}
    </TableBody>
  </Table>
)

export default PendingInvoices
