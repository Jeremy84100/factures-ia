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
import { Amount } from "@/components/App/Amount"
import { ListGroup, ListRow } from "@/components/App/ListRow"
import { displayName, isDemoUser } from "@/components/App/Navigation"
import { UploadButton, useFilePicker } from "@/components/App/UploadButton"
import { overbilled, PurchaseRow } from "@/components/Purchases/PurchaseRow"
import { PurchaseSheet } from "@/components/Purchases/PurchaseSheet"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item"
import { Spinner } from "@/components/ui/spinner"
import useAuth from "@/hooks/useAuth"
import { formatAmount, isBusy, needsReview, plural } from "@/lib/documents"
import { documentsQuery, purchasesQuery, useLiveOptions } from "@/lib/queries"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/")({
  loader: ({ context }) =>
    Promise.all([
      context.queryClient.ensureQueryData(documentsQuery),
      context.queryClient.ensureQueryData(purchasesQuery),
    ]),
  component: Home,
  head: () => ({ meta: [{ title: "Accueil - Factures IA" }] }),
})

// shadcn Empty with a dashed border: click to choose, or drop files on it.
function DropZone({ big = false }: { big?: boolean }) {
  const { picker, open, upload, isPending } = useFilePicker()
  const [over, setOver] = useState(false)
  return (
    <>
      {picker}
      <Empty
        role="button"
        tabIndex={0}
        onClick={open}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") open()
        }}
        onDragOver={(event) => {
          event.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event: DragEvent) => {
          event.preventDefault()
          setOver(false)
          upload(Array.from(event.dataTransfer.files))
        }}
        className={cn(
          "cursor-pointer border border-dashed transition-colors hover:border-foreground/30 hover:bg-muted/40",
          big ? "py-16" : "hidden md:flex",
          over && "border-foreground/40 bg-muted/60",
        )}
      >
        <EmptyHeader>
          <EmptyMedia variant="icon">
            {isPending ? <Spinner /> : <Upload />}
          </EmptyMedia>
          <EmptyTitle>
            {isPending ? "Envoi…" : "Glissez vos documents ici"}
          </EmptyTitle>
          <EmptyDescription>
            Commandes, bons de livraison, factures · PDF ou photo · tout en vrac
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    </>
  )
}

function Welcome() {
  return (
    <div className="flex flex-col gap-8 pt-4 md:pt-10">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold md:text-4xl">
          Déposez vos premiers documents
        </h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          Mettez ensemble la commande, le bon de livraison et la facture d'un
          même achat. L'IA les trie, les lit et vous dit si vous pouvez payer.
        </p>
      </div>
      <DropZone big />
      <UploadButton className="h-14 w-full text-base md:hidden">
        Choisir des documents ou des photos
      </UploadButton>
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

  if (documents.count === 0) return <Welcome />

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
        tone="danger"
        title={plural(disputes.length, "litige", "litiges")}
        subtitle={
          extra > 0.02
            ? `${formatAmount(extra)} facturés en trop`
            : "Un point bloque le paiement"
        }
        end={<ChevronRight className="size-5 text-muted-foreground" />}
        onClick={() => go("dispute")}
      />
    ),
    late.length > 0 && (
      <ListRow
        key="late"
        icon={Clock}
        tone="warning"
        title={plural(
          late.length,
          "livraison en retard",
          "livraisons en retard",
        )}
        subtitle="Après la date promise"
        end={<ChevronRight className="size-5 text-muted-foreground" />}
        onClick={() => go("late")}
      />
    ),
    purchases.unlinked.length > 0 && (
      <ListRow
        key="unlinked"
        icon={Link2}
        tone="info"
        title={plural(
          purchases.unlinked.length,
          "document à relier",
          "documents à relier",
        )}
        subtitle="Sans numéro de commande"
        end={<ChevronRight className="size-5 text-muted-foreground" />}
        onClick={() => go("unlinked")}
      />
    ),
    waiting.length > 0 && (
      <ListRow
        key="waiting"
        icon={Hourglass}
        title={plural(waiting.length, "achat en attente", "achats en attente")}
        subtitle="Livraison ou facture manquante"
        end={<ChevronRight className="size-5 text-muted-foreground" />}
        onClick={() => go("waiting")}
      />
    ),
    review > 0 && (
      <ListRow
        key="review"
        icon={FileWarning}
        tone="warning"
        title={plural(review, "document à vérifier", "documents à vérifier")}
        subtitle="L'IA a un doute"
        end={<ChevronRight className="size-5 text-muted-foreground" />}
        onClick={() =>
          navigate({ to: "/documents", search: { filter: "review" } })
        }
      />
    ),
  ].filter(Boolean)

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-1 pt-2 md:pt-4">
        <span className="text-muted-foreground">
          {name ? `Bonjour ${name}, vous` : "Vous"} pouvez payer
        </span>
        <Amount value={payable} className="text-5xl md:text-6xl" />
        <span className="text-muted-foreground">
          hors taxes ·{" "}
          {toPay.length > 0
            ? `${plural(toPay.length, "achat vérifié", "achats vérifiés")} ligne par ligne`
            : "aucun achat complet pour l'instant"}
        </span>
      </section>

      {reading > 0 && (
        <Item variant="muted" size="sm">
          <ItemMedia>
            <Spinner className="size-5" />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>
              L'IA lit {plural(reading, "document", "documents")}…
            </ItemTitle>
            <ItemDescription>
              La page se met à jour toute seule.
            </ItemDescription>
          </ItemContent>
        </Item>
      )}

      {todo.length > 0 && <ListGroup title="À regarder">{todo}</ListGroup>}

      {toPay.length > 0 && (
        <ListGroup
          title="Bons à payer"
          action={
            <Link
              to="/reconciliations"
              search={{ filter: "to_pay" }}
              className="text-sm font-medium text-primary"
            >
              Tout voir
            </Link>
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
