import type { DocumentKind, DocumentStatus, PurchaseStatus } from "@/client"

type Variant = "default" | "secondary" | "destructive" | "outline"

export const STATUS: Record<
  DocumentStatus,
  { label: string; variant: Variant }
> = {
  pending: { label: "En attente", variant: "outline" },
  processing: { label: "Lecture…", variant: "outline" },
  ok: { label: "Validé", variant: "default" },
  to_check: { label: "À vérifier", variant: "secondary" },
  unreadable: { label: "Illisible", variant: "destructive" },
  failed: { label: "Erreur IA", variant: "destructive" },
}

export const KIND: Record<DocumentKind, string> = {
  unknown: "Autre",
  invoice: "Facture",
  order: "Commande",
  delivery: "Livraison",
}

export const PURCHASE_STATUS: Record<
  PurchaseStatus,
  { label: string; variant: Variant }
> = {
  to_pay: { label: "Bon à payer", variant: "default" },
  dispute: { label: "Litige", variant: "destructive" },
  waiting: { label: "En attente", variant: "outline" },
  no_order: { label: "Sans commande", variant: "secondary" },
}

export const isBusy = (document: { status: DocumentStatus }) =>
  document.status === "pending" || document.status === "processing"

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

export function formatQuantity(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "—"
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 }).format(
    Number(value),
  )
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "—"
  return new Date(`${value}T00:00:00`).toLocaleDateString("fr-FR")
}
