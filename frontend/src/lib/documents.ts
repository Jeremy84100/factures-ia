import type { DocumentKind, DocumentStatus, PurchaseStatus } from "@/client"

type Variant = "default" | "secondary" | "destructive" | "outline"

export const STATUS: Record<
  DocumentStatus,
  { label: string; variant: Variant }
> = {
  pending: { label: "À lire", variant: "outline" },
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
  to_pay: { label: "À payer", variant: "default" },
  dispute: { label: "Litige", variant: "destructive" },
  waiting: { label: "En attente", variant: "outline" },
  paid: { label: "Payé", variant: "secondary" },
}

export const isBusy = (document: { status: DocumentStatus }) =>
  document.status === "pending" || document.status === "processing"

// French puts a narrow space between thousands, which some fonts draw almost
// invisible: a normal non-breaking space keeps "1 128,00 €" readable.
export const visibleSpaces = (text: string) => text.replace(/ /g, " ")

export function formatAmount(
  value: string | number | null | undefined,
  currency = "EUR",
) {
  if (value === null || value === undefined || value === "") return "—"
  return visibleSpaces(
    new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency: currency || "EUR",
    }).format(Number(value)),
  )
}

export function formatQuantity(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "—"
  return visibleSpaces(
    new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 }).format(
      Number(value),
    ),
  )
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "—"
  return new Date(`${value}T00:00:00`).toLocaleDateString("fr-FR")
}

export const KIND_LONG: Record<DocumentKind, string> = {
  unknown: "Document",
  invoice: "Facture",
  order: "Bon de commande",
  delivery: "Bon de livraison",
}

export const needsReview = (document: { status: DocumentStatus }) =>
  ["to_check", "unreadable", "failed"].includes(document.status)

export const plural = (count: number, one: string, many: string) =>
  `${count} ${count > 1 ? many : one}`

// "Ciment CEM II : facturé 50, livré 45" -> "facturé 50, livré 45"
export const afterLabel = (text: string) =>
  text.includes(" : ") ? text.slice(text.indexOf(" : ") + 3) : text

const DAY_MS = 86_400_000

const startOfDay = (value: Date) =>
  new Date(value.getFullYear(), value.getMonth(), value.getDate())

// Days from today to a "2026-11-20" date: negative once it is past.
export function daysUntil(value: string, today = new Date()) {
  const day = new Date(`${value}T00:00:00`)
  return Math.round((day.getTime() - startOfDay(today).getTime()) / DAY_MS)
}

export const days = (count: number) => plural(count, "jour", "jours")

// "avant le 20/11", "aujourd'hui", "en retard de 3 jours".
export function dueLabel(value: string | null | undefined) {
  if (!value) return null
  const left = daysUntil(value)
  if (left < 0) return { text: `${-left} j de retard`, late: true }
  if (left === 0) return { text: "aujourd'hui", late: false }
  const short = new Date(`${value}T00:00:00`).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
  })
  return { text: `avant le ${short}`, late: false }
}
