import type { InvoicePublic, InvoiceStatus } from "@/client"

export const STATUS: Record<
  InvoiceStatus,
  {
    label: string
    variant: "default" | "secondary" | "destructive" | "outline"
  }
> = {
  pending: { label: "En attente", variant: "outline" },
  processing: { label: "Lecture…", variant: "outline" },
  ok: { label: "Validée", variant: "default" },
  to_check: { label: "À vérifier", variant: "secondary" },
  unreadable: { label: "Illisible", variant: "destructive" },
  failed: { label: "Erreur IA", variant: "destructive" },
}

export const isBusy = (invoice: InvoicePublic) =>
  invoice.status === "pending" || invoice.status === "processing"

export function formatAmount(
  value: string | number | null | undefined,
  currency = "EUR",
) {
  if (value === null || value === undefined || value === "") return "—"
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: currency || "EUR",
  }).format(Number(value))
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "—"
  return new Date(`${value}T00:00:00`).toLocaleDateString("fr-FR")
}
