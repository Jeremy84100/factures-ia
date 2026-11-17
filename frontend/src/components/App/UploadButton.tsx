import { Plus } from "lucide-react"
import { type ComponentProps, type ReactNode, useRef } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { ACCEPTED, useUpload } from "@/hooks/useUpload"

// With `camera`, a phone opens its camera straight away (one photo at a time);
// a computer simply offers to pick images.
export function useFilePicker({ camera = false }: { camera?: boolean } = {}) {
  const input = useRef<HTMLInputElement>(null)
  const { upload, isPending } = useUpload()
  const picker = (
    <input
      ref={input}
      type="file"
      accept={camera ? "image/*" : ACCEPTED}
      capture={camera ? "environment" : undefined}
      multiple={!camera}
      hidden
      data-testid="document-input"
      onChange={(e) => {
        upload(Array.from(e.target.files ?? []))
        e.target.value = ""
      }}
    />
  )
  return { picker, open: () => input.current?.click(), upload, isPending }
}

export function UploadButton({
  children = "Ajouter des documents",
  ...props
}: { children?: ReactNode } & Omit<
  ComponentProps<typeof Button>,
  "onClick" | "children"
>) {
  const { picker, open, isPending } = useFilePicker()
  return (
    <>
      {picker}
      <Button onClick={open} disabled={isPending} {...props}>
        {isPending ? (
          <Spinner data-icon="inline-start" />
        ) : (
          <Plus data-icon="inline-start" />
        )}
        {isPending ? "Envoi…" : children}
      </Button>
    </>
  )
}
