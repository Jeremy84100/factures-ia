import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import {
  ChevronRight,
  Clock,
  FileWarning,
  Hourglass,
  Link2,
  TriangleAlert,
  Upload,
} from "lucide-react"
import { type DragEvent, useState } from "react"

import type { Purchase } from "@/client"
import { EmptyState } from "@/components/App/EmptyState"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { displayName, isDemoUser } from "@/components/App/Navigation"
import { UploadButton, useFilePicker } from "@/components/App/UploadButton"
import { overbilled, PurchaseRow } from "@/components/Purchases/PurchaseRow"
import { PurchaseSheet } from "@/components/Purchases/PurchaseSheet"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import useAuth from "@/hooks/useAuth"
import { formatAmount, isBusy, needsReview, plural } from "@/lib/documents"
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

// shadcn Empty with a border, as in its examples. Files can also be dropped
// anywhere on it.
function DropZone() {
  const { upload } = useFilePicker()
  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: mouse-only drop target; the button inside is the keyboard path
    <div
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event: DragEvent) => {
        event.preventDefault()
        upload(Array.from(event.dataTransfer.files))
      }}
    >
      <EmptyState
        icon={Upload}
        title="Déposez vos documents"
        description="Commandes, bons de livraison et factures, en PDF ou en photo, tout en vrac. Glissez-les ici ou choisissez-les."
        className="border"
      >
        <UploadButton variant="outline">Choisir des fichiers</UploadButton>
      </EmptyState>
    </div>
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

  if (documents.count === 0) return <DropZone />

  const list = purchases.data
  const toPay = list.filter((p) => p.status === "to_pay")
  const disputes = list.filter((p) => p.status === "dispute")
  const waiting = list.filter((p) => p.status === "waiting")
  const late = list.filter((p) => p.late)
  const reading = documents.data.filter(isBusy).length
  const review = documents.data.filter(needsReview).length
  const payable = toPay.reduce(
    (sum, p) => sum + Number(p.invoiced_excl_tax ?? 0),
    0,
  )
  const extra = disputes.reduce((sum, p) => sum + overbilled(p), 0)
  const name = isDemoUser(user)
    ? ""
    : displayName(user ?? undefined).split(" ")[0]

  const open = (purchase: Purchase) => {
    setSelected(purchase.key)
    setSheetOpen(true)
  }
  const go = (filter: "dispute" | "waiting" | "late" | "unlinked") =>
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
        actions={<ChevronRight />}
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
        subtitle="Après la date promise"
        actions={<ChevronRight />}
        onClick={() => go("late")}
      />
    ),
    purchases.unlinked.length > 0 && (
      <ListRow
        key="unlinked"
        icon={Link2}
        title={plural(
          purchases.unlinked.length,
          "document à relier",
          "documents à relier",
        )}
        subtitle="Sans numéro de commande"
        actions={<ChevronRight />}
        onClick={() => go("unlinked")}
      />
    ),
    waiting.length > 0 && (
      <ListRow
        key="waiting"
        icon={Hourglass}
        title={plural(waiting.length, "achat en attente", "achats en attente")}
        subtitle="Livraison ou facture manquante"
        actions={<ChevronRight />}
        onClick={() => go("waiting")}
      />
    ),
    review > 0 && (
      <ListRow
        key="review"
        icon={FileWarning}
        title={plural(review, "document à vérifier", "documents à vérifier")}
        subtitle="L'IA a un doute"
        actions={<ChevronRight />}
        onClick={() =>
          navigate({ to: "/documents", search: { filter: "review" } })
        }
      />
    ),
  ].filter(Boolean)

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardDescription>
            {name ? `Bonjour ${name}, vous` : "Vous"} pouvez payer
          </CardDescription>
          <CardTitle className="text-3xl tabular-nums">
            {formatAmount(payable)}
          </CardTitle>
        </CardHeader>
        <CardFooter className="text-sm text-muted-foreground">
          Hors taxes ·{" "}
          {toPay.length > 0
            ? `${plural(toPay.length, "achat vérifié", "achats vérifiés")} ligne par ligne`
            : "aucun achat complet pour l'instant"}
        </CardFooter>
      </Card>

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
          title="Bons à payer"
          action={
            <Button variant="link" size="sm" asChild>
              <Link to="/reconciliations" search={{ filter: "to_pay" }}>
                Tout voir
              </Link>
            </Button>
          }
        >
          {toPay.slice(0, 4).map((purchase) => (
            <PurchaseRow
              key={purchase.key}
              purchase={purchase}
              onClick={() => open(purchase)}
            />
          ))}
        </ListGroup>
      )}

      <DropZone />

      <PurchaseSheet
        purchase={list.find((p) => p.key === selected)}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  )
}
