import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import {
  Camera,
  Clock,
  FileWarning,
  Hourglass,
  Link2,
  Plus,
  TriangleAlert,
  Upload,
} from "lucide-react"
import { type DragEvent, type ReactNode, useState } from "react"

import type { Purchase } from "@/client"
import { EmptyState } from "@/components/App/EmptyState"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { DemoBanner, isDemoUser } from "@/components/App/Navigation"
import {
  BigAmount,
  QuickAction,
  QuickActions,
} from "@/components/App/QuickAction"
import { UploadButton, useFilePicker } from "@/components/App/UploadButton"
import {
  overbilled,
  PurchaseRow,
  shortReason,
} from "@/components/Purchases/PurchaseRow"
import { PurchaseSheet } from "@/components/Purchases/PurchaseSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import useAuth from "@/hooks/useAuth"
import {
  daysUntil,
  formatAmount,
  isBusy,
  needsReview,
  plural,
} from "@/lib/documents"
import { documentsQuery, purchasesQuery, useLiveOptions } from "@/lib/queries"

export const Route = createFileRoute("/_layout/")({
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(documentsQuery),
      context.queryClient.ensureQueryData(purchasesQuery),
    ]),
  component: Home,
  head: () => ({ meta: [{ title: "Accueil - Factures IA" }] }),
})

// Files can be dropped anywhere on the page from a computer.
function DropTarget({ children }: { children: ReactNode }) {
  const { upload } = useFilePicker()
  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: mouse-only drop target; the buttons are the keyboard path
    <div
      className="flex flex-col gap-8"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event: DragEvent) => {
        event.preventDefault()
        upload(Array.from(event.dataTransfer.files))
      }}
    >
      {children}
    </div>
  )
}

function HomeActions({ disputes }: { disputes: number }) {
  const navigate = useNavigate()
  const files = useFilePicker()
  const photo = useFilePicker({ camera: true })
  return (
    <QuickActions>
      {files.picker}
      {photo.picker}
      <QuickAction
        icon={Plus}
        label="Ajouter"
        onClick={files.open}
        pending={files.isPending}
      />
      <QuickAction
        icon={Camera}
        label="Photo"
        onClick={photo.open}
        pending={photo.isPending}
      />
      <QuickAction
        icon={TriangleAlert}
        label={disputes > 0 ? `Litiges (${disputes})` : "Litiges"}
        onClick={() =>
          navigate({ to: "/reconciliations", search: { filter: "dispute" } })
        }
      />
    </QuickActions>
  )
}

function FirstVisit() {
  return (
    <DropTarget>
      <EmptyState
        icon={Upload}
        title="Déposez vos documents"
        description="Commandes, bons de livraison et factures, en PDF ou en photo, tout en vrac."
      >
        <UploadButton>Choisir des fichiers</UploadButton>
      </EmptyState>
    </DropTarget>
  )
}

function Home() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const live = useLiveOptions()
  const { data: documents } = useSuspenseQuery(live.documents)
  const { data: purchases } = useSuspenseQuery(live.purchases)
  const [selected, setSelected] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  if (documents.count === 0) return <FirstVisit />

  const list = purchases.data
  // Sorted by the server: the soonest due first.
  const toPay = list.filter((p) => p.status === "to_pay")
  const disputes = list.filter((p) => p.status === "dispute")
  const waiting = list.filter((p) => p.status === "waiting" && !p.late)
  const late = list.filter((p) => p.late)
  const reading = documents.data.filter(isBusy).length
  // A document only waiting to be filed is counted once, among those to file.
  const toFile = new Set(purchases.unlinked.map((d) => d.id))
  const review = documents.data.filter(
    (d) => needsReview(d) && !toFile.has(d.id),
  ).length
  const sum = (items: Purchase[]) =>
    items.reduce((total, p) => total + Number(p.to_pay_incl_tax ?? 0), 0)
  const payable = sum(toPay)
  const overdue = toPay.filter(
    (p) =>
      p.due_date && daysUntil(p.due_date) < 0 && Number(p.to_pay_incl_tax) > 0,
  )
  const extra = disputes.reduce((total, p) => total + overbilled(p), 0)
  const name = isDemoUser(user) ? "" : (user?.full_name ?? "").split(" ")[0]

  const open = (purchase: Purchase) => {
    setSelected(purchase.key)
    setSheetOpen(true)
  }
  const go = (filter: "dispute" | "waiting" | "to_pay") =>
    navigate({ to: "/reconciliations", search: { filter } })

  const todo = [
    disputes.length > 0 && (
      <ListRow
        key="dispute"
        icon={TriangleAlert}
        title={plural(disputes.length, "litige", "litiges")}
        subtitle={
          extra > 0.02
            ? `${formatAmount(extra)} facturés en trop`
            : "Un point bloque le paiement"
        }
        chevron
        onClick={() => go("dispute")}
      />
    ),
    late.length > 0 && (
      <ListRow
        key="late"
        icon={Clock}
        title={plural(
          late.length,
          "livraison en retard",
          "livraisons en retard",
        )}
        subtitle="Pas encore reçues : relancez le fournisseur"
        chevron
        onClick={() => go("waiting")}
      />
    ),
    purchases.unlinked.length > 0 && (
      <ListRow
        key="unlinked"
        icon={Link2}
        title={plural(
          purchases.unlinked.length,
          "document à ranger",
          "documents à ranger",
        )}
        subtitle="Sans numéro de commande : touchez pour les ranger"
        chevron
        onClick={() => go("waiting")}
      />
    ),
    waiting.length > 0 && (
      <ListRow
        key="waiting"
        icon={Hourglass}
        title={plural(waiting.length, "achat en attente", "achats en attente")}
        subtitle={
          waiting.length === 1
            ? shortReason(waiting[0].notes?.[0] ?? "Il manque un document")
            : "Il manque une livraison, une facture ou une vérification"
        }
        chevron
        onClick={() => go("waiting")}
      />
    ),
    review > 0 && (
      <ListRow
        key="review"
        icon={FileWarning}
        title={plural(review, "document à vérifier", "documents à vérifier")}
        subtitle="L'IA a un doute"
        chevron
        onClick={() =>
          navigate({ to: "/documents", search: { filter: "review" } })
        }
      />
    ),
  ].filter(Boolean)

  return (
    <DropTarget>
      <DemoBanner />
      <section className="flex flex-col items-center gap-2 pt-2 text-center">
        <p className="text-sm text-muted-foreground">
          {name ? `Bonjour ${name}, il reste à payer` : "Reste à payer"}
        </p>
        <BigAmount text={formatAmount(payable)} />
        <p className="text-sm text-muted-foreground">
          TTC ·{" "}
          {toPay.length > 0
            ? plural(toPay.length, "achat vérifié", "achats vérifiés")
            : "rien de prêt à payer"}
        </p>
        {overdue.length > 0 && (
          <p className="text-sm text-destructive">
            Dont {formatAmount(sum(overdue))} en retard de paiement
          </p>
        )}
      </section>

      <HomeActions disputes={disputes.length} />

      {reading > 0 && (
        <Alert>
          <Spinner />
          <AlertTitle>
            L'IA lit {plural(reading, "document", "documents")}
          </AlertTitle>
          <AlertDescription>
            La page se met à jour toute seule.
          </AlertDescription>
        </Alert>
      )}

      {todo.length > 0 && <ListGroup title="À regarder">{todo}</ListGroup>}

      {toPay.length > 0 && (
        <ListGroup
          title="Prochains paiements"
          action={
            <Button variant="link" size="sm" asChild>
              <Link to="/reconciliations" search={{ filter: "to_pay" }}>
                Tout voir
              </Link>
            </Button>
          }
        >
          {toPay.slice(0, 5).map((purchase) => (
            <PurchaseRow
              key={purchase.key}
              purchase={purchase}
              onClick={() => open(purchase)}
            />
          ))}
        </ListGroup>
      )}

      <PurchaseSheet
        purchase={list.find((p) => p.key === selected)}
        unlinked={purchases.unlinked}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </DropTarget>
  )
}
