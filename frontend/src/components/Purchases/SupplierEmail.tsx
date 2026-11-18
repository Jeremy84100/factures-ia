import { useQuery } from "@tanstack/react-query"
import { Copy, Mail } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { ReconciliationsService, type SupplierEmail } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"

const mailto = ({ subject, body }: SupplierEmail) =>
  `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(
    body.replace(/\n/g, "\r\n"),
  )}`

function EmailForm({ email }: { email: SupplierEmail }) {
  const [subject, setSubject] = useState(email.subject)
  const [body, setBody] = useState(email.body)
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const copy = () =>
    navigator.clipboard
      .writeText(`${subject}\n\n${body}`)
      .then(() =>
        showSuccessToast("Mail copié, collez-le dans votre messagerie"),
      )
      .catch(() => showErrorToast("Impossible de copier le texte"))

  return (
    <Card size="sm">
      <CardContent>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="email-subject">Objet</FieldLabel>
            <Input
              id="email-subject"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="email-body">Message</FieldLabel>
            <Textarea
              id="email-body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
          </Field>
        </FieldGroup>
      </CardContent>
      <CardFooter className="flex-wrap gap-2">
        <Button asChild>
          <a href={mailto({ subject, body })}>
            <Mail data-icon="inline-start" />
            Ouvrir ma messagerie
          </a>
        </Button>
        <Button variant="secondary" onClick={copy}>
          <Copy data-icon="inline-start" />
          Copier
        </Button>
      </CardFooter>
    </Card>
  )
}

// The letter is written by the server from the comparison: the user only
// reads it, adds the supplier's address and sends it.
export function SupplierEmailSection({ purchaseKey }: { purchaseKey: string }) {
  const section = useRef<HTMLElement>(null)
  useEffect(() => {
    section.current?.scrollIntoView({ behavior: "smooth", block: "start" })
  }, [])
  const { data, isError } = useQuery({
    queryKey: ["purchases", purchaseKey, "email"],
    queryFn: async () =>
      (
        await ReconciliationsService.readSupplierEmail({
          path: { key: purchaseKey },
        })
      ).data,
  })
  return (
    <section ref={section} className="flex scroll-mt-4 flex-col gap-3">
      <h2 className="px-1 text-base font-semibold">Mail au fournisseur</h2>
      {data ? (
        <EmailForm email={data} />
      ) : isError ? (
        <p className="px-1 text-sm text-destructive">
          Impossible de préparer le mail.
        </p>
      ) : (
        <Spinner className="mx-auto" />
      )}
    </section>
  )
}
